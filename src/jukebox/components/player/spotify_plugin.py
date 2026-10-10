"""Optional Spotify backend registration for the player plugin.

When ``spotify.enable`` is set, the Spotify backend is registered with the player
coordinator as ``spotify``. Spotify account functions that are not part of the
player contract (Web API authorization and catalog search) are registered as the
plugin ``player.spotify``.

## Publishes

* spotify.auth_status
"""

import logging
import os

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.publishing as publishing

from .backends.spotify import SpotifyBackend
from .backends.spotify.go_librespot_client import GoLibrespotClient
from .backends.spotify.web_api import SpotifyWebApi
from .coordinator import PlayerCoordinator


logger = logging.getLogger('jb.spotify')
cfg = jukebox.cfghandler.get_handler('jukebox')
cfg_credentials = jukebox.cfghandler.get_handler('spotify')


def resolve_path(path: str) -> str:
    """Resolve a config path relative to ``src/jukebox``, like all other settings paths."""
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        return expanded
    base = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))
    return os.path.abspath(os.path.join(base, expanded))


def credentials_file() -> str:
    return resolve_path(cfg.setndefault('spotify', 'credentials_file',
                                        value='../../shared/settings/spotify.yaml'))


def read_client_id():
    """Return the Spotify app client id from the credentials file, or None."""
    filename = credentials_file()
    if not os.path.isfile(filename):
        logger.info(f"No Spotify credentials file at '{filename}'")
        return None
    try:
        jukebox.cfghandler.load_yaml(cfg_credentials, filename)
    except Exception as e:
        logger.error(f"Could not read Spotify credentials file '{filename}': {e}")
        return None
    return cfg_credentials.getn('client_id', default=None) or None


def write_client_id(client_id: str) -> None:
    """Store the Spotify app client id in the credentials file."""
    filename = credentials_file()
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with cfg_credentials:
        cfg_credentials.setn('client_id', value=client_id)
        jukebox.cfghandler.write_yaml(cfg_credentials, filename)


def create_web_api() -> SpotifyWebApi:
    redirect_port = cfg.setndefault('spotify', 'web_api', 'redirect_port', value=8080)
    cache_path = resolve_path(cfg.setndefault('spotify', 'web_api', 'token_cache_file',
                                              value='../../shared/settings/spotify-token.json'))
    return SpotifyWebApi(client_id=read_client_id(), redirect_port=redirect_port, cache_path=cache_path)


class SpotifyAccount:
    """Spotify account functions beside the player contract (``player.spotify``)."""

    def __init__(self, backend: SpotifyBackend, web_api: SpotifyWebApi):
        self.backend = backend
        self.web_api = web_api

    def _publish_auth_status(self):
        publishing.get_publisher().send('spotify.auth_status', self.auth_status())

    @plugs.tag
    def auth_status(self) -> dict:
        """Return Web API authorization and go-librespot connection state"""
        return {
            'client_id_configured': bool(self.web_api.client_id),
            'web_api_connected': self.web_api.is_connected(),
            'go_librespot_connected': self.backend.connected,
        }

    @plugs.tag
    def set_client_id(self, client_id: str) -> dict:
        """Store the Spotify app client id and rebuild the Web API client"""
        client_id = (client_id or '').strip()
        write_client_id(client_id)
        self.web_api.set_client_id(client_id)
        self._publish_auth_status()
        return self.auth_status()

    @plugs.tag
    def start_auth(self) -> dict:
        """Start the Web API authorization (PKCE) and return the URL to open"""
        return self.web_api.start_auth()

    @plugs.tag
    def complete_auth(self, code_or_url: str) -> dict:
        """Complete the Web API authorization with the redirect URL or code"""
        result = self.web_api.complete_auth(code_or_url)
        self._publish_auth_status()
        return result

    @plugs.tag
    def search(self, query: str, types: str = 'track,album,playlist', limit: int = 10) -> list:
        """Search the Spotify catalog"""
        return self.web_api.search(query, types, limit)


def register_spotify_backend(player_ctrl: PlayerCoordinator, plugin_module_name: str):
    """Register the Spotify backend with the coordinator if it is enabled in the config.

    Errors are logged and never propagate, so a broken Spotify setup cannot keep
    the default (MPD) backend from loading.

    :return: The registered backend, or None if Spotify is disabled or failed to load
    """
    if not cfg.setndefault('spotify', 'enable', value=False):
        return None
    try:
        return _register_spotify_backend(player_ctrl, plugin_module_name)
    except Exception as e:
        logger.error(f"Spotify backend disabled: {e.__class__.__name__}: {e}")
        return None


def _register_spotify_backend(player_ctrl: PlayerCoordinator, plugin_module_name: str) -> SpotifyBackend:
    client = GoLibrespotClient(
        host=cfg.setndefault('spotify', 'go_librespot', 'host', value='localhost'),
        port=cfg.setndefault('spotify', 'go_librespot', 'port', value=3678),
    )
    web_api = create_web_api()
    backend = SpotifyBackend(client, web_api,
                             poll_interval=cfg.setndefault('spotify', 'status_poll_interval', value=0.25))
    backend.on_external_playback = lambda: player_ctrl.select_backend('spotify')
    player_ctrl.register_backend('spotify', backend)
    backend.start()

    account = SpotifyAccount(backend, web_api)
    plugs.register(account, name='spotify', package=plugs.loaded_as(plugin_module_name))
    account._publish_auth_status()
    logger.info("Registered Spotify player backend")
    return backend
