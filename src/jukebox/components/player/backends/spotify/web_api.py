# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Spotify Web API client for library browsing, search and cover art.

This is a *separate* concern from playback (go-librespot). It uses **spotipy**
with **Authorization Code + PKCE** (``spotipy.oauth2.SpotifyPKCE``) and a
``http://127.0.0.1:<port>/callback`` redirect (IP, NOT ``localhost`` -- required
since Spotify's 27 Nov 2025 OAuth migration). PKCE needs only the app's
``client_id``; no client secret is stored.

The token cache is persisted to a file under ``shared/settings/`` so the box
re-authenticates only once. spotipy handles token refresh transparently.

Only endpoints available to Development Mode apps after Spotify's February 2026
changes are used: ``/me/playlists``, ``/me/albums``, ``/albums/{id}``,
``/playlists/{id}``, ``/playlists/{id}/items``, ``/tracks/{id}`` and ``/search``.
Note that playlist contents are only returned for playlists the user owns or
collaborates on; other playlists can still be played and assigned to cards.
"""
import logging
import time

from . import uri_utils

logger = logging.getLogger('jb.spotify.webapi')

#: OAuth scopes: read access to the user's playlists and saved albums
SCOPE = 'playlist-read-private playlist-read-collaborative user-library-read'

#: Spotify caps the search 'limit' at 10 for Development Mode apps
MAX_SEARCH_LIMIT = 10

#: Page size for library and track listings (Spotify maximum)
_PAGE_SIZE = 50

#: Upper bound of entries fetched for a single listing, to keep the Web App responsive
_MAX_ENTRIES = 500

#: Seconds library and track listings are cached. Listings take several requests and
#: the player coordinator serializes catalog calls with playback commands.
LISTING_TTL = 300

PROVIDER = 'spotify'


class SpotifyWebApi:
    """Wrapper around spotipy providing Web App friendly results.

    Degrades gracefully: if spotipy is not installed, no client id is configured
    or the user has not authorized the app yet, the methods return empty results
    instead of raising.

    :param client_id: Spotify application client id
    :param redirect_port: Local port for the OAuth redirect listener
    :param cache_path: File path for the persisted token cache
    """

    def __init__(self, client_id: str = None, redirect_port: int = 8080, cache_path: str = None):
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.redirect_uri = f'http://127.0.0.1:{redirect_port}/callback'
        self.cache_path = cache_path
        self._auth_manager = None
        self._client = None
        # Per-URI metadata cache (Spotify object metadata is immutable), so the
        # card list / repeated cover lookups don't re-hit the Web API every render.
        self._metadata_cache = {}
        self._listing_cache = {}
        self.set_client_id(client_id)

    def set_client_id(self, client_id: str):
        """(Re)build the spotipy client and auth manager for ``client_id``."""
        self.client_id = client_id
        self._auth_manager = None
        self._client = None
        self._listing_cache = {}
        if not client_id:
            logger.warning("Spotify Web API disabled: client_id not configured")
            return
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyPKCE
        except ImportError:
            logger.warning("Spotify Web API disabled: 'spotipy' is not installed")
            return

        self._auth_manager = SpotifyPKCE(
            client_id=client_id,
            redirect_uri=self.redirect_uri,
            scope=SCOPE,
            cache_path=self.cache_path,
            open_browser=False,
        )
        self._client = spotipy.Spotify(auth_manager=self._auth_manager)

    # -- connection state ---------------------------------------------------
    def is_connected(self) -> bool:
        """Return True if a (cached) token with the required scopes is available."""
        if self._auth_manager is None:
            return False
        try:
            token = self._auth_manager.get_cached_token()
        except Exception as e:
            logger.debug(f"Could not read cached Spotify token: {e}")
            return False
        return token is not None

    # -- one-time auth flow -------------------------------------------------
    def start_auth(self) -> dict:
        """Begin the PKCE auth flow and return the URL the user must open.

        :return: ``{'auth_url': str}`` (empty string if unavailable)
        """
        if self._auth_manager is None:
            logger.warning("Cannot start Spotify auth: Web API not configured")
            return {'auth_url': ''}
        return {'auth_url': self._auth_manager.get_authorize_url()}

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
        self._listing_cache = {}
        return {'success': True}

    def _ready(self, purpose: str) -> bool:
        if self._client is None or not self.is_connected():
            logger.info(f"Spotify {purpose} unavailable: Web API not configured or not authorized")
            return False
        return True

    # -- library ------------------------------------------------------------
    def _cached(self, key: str, fetch):
        """Return the cached listing for ``key``, calling ``fetch`` when missing or expired."""
        now = time.monotonic()
        cached = self._listing_cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1]
        value = fetch()
        self._listing_cache[key] = (now + LISTING_TTL, value)
        return value

    def _collect(self, first_page: dict) -> list:
        """Follow spotipy paging objects until exhausted or ``_MAX_ENTRIES`` is reached."""
        items = []
        page = first_page
        while page:
            items.extend(entry for entry in (page.get('items') or []) if entry)
            if len(items) >= _MAX_ENTRIES or not page.get('next'):
                break
            page = self._client.next(page)
        return items[:_MAX_ENTRIES]

    def list_playlists(self) -> list:
        """Return the user's playlists as library items."""
        if not self._ready('playlists'):
            return []
        return self._cached('playlists', lambda: [
            shape_playlist_item(entry)
            for entry in self._collect(self._client.current_user_playlists(limit=_PAGE_SIZE))
        ])

    def list_saved_albums(self) -> list:
        """Return the user's saved albums as library items."""
        if not self._ready('saved albums'):
            return []
        return self._cached('albums', lambda: [
            shape_album_item(entry['album'])
            for entry in self._collect(self._client.current_user_saved_albums(limit=_PAGE_SIZE))
            if entry.get('album')
        ])

    def list_tracks(self, content_uri: str) -> list:
        """Return the tracks of an album or playlist as song entries.

        :param content_uri: Spotify album or playlist URI / share link
        """
        if not self._ready('track listing'):
            return []
        content_type, content_id = uri_utils.parse_uri(content_uri)
        if content_type not in ('album', 'playlist'):
            raise ValueError(f"Cannot list tracks of Spotify {content_type} '{content_uri}'")
        return self._cached(f'tracks:{content_type}:{content_id}',
                            lambda: self._fetch_tracks(content_type, content_id))

    def _fetch_tracks(self, content_type: str, content_id: str) -> list:
        if content_type == 'album':
            album = self._client.album(content_id)
            tracks = self._collect(album.get('tracks'))
            return [shape_song(track, album) for track in tracks]
        entries = self._collect(self._client.playlist_items(content_id, additional_types=('track',)))
        # Since February 2026 playlist entries carry the track as 'item' (previously 'track')
        tracks = (entry.get('item') or entry.get('track') for entry in entries)
        return [shape_song(track) for track in tracks if track and track.get('type', 'track') == 'track']

    def get_song(self, uri: str) -> dict:
        """Return a single track as song entry, or ``{}`` if unavailable."""
        if not self._ready('track lookup'):
            return {}
        _, track_id = uri_utils.parse_uri(uri)
        return shape_song(self._client.track(track_id))

    # -- search & metadata --------------------------------------------------
    def search(self, query: str, types: str = 'track,album,playlist', limit: int = MAX_SEARCH_LIMIT) -> list:
        """Search Spotify, returning a flat list of Web App friendly items.

        :param query: Free-text search query
        :param types: Comma-separated Spotify object types
        :param limit: Max items per type (clamped to ``MAX_SEARCH_LIMIT``)
        :return: list of dicts ``{uri, type, name, artists, album, cover_url, duration_ms}``
        """
        if not self._ready('search'):
            return []
        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
        try:
            raw = self._client.search(q=query, type=types, limit=limit)
        except Exception as e:
            logger.error(f"Spotify search failed: {e}")
            return []
        return flatten_search(raw)

    def get_metadata(self, uri: str) -> dict:
        """Return normalized metadata for a single Spotify URI.

        :param uri: A Spotify URI or share link
        :return: dict ``{uri, type, name, artists, album, cover_url, duration_ms}``
            or ``{}`` on error
        """
        if not self._ready('metadata'):
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
                result = shape_search_track(self._client.track(uri_id))
            elif uri_type == 'album':
                result = shape_search_album(self._client.album(uri_id))
            elif uri_type == 'playlist':
                result = shape_search_playlist(self._client.playlist(uri_id, fields='uri,name,owner,images'))
            else:
                logger.warning(f"get_metadata: unsupported type '{uri_type}'")
                return {}
        except Exception as e:
            logger.error(f"Spotify get_metadata failed for {uri}: {e}")
            return {}
        self._metadata_cache[cache_key] = result
        return result


# -- result shaping helpers (module level, pure -> easy to unit test) -------
def first_image_url(images):
    """Return the first image URL from a Spotify ``images`` list, or None."""
    if images:
        return images[0].get('url')
    return None


def artist_names(artists):
    """Return a list of artist name strings from a Spotify ``artists`` list."""
    return [a.get('name', '') for a in (artists or [])]


def shape_playlist_item(item: dict) -> dict:
    """Shape a Spotify playlist object into a player library item."""
    owner = item.get('owner') or {}
    return {
        'provider': PROVIDER,
        'content_type': 'playlist',
        'content_uri': item.get('uri'),
        'albumartist': owner.get('display_name') or owner.get('id'),
        'album': item.get('name'),
        'cover_url': first_image_url(item.get('images')),
    }


def shape_album_item(item: dict) -> dict:
    """Shape a Spotify album object into a player library item."""
    return {
        'provider': PROVIDER,
        'content_type': 'album',
        'content_uri': item.get('uri'),
        'albumartist': ', '.join(artist_names(item.get('artists'))),
        'album': item.get('name'),
        'cover_url': first_image_url(item.get('images')),
    }


def shape_song(track: dict, album: dict = None) -> dict:
    """Shape a Spotify track object into a player song entry.

    :param track: Spotify track object
    :param album: Album object for album track listings, whose tracks carry no album data
    """
    album = album or track.get('album') or {}
    duration_ms = track.get('duration_ms')
    return {
        'provider': PROVIDER,
        'file': track.get('uri'),
        'title': track.get('name'),
        'artist': ', '.join(artist_names(track.get('artists'))),
        'album': album.get('name'),
        'albumartist': ', '.join(artist_names(album.get('artists'))),
        'track': track.get('track_number'),
        'duration': duration_ms / 1000 if duration_ms is not None else None,
        'cover_url': first_image_url(album.get('images')),
    }


def shape_search_track(item: dict) -> dict:
    """Shape a Spotify track object into a search result."""
    album = item.get('album') or {}
    return {
        'uri': item.get('uri'),
        'type': 'track',
        'name': item.get('name'),
        'artists': artist_names(item.get('artists')),
        'album': album.get('name'),
        'cover_url': first_image_url(album.get('images')),
        'duration_ms': item.get('duration_ms'),
    }


def shape_search_album(item: dict) -> dict:
    """Shape a Spotify album object into a search result."""
    return {
        'uri': item.get('uri'),
        'type': 'album',
        'name': item.get('name'),
        'artists': artist_names(item.get('artists')),
        'album': item.get('name'),
        'cover_url': first_image_url(item.get('images')),
        'duration_ms': None,
    }


def shape_search_playlist(item: dict) -> dict:
    """Shape a Spotify playlist object into a search result."""
    owner = item.get('owner') or {}
    return {
        'uri': item.get('uri'),
        'type': 'playlist',
        'name': item.get('name'),
        'artists': [owner.get('display_name')] if owner.get('display_name') else [],
        'album': None,
        'cover_url': first_image_url(item.get('images')),
        'duration_ms': None,
    }


_SEARCH_SHAPERS = {
    'tracks': shape_search_track,
    'albums': shape_search_album,
    'playlists': shape_search_playlist,
}


def flatten_search(raw: dict) -> list:
    """Flatten a spotipy search response into a single ordered list of items.

    spotipy returns one keyed section per requested type, each with an
    ``items`` list (some entries may be ``None``).
    """
    results = []
    for section_key, shaper in _SEARCH_SHAPERS.items():
        section = raw.get(section_key) or {}
        for item in section.get('items') or []:
            if item:
                results.append(shaper(item))
    return results
