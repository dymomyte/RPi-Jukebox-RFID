# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Resume positions of Spotify podcasts and audiobooks.

For every show (podcast or audiobook) and every episode played on its own, the
store keeps the episode last heard and the position in it, so the next play
continues there. Positions live on the box and do not depend on Spotify.

Writes are atomic. While playing, positions are written at most every
:data:`SAVE_INTERVAL` seconds; pauses, stops and backend switches are written at once.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger('jb.spotify')

#: Spotify URI types that resume where they stopped
RESUMABLE_TYPES = ('show', 'episode')

#: Positions this close to the end of an episode count as finished
FINISHED_MARGIN_MS = 10000

#: Seconds between writes while playing
SAVE_INTERVAL = 30

#: Number of shows and episodes remembered; the least recently played are dropped
MAX_ENTRIES = 200


class ResumeStore:
    """Persistent resume positions keyed by the content URI that was played.

    :param path: JSON file the positions are kept in, or None to keep them in memory only
    """

    def __init__(self, path: str = None):
        self.path = path
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._entries = self._load()
        self._dirty = False
        self._last_save = time.monotonic()

    def _load(self) -> dict:
        if not self.path:
            return {}
        try:
            with open(self.path) as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            logger.warning(f"Could not read Spotify resume positions: {e}")
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, content_uri: str):
        """Return ``{episode, position_ms, duration_ms, updated}`` for ``content_uri``, or None."""
        with self._lock:
            entry = self._entries.get(content_uri)
            return dict(entry) if entry else None

    def update(self, content_uri: str, episode_uri: str, position_ms: int, duration_ms: int):
        """Remember that ``content_uri`` is at ``position_ms`` of ``episode_uri``."""
        with self._lock:
            entry = self._entries.get(content_uri) or {}
            if (entry.get('episode'), entry.get('position_ms')) == (episode_uri, int(position_ms)):
                return
            self._entries[content_uri] = {
                'episode': episode_uri,
                'position_ms': int(position_ms),
                'duration_ms': int(duration_ms),
                'updated': int(time.time()),
            }
            if len(self._entries) > MAX_ENTRIES:
                oldest = min(self._entries, key=lambda uri: self._entries[uri]['updated'])
                del self._entries[oldest]
            self._dirty = True

    def remove(self, content_uri: str):
        """Forget the position of ``content_uri``, so it starts from the beginning."""
        with self._lock:
            if self._entries.pop(content_uri, None) is not None:
                self._dirty = True

    def save(self, force: bool = False):
        """Write changed positions, at most every :data:`SAVE_INTERVAL` seconds unless ``force``."""
        with self._save_lock:
            with self._lock:
                if not self._dirty or not self.path:
                    return
                if not force and time.monotonic() - self._last_save < SAVE_INTERVAL:
                    return
                data = json.dumps(self._entries, indent=2)
                self._dirty = False
                self._last_save = time.monotonic()
            tmp_path = f'{self.path}.tmp'
            try:
                with open(tmp_path, 'w') as f:
                    f.write(data)
                os.replace(tmp_path, self.path)
            except OSError as e:
                logger.warning(f"Could not save Spotify resume positions: {e}")


def is_finished(entry: dict) -> bool:
    """Return True if the saved position is at the end of its episode."""
    return entry['duration_ms'] - entry['position_ms'] <= FINISHED_MARGIN_MS
