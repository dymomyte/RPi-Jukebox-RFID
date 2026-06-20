import sys
import os
# In case this is run locally
sys.path.append(os.path.abspath('../../src/jukebox'))

from components.spotify import map_status  # noqa: E402


def test_map_status_empty():
    assert map_status({}) == {
        'connected': False, 'state': 'stop', 'track': None, 'elapsed_ms': 0,
    }


def test_map_status_stopped():
    status = map_status({'stopped': True, 'paused': False})
    assert status['connected'] is True
    assert status['state'] == 'stop'
    assert status['track'] is None


def test_map_status_paused():
    raw = {
        'stopped': False,
        'paused': True,
        'track': {
            'uri': 'spotify:track:ID',
            'name': 'Song',
            'artist_names': ['A1', 'A2'],
            'album_name': 'Album',
            'album_cover_url': 'http://img/cover.jpg',
            'duration': 200000,
            'position': 12345,
        },
    }
    status = map_status(raw)
    assert status['state'] == 'pause'
    assert status['elapsed_ms'] == 12345
    assert status['track'] == {
        'uri': 'spotify:track:ID',
        'name': 'Song',
        'artists': ['A1', 'A2'],
        'album': 'Album',
        'cover_url': 'http://img/cover.jpg',
        'duration_ms': 200000,
    }


def test_map_status_playing():
    raw = {'stopped': False, 'paused': False, 'track': {'uri': 'spotify:track:X', 'position': 0}}
    status = map_status(raw)
    assert status['state'] == 'play'
    assert status['connected'] is True
    assert status['track']['artists'] == []
    assert status['elapsed_ms'] == 0
