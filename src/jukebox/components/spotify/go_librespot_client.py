# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Thin REST client for the go-librespot HTTP control API.

go-librespot (https://github.com/devgianlu/go-librespot) exposes a local
REST + WebSocket API for controlling Spotify Connect playback. This client
wraps the REST subset we need using ``requests`` (already a project dependency).

Endpoints used (per go-librespot api-spec.yml, verified June 2026):

* ``GET  /status``           -> full player state
* ``POST /player/play``      {uri, skip_to_uri, paused}
* ``POST /player/resume``
* ``POST /player/pause``
* ``POST /player/stop``
* ``POST /player/playpause`` (toggle)
* ``POST /player/next``      {uri}
* ``POST /player/prev``
* ``POST /player/seek``      {position, relative}
* ``GET  /player/volume``    -> {value, max}
* ``POST /player/volume``    {volume, relative}

Note: the upstream API endpoint is ``/player/play`` (NOT ``/player/load`` as
assumed in early planning). Seek takes ``position`` in milliseconds with a
``relative`` flag (NOT ``position_ms``).
"""
import logging

import requests

logger = logging.getLogger('jb.spotify.golibrespot')


class GoLibrespotError(Exception):
    """Raised when a go-librespot request fails."""
    pass


class GoLibrespotClient:
    """REST client for a running go-librespot instance.

    :param host: Hostname / IP of the go-librespot HTTP API
    :param port: Port of the go-librespot HTTP API
    :param timeout: Per-request timeout in seconds
    """

    def __init__(self, host: str = 'localhost', port: int = 3678, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f'http://{host}:{port}'
        self._session = requests.Session()

    # -- low level ----------------------------------------------------------
    def _post(self, path: str, payload: dict = None):
        """POST to a go-librespot endpoint, raising GoLibrespotError on failure."""
        url = f'{self.base_url}{path}'
        try:
            response = self._session.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise GoLibrespotError(f"POST {path} failed: {e}") from e
        return response

    def _get(self, path: str):
        """GET from a go-librespot endpoint, raising GoLibrespotError on failure."""
        url = f'{self.base_url}{path}'
        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            raise GoLibrespotError(f"GET {path} failed: {e}") from e
        return response

    # -- high level ---------------------------------------------------------
    def is_reachable(self) -> bool:
        """Return True if the go-librespot API answers on GET /status."""
        try:
            self._get('/status')
            return True
        except GoLibrespotError:
            return False

    def status(self) -> dict:
        """Return the raw go-librespot player state (GET /status) as a dict."""
        response = self._get('/status')
        try:
            return response.json()
        except ValueError as e:
            raise GoLibrespotError(f"GET /status returned invalid JSON: {e}") from e

    def load(self, uri: str, play: bool = True, skip_to_uri: str = None):
        """Load and (optionally) start playing a Spotify URI.

        Maps to ``POST /player/play`` with ``paused = not play``.

        :param uri: Canonical ``spotify:<type>:<id>`` URI
        :param play: Start playing immediately (``paused=False``) if True
        :param skip_to_uri: Optional track URI within a context to start at
        """
        payload = {'uri': uri, 'paused': not play}
        if skip_to_uri is not None:
            payload['skip_to_uri'] = skip_to_uri
        return self._post('/player/play', payload)

    def resume(self):
        """Resume playback (POST /player/resume)."""
        return self._post('/player/resume')

    def play(self):
        """Resume playback. Alias of :meth:`resume` for the player contract."""
        return self.resume()

    def pause(self):
        """Pause playback (POST /player/pause)."""
        return self._post('/player/pause')

    def playpause(self):
        """Toggle play/pause (POST /player/playpause)."""
        return self._post('/player/playpause')

    def stop(self):
        """Stop playback (POST /player/stop)."""
        return self._post('/player/stop')

    def next(self, uri: str = None):
        """Skip to next track (POST /player/next)."""
        payload = {'uri': uri} if uri is not None else None
        return self._post('/player/next', payload)

    def prev(self):
        """Skip to previous track (POST /player/prev)."""
        return self._post('/player/prev')

    def seek(self, position_ms: int, relative: bool = False):
        """Seek to a position.

        Maps to ``POST /player/seek`` whose body uses ``position`` (in ms).

        :param position_ms: Target position in milliseconds
        :param relative: If True, seek relative to current position
        """
        return self._post('/player/seek', {'position': int(position_ms), 'relative': relative})

    def get_volume(self) -> dict:
        """Return current volume (GET /player/volume) as ``{value, max}``."""
        response = self._get('/player/volume')
        try:
            return response.json()
        except ValueError as e:
            raise GoLibrespotError(f"GET /player/volume returned invalid JSON: {e}") from e

    def set_volume(self, volume: int, relative: bool = False):
        """Set volume (POST /player/volume)."""
        return self._post('/player/volume', {'volume': volume, 'relative': relative})
