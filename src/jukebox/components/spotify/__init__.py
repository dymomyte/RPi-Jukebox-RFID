# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Spotify Player Plugin Package (go-librespot backend)

## Features

* Play Spotify tracks / albums / playlists from a card swipe or the Web App
* Sibling backend to MPD: only one backend plays at a time (mutual stop)
* First / second swipe handling (mirrors playermpd.play_card)
* Status polling of go-librespot and status publishing
* Spotify Web API search / browse / metadata (see spotify_web_api.py)

## Publishes

* spotify.status
* spotify.auth_status

## Integration

Playback runs on **go-librespot** (a local Spotify Connect daemon exposing a
REST API). Search / metadata uses the Spotify **Web API** via spotipy. Both
share the single PulseAudio sink and the single Spotify connection, so on
Spotify play we stop MPD (``player.ctrl.stop``) and vice-versa.

The player instance is registered as ``spotify.ctrl`` so cards / the webapp
call e.g. ``spotify.ctrl.play_spotify``. Web API functions are registered at
module level as ``spotify.search`` etc. (see :mod:`spotify_web_api`).

## Graceful disable

If ``spotify.enable`` is false, go-librespot is unreachable, or credentials
are missing, the package logs a clear "Spotify disabled" warning and degrades:
control methods log and no-op, ``auth_status`` reports false. It never raises
during initialize in a way that would crash other plugins.
"""
import logging
import os

from ruamel.yaml import YAML

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.multitimer as multitimer
import jukebox.publishing as publishing

from . import uri_utils
from . import spotify_web_api
from .go_librespot_client import GoLibrespotClient, GoLibrespotError

logger = logging.getLogger('jb.spotify')
cfg = jukebox.cfghandler.get_handler('jukebox')

#: Default location of the secrets file (relative to src/jukebox)
_DEFAULT_CREDENTIALS_FILE = '../../shared/settings/spotify.yaml'


def _resolve_path(path: str) -> str:
    """Resolve a possibly-relative path against the ``src/jukebox`` directory.

    Relative config paths like ``../../shared/settings/spotify.yaml`` follow the
    project convention of being relative to ``src/jukebox`` (see run_jukebox.py),
    which is two levels up from this component's directory.
    """
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        return expanded
    component_dir = os.path.dirname(os.path.realpath(__file__))
    base = os.path.abspath(os.path.join(component_dir, '..', '..'))
    return os.path.abspath(os.path.join(base, expanded))


def _credentials_file() -> str:
    """Return the resolved path to the Spotify credentials yaml file."""
    path = cfg.getn('spotify', 'credentials_file', default=_DEFAULT_CREDENTIALS_FILE)
    return _resolve_path(path)


def read_credentials() -> dict:
    """Read ``client_id`` / ``client_secret`` from the secrets file.

    :return: dict with keys ``client_id`` and ``client_secret`` (values may
        be ``None`` if the file is missing or incomplete)
    """
    filename = _credentials_file()
    result = {'client_id': None, 'client_secret': None}
    if not os.path.isfile(filename):
        logger.info(f"No Spotify credentials file at '{filename}'")
        return result
    try:
        yaml = YAML(typ='safe')
        with open(filename) as stream:
            data = yaml.load(stream) or {}
        result['client_id'] = data.get('client_id')
        result['client_secret'] = data.get('client_secret')
    except Exception as e:
        logger.error(f"Could not read Spotify credentials file '{filename}': {e}")
    return result


def write_credentials(client_id: str, client_secret: str) -> None:
    """Write ``client_id`` / ``client_secret`` to the secrets file."""
    filename = _credentials_file()
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    try:
        with open(filename, 'w') as stream:
            yaml.dump({'client_id': client_id, 'client_secret': client_secret}, stream)
        logger.info(f"Wrote Spotify credentials to '{filename}'")
    except Exception as e:
        logger.error(f"Could not write Spotify credentials file '{filename}': {e}")


def map_status(raw: dict) -> dict:
    """Map a raw go-librespot ``/status`` response to the ``spotify.status`` schema.

    :param raw: Raw dict from :meth:`GoLibrespotClient.status`
    :return: ``{connected, state, track, elapsed_ms}``
    """
    if not raw:
        return {'connected': False, 'state': 'stop', 'track': None, 'elapsed_ms': 0}

    if raw.get('stopped'):
        state = 'stop'
    elif raw.get('paused'):
        state = 'pause'
    else:
        state = 'play'

    track = None
    raw_track = raw.get('track')
    if raw_track:
        track = {
            'uri': raw_track.get('uri'),
            'name': raw_track.get('name'),
            'artists': raw_track.get('artist_names') or [],
            'album': raw_track.get('album_name'),
            'cover_url': raw_track.get('album_cover_url'),
            'duration_ms': raw_track.get('duration'),
        }
        elapsed_ms = int(raw_track.get('position') or 0)
    else:
        elapsed_ms = 0

    return {'connected': True, 'state': state, 'track': track, 'elapsed_ms': elapsed_ms}


class SpotifyPlayer:
    """Spotify playback controller backed by go-librespot.

    Mirrors the relevant parts of the player contract so cards and the webapp
    behave consistently across backends.
    """

    #: Map of second-swipe action aliases to bound methods
    def __init__(self, client: GoLibrespotClient, poll_interval: float = 0.25):
        self.client = client
        self.poll_interval = poll_interval
        self.last_played_uri = None
        self.last_status = {'connected': False, 'state': 'stop', 'track': None, 'elapsed_ms': 0}
        self._status_is_closing = False
        self._enabled = client.is_reachable()
        if not self._enabled:
            logger.warning("Spotify disabled: go-librespot is not reachable at "
                           f"{client.base_url}")

        self.second_swipe_action_dict = {
            'toggle': self.toggle,
            'play': self.play,
            'pause': self.pause,
            'skip': self.next,
            'stop': self.stop,
        }
        self.second_swipe_action = self._decode_2nd_swipe_option()

        self.status_thread = multitimer.GenericEndlessTimerClass(
            'spotify.timer_status', self.poll_interval, self._status_poll)
        self.status_thread.start()

    def _decode_2nd_swipe_option(self):
        """Resolve the configured second-swipe action (default: toggle)."""
        action = cfg.getn('spotify', 'second_swipe_action', 'alias', default='toggle')
        if isinstance(action, str):
            action = action.lower()
        if action in self.second_swipe_action_dict:
            return self.second_swipe_action_dict[action]
        if action in ('none', None):
            return None
        logger.warning(f"spotify.second_swipe_action '{action}' unknown; defaulting to 'toggle'")
        return self.toggle

    # -- lifecycle ----------------------------------------------------------
    def exit(self):
        """Shut down the status poll timer. Returns the timer thread."""
        logger.debug("Exit routine of SpotifyPlayer started")
        self._status_is_closing = True
        self.status_thread.cancel()
        return self.status_thread.timer_thread

    @plugs.tag
    def go_librespot_connected(self) -> bool:
        """Return True if go-librespot currently answers."""
        return self.client.is_reachable()

    # -- status -------------------------------------------------------------
    def _status_poll(self):
        """Poll go-librespot, map and publish status (called by the timer)."""
        if self._status_is_closing:
            return
        try:
            raw = self.client.status()
        except GoLibrespotError:
            # Only publish a disconnect transition once to avoid log/topic spam
            if self.last_status.get('connected'):
                self.last_status = {'connected': False, 'state': 'stop',
                                    'track': None, 'elapsed_ms': 0}
                publishing.get_publisher().send('spotify.status', self.last_status)
            return
        status = map_status(raw)
        self.last_status = status
        publishing.get_publisher().send('spotify.status', status)

    @plugs.tag
    def get_status(self) -> dict:
        """Return the most recent mapped status dict (``spotify.status`` schema)."""
        return self.last_status

    @plugs.tag
    def playerstatus(self) -> dict:
        """Alias of :meth:`get_status` for player-contract parity."""
        return self.last_status

    # -- playback control ---------------------------------------------------
    def _ensure_enabled(self) -> bool:
        """Return True if playback is possible, else log and return False."""
        if not self.client.is_reachable():
            logger.warning("Spotify disabled: go-librespot is not reachable")
            return False
        return True

    @plugs.tag
    def play_uri(self, uri: str):
        """Normalize ``uri``, stop MPD, then load + play it on go-librespot.

        :param uri: A Spotify URI or share link
        """
        try:
            normalized = uri_utils.normalize_uri(uri)
        except ValueError as e:
            logger.error(f"play_uri: {e}")
            return
        if not self._ensure_enabled():
            return
        # Arbitration: stop the local-files backend (no-op if not loaded)
        plugs.call_ignore_errors('player', 'ctrl', 'stop')
        try:
            self.client.load(normalized, play=True)
            self.last_played_uri = normalized
        except GoLibrespotError as e:
            logger.error(f"play_uri failed for {normalized}: {e}")

    @plugs.tag
    def play_spotify(self, uri: str):
        """Card entry point with first / second swipe handling.

        On the first swipe of a URI, delegates to :meth:`play_uri`. On a second
        swipe of the same URI, runs the configured second-swipe action
        (default: toggle).

        :param uri: A Spotify URI or share link
        """
        try:
            normalized = uri_utils.normalize_uri(uri)
        except ValueError as e:
            logger.error(f"play_spotify: {e}")
            return
        is_second_swipe = self.last_played_uri == normalized
        if self.second_swipe_action is not None and is_second_swipe:
            logger.debug('Calling second swipe action')
            self.second_swipe_action()
        else:
            logger.debug('Calling first swipe action')
            self.play_uri(normalized)

    @plugs.tag
    def play(self):
        """Resume playback."""
        if not self._ensure_enabled():
            return
        plugs.call_ignore_errors('player', 'ctrl', 'stop')
        try:
            self.client.play()
        except GoLibrespotError as e:
            logger.error(f"play failed: {e}")

    @plugs.tag
    def pause(self, state: int = 1):
        """Pause (``state=1``) or resume (``state=0``) playback."""
        if not self._ensure_enabled():
            return
        try:
            if state:
                self.client.pause()
            else:
                self.client.play()
        except GoLibrespotError as e:
            logger.error(f"pause failed: {e}")

    @plugs.tag
    def toggle(self):
        """Toggle play / pause."""
        if not self._ensure_enabled():
            return
        try:
            self.client.playpause()
        except GoLibrespotError as e:
            logger.error(f"toggle failed: {e}")

    @plugs.tag
    def next(self):
        """Skip to the next track."""
        if not self._ensure_enabled():
            return
        try:
            self.client.next()
        except GoLibrespotError as e:
            logger.error(f"next failed: {e}")

    @plugs.tag
    def prev(self):
        """Skip to the previous track."""
        if not self._ensure_enabled():
            return
        try:
            self.client.prev()
        except GoLibrespotError as e:
            logger.error(f"prev failed: {e}")

    @plugs.tag
    def stop(self):
        """Stop playback."""
        if not self.client.is_reachable():
            return
        try:
            self.client.stop()
        except GoLibrespotError as e:
            logger.error(f"stop failed: {e}")

    @plugs.tag
    def seek(self, new_time):
        """Seek to an absolute position in milliseconds."""
        if not self._ensure_enabled():
            return
        try:
            self.client.seek(int(new_time))
        except (GoLibrespotError, ValueError) as e:
            logger.error(f"seek failed: {e}")


# ---------------------------------------------------------------------------
# Web API RPC entry points (callable as spotify.<func>)
#
# These must live in the package __init__ so plugs deduces the package as
# 'spotify'. They delegate to the SpotifyWebApi instance in spotify_web_api.
# ---------------------------------------------------------------------------
@plugs.register
def search(query: str, types: str = 'track,album,playlist', limit: int = 10):
    """RPC: search Spotify (see :meth:`spotify_web_api.SpotifyWebApi.search`)."""
    if spotify_web_api.web_api is None:
        return []
    return spotify_web_api.web_api.search(query, types, limit)


@plugs.register
def get_metadata(uri: str) -> dict:
    """RPC: metadata for a Spotify URI."""
    if spotify_web_api.web_api is None:
        return {}
    return spotify_web_api.web_api.get_metadata(uri)


@plugs.register
def auth_status() -> dict:
    """RPC: combined Web API + go-librespot connection status."""
    result = {'web_api_connected': False, 'go_librespot_connected': False}
    if spotify_web_api.web_api is not None:
        result.update(spotify_web_api.web_api.auth_status())
    if player_ctrl is not None:
        try:
            result['go_librespot_connected'] = bool(player_ctrl.go_librespot_connected())
        except Exception as e:
            logger.debug(f"Could not read go-librespot status: {e}")
    return result


@plugs.register
def start_auth() -> dict:
    """RPC: start the PKCE auth flow."""
    if spotify_web_api.web_api is None:
        return {'auth_url': ''}
    return spotify_web_api.web_api.start_auth()


@plugs.register
def complete_auth(code_or_url: str) -> dict:
    """RPC: complete the PKCE auth flow."""
    if spotify_web_api.web_api is None:
        return {'success': False}
    return spotify_web_api.web_api.complete_auth(code_or_url)


@plugs.register
def set_credentials(client_id: str, client_secret: str) -> None:
    """RPC: persist Spotify app credentials to the secrets file and reload.

    Rebuilds the Web API client so new credentials take effect without a restart.
    """
    write_credentials(client_id, client_secret)
    api = spotify_web_api.web_api
    if api is not None:
        api.client_id = client_id
        api.client_secret = client_secret
        api._build_client()
        api._publish_auth_status()


# ---------------------------------------------------------------------------
# Plugin entry points
# ---------------------------------------------------------------------------
#: The active player instance (registered as spotify.ctrl)
player_ctrl: SpotifyPlayer = None


@plugs.initialize
def initialize():
    global player_ctrl

    enable = cfg.getn('spotify', 'enable', default=True)
    if not enable:
        logger.warning("Spotify disabled: 'spotify.enable' is false")

    host = cfg.getn('spotify', 'go_librespot', 'host', default='localhost')
    port = cfg.getn('spotify', 'go_librespot', 'port', default=3678)
    poll_interval = cfg.getn('spotify', 'status_poll_interval', default=0.25)
    redirect_port = cfg.getn('spotify', 'web_api', 'redirect_port', default=8080)

    client = GoLibrespotClient(host=host, port=port)
    player_ctrl = SpotifyPlayer(client, poll_interval=poll_interval)
    plugs.register(player_ctrl, name='ctrl')

    # Web API (search / metadata) -- separate concern, optional credentials
    creds = read_credentials()
    cache_path = _resolve_path('../../shared/settings/spotify-token.json')
    spotify_web_api.web_api = spotify_web_api.SpotifyWebApi(
        client_id=creds.get('client_id'),
        client_secret=creds.get('client_secret'),
        redirect_port=redirect_port,
        cache_path=cache_path,
    )
    if not creds.get('client_id'):
        logger.warning("Spotify Web API disabled: no credentials configured "
                       "(run ./run_register_spotify.sh or set them in the Web App)")

    # Publish initial auth status
    publishing.get_publisher().send('spotify.auth_status', auth_status())


@plugs.atexit
def atexit(**ignored_kwargs):
    global player_ctrl
    if player_ctrl is not None:
        return player_ctrl.exit()
