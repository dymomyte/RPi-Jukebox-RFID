import sys
import os
from unittest import mock
# In case this is run locally
sys.path.append(os.path.abspath('../../src/jukebox'))

from components.spotify import spotify_web_api  # noqa: E402


def test_flatten_search_shapes_all_types():
    raw = {
        'tracks': {'items': [
            {
                'uri': 'spotify:track:T', 'name': 'Track1',
                'artists': [{'name': 'Artist1'}],
                'album': {'name': 'Album1', 'images': [{'url': 'cover1'}]},
                'duration_ms': 1000,
            },
            None,  # tolerate null entries
        ]},
        'albums': {'items': [
            {
                'uri': 'spotify:album:A', 'name': 'Album2',
                'artists': [{'name': 'Artist2'}],
                'images': [{'url': 'cover2'}],
            },
        ]},
        'playlists': {'items': [
            {
                'uri': 'spotify:playlist:P', 'name': 'Playlist3',
                'owner': {'display_name': 'Owner3'},
                'images': [{'url': 'cover3'}],
            },
        ]},
    }
    results = spotify_web_api._flatten_search(raw)
    assert len(results) == 3

    track = results[0]
    assert track == {
        'uri': 'spotify:track:T', 'type': 'track', 'name': 'Track1',
        'artists': ['Artist1'], 'album': 'Album1', 'cover_url': 'cover1',
        'duration_ms': 1000,
    }

    album = results[1]
    assert album['type'] == 'album'
    assert album['album'] == 'Album2'
    assert album['cover_url'] == 'cover2'
    assert album['duration_ms'] is None

    playlist = results[2]
    assert playlist['type'] == 'playlist'
    assert playlist['artists'] == ['Owner3']
    assert playlist['album'] is None


def test_flatten_search_missing_sections():
    assert spotify_web_api._flatten_search({}) == []
    assert spotify_web_api._flatten_search({'tracks': {'items': []}}) == []


def test_shape_track_handles_missing_album():
    shaped = spotify_web_api._shape_track({'uri': 'spotify:track:T', 'name': 'X'})
    assert shaped['album'] is None
    assert shaped['cover_url'] is None
    assert shaped['artists'] == []


def test_search_returns_empty_when_no_client():
    api = spotify_web_api.SpotifyWebApi(client_id=None)
    assert api.search('anything') == []
    assert api.is_connected() is False
    assert api.auth_status() == {'web_api_connected': False}


def test_search_delegates_to_spotipy_client():
    api = spotify_web_api.SpotifyWebApi(client_id=None)
    api._client = mock.MagicMock()
    api._client.search.return_value = {
        'tracks': {'items': [{'uri': 'spotify:track:T', 'name': 'N',
                              'artists': [], 'album': {}, 'duration_ms': 5}]}
    }
    results = api.search('query', types='track', limit=10)
    api._client.search.assert_called_once_with(q='query', type='track', limit=10)
    assert results[0]['uri'] == 'spotify:track:T'


def test_get_metadata_track():
    api = spotify_web_api.SpotifyWebApi(client_id=None)
    api._client = mock.MagicMock()
    api._client.track.return_value = {
        'uri': 'spotify:track:T', 'name': 'N', 'artists': [{'name': 'A'}],
        'album': {'name': 'AL', 'images': [{'url': 'c'}]}, 'duration_ms': 100,
    }
    meta = api.get_metadata('spotify:track:T')
    api._client.track.assert_called_once_with('T')
    assert meta['name'] == 'N'
    assert meta['cover_url'] == 'c'


def test_get_metadata_invalid_uri_returns_empty():
    api = spotify_web_api.SpotifyWebApi(client_id=None)
    api._client = mock.MagicMock()
    assert api.get_metadata('not-a-uri') == {}
