# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Spotify player backend (go-librespot)

Implements the player backend contract (see ``documentation/developers/player-backends.md``)
for Spotify. The backend is registered with the player coordinator as ``spotify``;
cards, the Web App and all other components keep talking to ``player.ctrl``.

## Features

* Playback of Spotify tracks, albums and playlists through ``play_single`` and
  ``play_album`` with ``provider='spotify'`` and the Spotify URI as content URI
* Transport controls, seek, shuffle and repeat through go-librespot
* Status polling of go-librespot; ``playerstatus`` is published in the same shape
  as the MPD backend, but only while this backend is active
* Library source with the user's playlists and saved albums (Spotify Web API)
* Spotify Connect playback started from another device selects this backend,
  so the coordinator stops the previously active backend

## Publishes

* playerstatus (while active)

## Integration

Playback runs on **go-librespot**, a local Spotify Connect daemon exposing a
REST API. Library browsing and cover art use the Spotify **Web API** via spotipy
(see :mod:`web_api`) and are optional: without Web API authorization, cards and
playback keep working, only the library listings stay empty.
"""
import logging
import threading

import jukebox.multitimer as multitimer
import jukebox.publishing as publishing

from . import uri_utils
from .go_librespot_client import GoLibrespotClient, GoLibrespotError
from .web_api import SpotifyWebApi

logger = logging.getLogger('jb.spotify')

PROVIDER = 'spotify'


def map_status(raw) -> dict:
    """Map a raw go-librespot ``/status`` response to the shared ``playerstatus`` shape.

    The keys mirror the subset of the MPD status the Web App and other components
    consume (``state``, ``songid``, ``title``, ``elapsed`` in seconds, ...).

    :param raw: Raw dict from :meth:`GoLibrespotClient.status`, or None
    """
    status = {
        'state': 'stop',
        'random': '0',
        'repeat': '0',
        'single': '0',
        'provider': PROVIDER,
    }
    if not raw:
        return status

    if raw.get('stopped'):
        status['state'] = 'stop'
    elif raw.get('paused'):
        status['state'] = 'pause'
    else:
        status['state'] = 'play'

    repeat_track = bool(raw.get('repeat_track'))
    status['random'] = '1' if raw.get('shuffle_context') else '0'
    status['repeat'] = '1' if (raw.get('repeat_context') or repeat_track) else '0'
    status['single'] = '1' if repeat_track else '0'

    if raw.get('context_uri'):
        status['context_uri'] = raw['context_uri']

    track = raw.get('track')
    if track and not raw.get('stopped'):
        status.update({
            'songid': track.get('uri'),
            'file': track.get('uri'),
            'title': track.get('name'),
            'artist': ', '.join(track.get('artist_names') or []),
            'album': track.get('album_name'),
            'cover_url': track.get('album_cover_url'),
            'elapsed': f"{(track.get('position') or 0) / 1000:.3f}",
            'duration': f"{(track.get('duration') or 0) / 1000:.3f}",
        })
    return status


class SpotifyBackend:
    """Player backend for Spotify playback through go-librespot.

    :param client: go-librespot REST client
    :param web_api: Spotify Web API wrapper for library browsing and cover art
    :param poll_interval: Status poll interval in seconds
    """

    def __init__(self, client: GoLibrespotClient, web_api: SpotifyWebApi = None, poll_interval: float = 0.25):
        self.client = client
        self.web_api = web_api
        self.poll_interval = poll_interval
        #: Called without arguments when Spotify Connect playback starts while the
        #: backend is inactive. The plugin sets this to select the backend.
        self.on_external_playback = None
        self.last_played_uri = None
        self.connected = False
        self._active = False
        self._was_playing = False
        self._status = map_status(None)
        self._status_lock = threading.Lock()
        self.status_thread = None

    def start(self):
        """Start polling go-librespot for status."""
        self.status_thread = multitimer.GenericEndlessTimerClass('spotify.timer_status',
                                                                 self.poll_interval, self._status_poll)
        self.status_thread.start()

    def exit(self):
        logger.debug("Exit routine of Spotify backend started")
        if self.status_thread is None:
            return None
        self.status_thread.close()
        return self.status_thread.timer_thread

    def set_active(self, active):
        self._active = active
        if active:
            publishing.get_publisher().send('playerstatus', self.playerstatus())

    # -- status -------------------------------------------------------------
    def _status_poll(self):
        """Poll go-librespot and publish the mapped status while active."""
        try:
            raw = self.client.status()
            self.connected = True
        except GoLibrespotError as e:
            if self.connected:
                logger.warning(f"Lost connection to go-librespot: {e}")
            raw = None
            self.connected = False

        status = map_status(raw)
        playing = status['state'] == 'play'
        # go-librespot reports the controlling device for playback that was not
        # started through its local API, i.e. from a Spotify app via Spotify Connect
        started_externally = (playing and not self._was_playing and not self._active
                              and bool(raw.get('play_origin_device_id')))
        self._was_playing = playing
        with self._status_lock:
            self._status = status

        if started_externally and self.on_external_playback is not None:
            logger.info("Spotify Connect playback started from another device")
            self.on_external_playback()
        elif self._active:
            publishing.get_publisher().send('playerstatus', status)

    def playerstatus(self):
        with self._status_lock:
            return dict(self._status)

    def get_current_song(self, param):
        return self.playerstatus()

    def get_player_type_and_version(self):
        return 'go-librespot'

    # -- transport ----------------------------------------------------------
    def play(self):
        self.client.resume()

    def resume(self):
        self.client.resume()

    def stop(self):
        # Never raise: the coordinator stops the active backend before switching,
        # which must succeed even if go-librespot is not running
        try:
            self.client.stop()
        except GoLibrespotError as e:
            logger.warning(f"Could not stop Spotify playback: {e}")

    def pause(self, state: int = 1):
        """Enforce pause to state (1: pause, 0: resume)"""
        if state:
            self.client.pause()
        else:
            self.client.resume()

    def toggle(self):
        self.client.playpause()

    def prev(self):
        self.client.prev()

    def next(self):
        self.client.next()

    def seek(self, new_time):
        """Seek to an absolute position in seconds (the unit shared with the MPD backend)"""
        self.client.seek(round(float(new_time) * 1000))

    def replay(self):
        """Play the last played Spotify content from the beginning"""
        if self.last_played_uri is None:
            logger.info("Nothing to replay: no Spotify content played yet")
            return
        self.client.load(self.last_played_uri)

    def rewind(self):
        self.replay()

    def replay_if_stopped(self):
        if self.playerstatus()['state'] == 'stop':
            self.replay()

    def shuffle(self, option='toggle'):
        if option == 'toggle':
            self.client.set_shuffle(self.playerstatus()['random'] == '0')
        elif option == 'enable':
            self.client.set_shuffle(True)
        elif option == 'disable':
            self.client.set_shuffle(False)
        else:
            logger.error(f"'{option}' does not exist for 'shuffle'")

    def _repeatmode(self, mode):
        self.client.set_repeat(context=mode == 'repeat', track=mode == 'single')

    def repeat(self, option='toggle'):
        status = self.playerstatus()
        if option == 'toggle':
            if status['repeat'] == '0':
                self._repeatmode('repeat')
            elif status['single'] == '0':
                self._repeatmode('single')
            else:
                self._repeatmode(None)
        elif option == 'toggle_repeat':
            self._repeatmode('repeat' if status['repeat'] == '0' else None)
        elif option == 'toggle_repeat_single':
            self._repeatmode('single' if status['single'] == '0' else None)
        elif option == 'enable_repeat':
            self._repeatmode('repeat')
        elif option == 'enable_repeat_single':
            self._repeatmode('single')
        elif option == 'disable':
            self._repeatmode(None)
        else:
            logger.error(f"'{option}' does not exist for 'repeat'")

    def get_volume(self):
        volume = self.client.get_volume()
        return round(100 * volume['value'] / volume['max']) if volume.get('max') else 0

    def set_volume(self, volume):
        maximum = self.client.get_volume().get('max') or 100
        self.client.set_volume(round(int(volume) * maximum / 100))
        return self.get_volume()

    # -- content ------------------------------------------------------------
    def _play_uri(self, uri: str):
        normalized = uri_utils.normalize_uri(uri)
        logger.info(f"Play Spotify content: '{normalized}'")
        self.client.load(normalized)
        self.last_played_uri = normalized

    def play_single(self, song_url):
        """Play a Spotify track (or any other Spotify URI / share link)"""
        self._play_uri(song_url)

    def play_album(self, albumartist: str, album: str, content_uri=None):
        """Play a Spotify album or playlist identified by ``content_uri``"""
        if not content_uri:
            raise ValueError(f"Spotify album '{album}' by '{albumartist}' has no content URI")
        self._play_uri(content_uri)

    def get_single_coverart(self, song_url):
        if self.web_api is None:
            return None
        return self.web_api.get_metadata(song_url).get('cover_url')

    def get_album_coverart(self, albumartist: str, album: str, content_uri=None):
        if self.web_api is None or not content_uri:
            return None
        return self.web_api.get_metadata(content_uri).get('cover_url')

    # -- library ------------------------------------------------------------
    def library_source(self):
        return {
            'id': PROVIDER,
            'label': 'Spotify',
            'views': [
                {
                    'id': 'playlists',
                    'label': 'Playlists',
                    'kind': 'items',
                    'content_types': ['playlist'],
                },
                {
                    'id': 'albums',
                    'label': 'Albums',
                    'kind': 'items',
                    'content_types': ['album'],
                },
            ],
        }

    def list_library_items(self, content_types=None):
        if self.web_api is None:
            return []
        items = []
        if content_types is None or 'playlist' in content_types:
            items.extend(self.web_api.list_playlists())
        if content_types is None or 'album' in content_types:
            items.extend(self.web_api.list_saved_albums())
        return items

    def list_albums(self):
        return self.list_library_items()

    def list_songs_by_artist_and_album(self, albumartist, album, content_uri=None):
        if self.web_api is None or not content_uri:
            return []
        return self.web_api.list_tracks(content_uri)

    def get_song_by_url(self, song_url):
        if self.web_api is None:
            return []
        song = self.web_api.get_song(song_url)
        return [song] if song else []
