# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Spotify Web API client for search / browse / metadata.

This is a *separate* concern from playback (go-librespot). It uses **spotipy**
with **Authorization Code + PKCE** (``spotipy.oauth2.SpotifyPKCE``) and a
``http://127.0.0.1:<port>/callback`` redirect (IP, NOT ``localhost`` -- required
since Spotify's 27 Nov 2025 OAuth migration).

The token cache is persisted to a file under ``shared/settings/`` so the box
re-authenticates only once. spotipy handles token refresh transparently.

Only non-deprecated endpoints are used (search, tracks, albums, playlists).
The recommendations / audio-features endpoints are intentionally avoided.

## Publishes

* spotify.auth_status
"""
import logging

import jukebox.publishing as publishing

from . import uri_utils

logger = logging.getLogger('jb.spotify.webapi')

# OAuth scopes: enough for search/metadata plus reading playback state.
# 'streaming' + 'user-read-*' allow future Connect control via the Web API too.
_SCOPE = 'user-read-playback-state user-modify-playback-state streaming user-read-email user-read-private'

# Spotify rejects search 'limit' values above ~10 with HTTP 400 "Invalid limit"
# for apps on the default (development-mode) quota -- despite the documented
# 0-50 range. Clamp to a value that is reliably accepted. (Observed on a real
# dev-mode app: limit=10 works, 16+ returns 400.)
_MAX_SEARCH_LIMIT = 10


class SpotifyWebApi:
    """Wrapper around spotipy providing webapp-friendly search and metadata.

    Degrades gracefully: if spotipy is not installed or credentials are
    missing, the client stays disconnected and methods return empty / error
    results instead of raising.

    :param client_id: Spotify application client id
    :param client_secret: Spotify application client secret (unused by PKCE,
        kept for parity / future client-credentials use)
    :param redirect_port: Local port for the OAuth redirect listener
    :param cache_path: File path for the persisted token cache
    """

    def __init__(self, client_id: str = None, client_secret: str = None,
                 redirect_port: int = 8080, cache_path: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_port = redirect_port
        self.redirect_uri = f'http://127.0.0.1:{redirect_port}/callback'
        self.cache_path = cache_path
        self._auth_manager = None
        self._client = None
        # Per-URI metadata cache (Spotify object metadata is immutable), so the
        # card list / repeated lookups don't re-hit the Web API every render.
        self._metadata_cache = {}
        self._build_client()

    def _build_client(self):
        """(Re)build the spotipy client and auth manager from current creds."""
        self._auth_manager = None
        self._client = None
        if not self.client_id:
            logger.warning("Spotify Web API disabled: client_id not configured")
            return
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyPKCE
        except ImportError:
            logger.warning("Spotify Web API disabled: 'spotipy' is not installed")
            return

        self._auth_manager = SpotifyPKCE(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=_SCOPE,
            cache_path=self.cache_path,
            open_browser=False,
        )
        self._client = spotipy.Spotify(auth_manager=self._auth_manager)

    # -- connection state ---------------------------------------------------
    def is_connected(self) -> bool:
        """Return True if a (cached) token is available and usable."""
        if self._auth_manager is None:
            return False
        try:
            token = self._auth_manager.get_cached_token()
        except Exception as e:
            logger.debug(f"Could not read cached Spotify token: {e}")
            return False
        return token is not None

    def auth_status(self) -> dict:
        """Return Web API connection status (go-librespot status added by player)."""
        return {'web_api_connected': self.is_connected()}

    # -- one-time auth flow -------------------------------------------------
    def start_auth(self) -> dict:
        """Begin the PKCE auth flow and return the URL the user must open.

        :return: ``{'auth_url': str}`` (empty string if unavailable)
        """
        if self._auth_manager is None:
            logger.warning("Cannot start Spotify auth: Web API not configured")
            return {'auth_url': ''}
        auth_url = self._auth_manager.get_authorize_url()
        return {'auth_url': auth_url}

    def complete_auth(self, code_or_url: str) -> dict:
        """Complete the PKCE auth flow with the redirect code or full URL.

        :param code_or_url: The ``code`` query param OR the full redirect URL
        :return: ``{'success': bool}``
        """
        if self._auth_manager is None:
            return {'success': False}
        try:
            code = code_or_url
            if '://' in code_or_url or 'code=' in code_or_url:
                code = self._auth_manager.parse_response_code(code_or_url)
            self._auth_manager.get_access_token(code)
        except Exception as e:
            logger.error(f"Spotify auth completion failed: {e}")
            return {'success': False}
        self._publish_auth_status()
        return {'success': True}

    def _publish_auth_status(self):
        publishing.get_publisher().send('spotify.auth_status', self.auth_status())

    # -- search & metadata --------------------------------------------------
    def search(self, query: str, types: str = 'track,album,playlist', limit: int = _MAX_SEARCH_LIMIT):
        """Search Spotify, returning a flat list of webapp-friendly items.

        :param query: Free-text search query
        :param types: Comma-separated Spotify object types
        :param limit: Max items per type (clamped to ``_MAX_SEARCH_LIMIT`` to
            avoid Spotify's dev-mode "Invalid limit" 400)
        :return: list of dicts ``{uri, type, name, artists, album, cover_url, duration_ms}``
        """
        if self._client is None:
            logger.warning("Spotify search unavailable: Web API not configured")
            return []
        limit = max(1, min(limit, _MAX_SEARCH_LIMIT))
        try:
            raw = self._client.search(q=query, type=types, limit=limit)
        except Exception as e:
            logger.error(f"Spotify search failed: {e}")
            return []
        return _flatten_search(raw)

    def get_metadata(self, uri: str) -> dict:
        """Return normalized metadata for a single Spotify URI.

        :param uri: A Spotify URI or share link
        :return: dict ``{uri, type, name, artists, album, cover_url, duration_ms}``
            or ``{}`` on error
        """
        if self._client is None:
            logger.warning("Spotify metadata unavailable: Web API not configured")
            return {}
        try:
            uri_type, uri_id = uri_utils.parse_uri(uri)
        except ValueError as e:
            logger.error(f"get_metadata: {e}")
            return {}
        cache_key = f"{uri_type}:{uri_id}"
        cached = self._metadata_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            if uri_type == 'track':
                result = _shape_track(self._client.track(uri_id))
            elif uri_type == 'album':
                result = _shape_album(self._client.album(uri_id))
            elif uri_type == 'playlist':
                result = _shape_playlist(self._client.playlist(uri_id))
            else:
                logger.warning(f"get_metadata: unsupported type '{uri_type}'")
                return {}
        except Exception as e:
            logger.error(f"Spotify get_metadata failed for {uri}: {e}")
            return {}
        self._metadata_cache[cache_key] = result
        return result


# -- result shaping helpers (module level, pure -> easy to unit test) -------
def _first_image_url(images):
    """Return the first image URL from a Spotify ``images`` list, or None."""
    if images:
        return images[0].get('url')
    return None


def _artist_names(artists):
    """Return a list of artist name strings from a Spotify ``artists`` list."""
    return [a.get('name', '') for a in (artists or [])]


def _shape_track(item: dict) -> dict:
    """Shape a Spotify track object into the contract dict."""
    album = item.get('album') or {}
    return {
        'uri': item.get('uri'),
        'type': 'track',
        'name': item.get('name'),
        'artists': _artist_names(item.get('artists')),
        'album': album.get('name'),
        'cover_url': _first_image_url(album.get('images')),
        'duration_ms': item.get('duration_ms'),
    }


def _shape_album(item: dict) -> dict:
    """Shape a Spotify album object into the contract dict."""
    return {
        'uri': item.get('uri'),
        'type': 'album',
        'name': item.get('name'),
        'artists': _artist_names(item.get('artists')),
        'album': item.get('name'),
        'cover_url': _first_image_url(item.get('images')),
        'duration_ms': None,
    }


def _shape_playlist(item: dict) -> dict:
    """Shape a Spotify playlist object into the contract dict."""
    owner = item.get('owner') or {}
    return {
        'uri': item.get('uri'),
        'type': 'playlist',
        'name': item.get('name'),
        'artists': [owner.get('display_name')] if owner.get('display_name') else [],
        'album': None,
        'cover_url': _first_image_url(item.get('images')),
        'duration_ms': None,
    }


_SHAPERS = {
    'tracks': _shape_track,
    'albums': _shape_album,
    'playlists': _shape_playlist,
}


def _flatten_search(raw: dict) -> list:
    """Flatten a spotipy search response into a single ordered list of items.

    spotipy returns one keyed section per requested type, each with an
    ``items`` list (some entries may be ``None``).
    """
    results = []
    for section_key, shaper in _SHAPERS.items():
        section = raw.get(section_key) or {}
        for item in section.get('items') or []:
            if item:
                results.append(shaper(item))
    return results


#: The active Web API instance, set by the package initializer
#: (:func:`components.spotify.initialize`). The plugin-registered RPC
#: functions in the package ``__init__`` delegate to this instance.
web_api: SpotifyWebApi = None
