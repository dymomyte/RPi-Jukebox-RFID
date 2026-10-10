from unittest.mock import Mock

import pytest

from components.player.backends.spotify import web_api
from components.player.backends.spotify.web_api import SpotifyWebApi


TRACK = {
    'type': 'track',
    'uri': 'spotify:track:T',
    'name': 'Track',
    'artists': [{'name': 'A1'}, {'name': 'A2'}],
    'album': {'name': 'Album', 'artists': [{'name': 'A1'}], 'images': [{'url': 'cover'}]},
    'track_number': 3,
    'duration_ms': 1500,
}


def connected_api(client):
    api = SpotifyWebApi.__new__(SpotifyWebApi)
    api.client_id = 'id'
    api._client = client
    api._auth_manager = Mock(get_cached_token=Mock(return_value={'access_token': 'x'}))
    api._metadata_cache = {}
    api._listing_cache = {}
    api._user_id = None
    client.current_user.return_value = {'id': 'me'}
    return api


def test_flatten_search_shapes_all_types():
    raw = {
        'tracks': {'items': [TRACK, None]},
        'albums': {'items': [{
            'uri': 'spotify:album:A', 'name': 'Album2',
            'artists': [{'name': 'Artist2'}], 'images': [{'url': 'cover2'}],
        }]},
        'playlists': {'items': [{
            'uri': 'spotify:playlist:P', 'name': 'Playlist3',
            'owner': {'display_name': 'Owner'}, 'images': [],
        }]},
    }

    assert web_api.flatten_search(raw) == [
        {'uri': 'spotify:track:T', 'type': 'track', 'name': 'Track', 'artists': ['A1', 'A2'],
         'album': 'Album', 'cover_url': 'cover', 'duration_ms': 1500},
        {'uri': 'spotify:album:A', 'type': 'album', 'name': 'Album2', 'artists': ['Artist2'],
         'album': 'Album2', 'cover_url': 'cover2', 'duration_ms': None},
        {'uri': 'spotify:playlist:P', 'type': 'playlist', 'name': 'Playlist3', 'artists': ['Owner'],
         'album': None, 'cover_url': None, 'duration_ms': None, 'tracks_available': True},
    ]


def test_library_items_use_player_contract_shape():
    playlist = {'uri': 'spotify:playlist:P', 'name': 'Mix', 'owner': {'display_name': 'Me'},
                'images': [{'url': 'img'}]}
    album = {'uri': 'spotify:album:A', 'name': 'Album', 'artists': [{'name': 'A1'}, {'name': 'A2'}],
             'images': []}

    assert web_api.shape_playlist_item(playlist) == {
        'provider': 'spotify', 'content_type': 'playlist', 'content_uri': 'spotify:playlist:P',
        'albumartist': 'Me', 'album': 'Mix', 'cover_url': 'img', 'tracks_available': True,
    }
    assert web_api.shape_album_item(album) == {
        'provider': 'spotify', 'content_type': 'album', 'content_uri': 'spotify:album:A',
        'albumartist': 'A1, A2', 'album': 'Album', 'cover_url': None,
    }


def test_song_shape_uses_seconds_and_song_url():
    assert web_api.shape_song(TRACK) == {
        'provider': 'spotify',
        'file': 'spotify:track:T',
        'title': 'Track',
        'artist': 'A1, A2',
        'album': 'Album',
        'albumartist': 'A1',
        'track': 3,
        'duration': 1.5,
        'cover_url': 'cover',
    }


def test_album_tracks_take_album_metadata_from_album():
    album_track = {key: value for key, value in TRACK.items() if key != 'album'}
    client = Mock()
    client.album.return_value = {
        'name': 'Whole Album', 'artists': [{'name': 'Band'}], 'images': [{'url': 'album-cover'}],
        'tracks': {'items': [album_track], 'next': None},
    }

    songs = connected_api(client).list_tracks('spotify:album:AID')

    client.album.assert_called_once_with('AID')
    assert songs[0]['album'] == 'Whole Album'
    assert songs[0]['cover_url'] == 'album-cover'


def test_playlist_tracks_accept_item_and_legacy_track_keys():
    episode = {'type': 'episode', 'uri': 'spotify:episode:E'}
    client = Mock()
    client.playlist_items.return_value = {
        'items': [{'item': TRACK}, {'track': {**TRACK, 'uri': 'spotify:track:U'}}, {'item': episode}, {'item': None}],
        'next': None,
    }

    songs = connected_api(client).list_tracks('https://open.spotify.com/playlist/PID')

    client.playlist_items.assert_called_once_with('PID', additional_types=('track',))
    assert [song['file'] for song in songs] == ['spotify:track:T', 'spotify:track:U']


def test_listings_follow_pages_up_to_limit(monkeypatch):
    monkeypatch.setattr(web_api, '_MAX_ENTRIES', 3)
    page = {'items': [{'uri': 'spotify:playlist:1'}, {'uri': 'spotify:playlist:2'}], 'next': 'page-2'}
    client = Mock()
    client.current_user_playlists.return_value = page
    client.next.return_value = {**page, 'next': 'page-3'}

    playlists = connected_api(client).list_playlists()

    assert len(playlists) == 3
    client.next.assert_called_once_with(page)


def test_saved_tracks_are_listed_as_songs():
    client = Mock()
    client.current_user_saved_tracks.return_value = {
        'items': [{'added_at': 'x', 'track': TRACK}, {'added_at': 'y', 'track': None}],
        'next': None,
    }

    songs = connected_api(client).list_saved_tracks()

    client.current_user_saved_tracks.assert_called_once_with(limit=web_api._PAGE_SIZE)
    assert songs == [web_api.shape_song(TRACK)]


def test_unlistable_content_raises():
    with pytest.raises(ValueError, match='Cannot list tracks'):
        connected_api(Mock()).list_tracks('spotify:track:T')


def test_unauthorized_api_returns_empty_results():
    api = SpotifyWebApi(client_id=None)
    assert api.is_connected() is False
    assert api.list_playlists() == []
    assert api.list_saved_tracks() == []
    assert api.list_tracks('spotify:album:A') == []
    assert api.search('query') == []
    assert api.get_song('spotify:track:T') == {}
    assert api.start_auth() == {'auth_url': ''}


def test_search_limit_is_clamped():
    client = Mock()
    client.search.return_value = {}
    connected_api(client).search('query', limit=50)
    assert client.search.call_args.kwargs['limit'] == web_api.MAX_SEARCH_LIMIT


def test_metadata_is_cached():
    client = Mock()
    client.track.return_value = TRACK
    api = connected_api(client)

    assert api.get_metadata('spotify:track:T')['cover_url'] == 'cover'
    assert api.get_metadata('https://open.spotify.com/track/T')['cover_url'] == 'cover'
    client.track.assert_called_once_with('T')


def test_listings_are_cached_until_expiry(monkeypatch):
    clock = Mock(return_value=1000.0)
    monkeypatch.setattr(web_api.time, 'monotonic', clock)
    client = Mock()
    client.current_user_playlists.return_value = {'items': [{'uri': 'spotify:playlist:1'}], 'next': None}
    api = connected_api(client)

    api.list_playlists()
    api.list_playlists()
    assert client.current_user_playlists.call_count == 1

    clock.return_value = 1000.0 + web_api.LISTING_TTL + 1
    api.list_playlists()
    assert client.current_user_playlists.call_count == 2


def test_listing_cache_is_cleared_after_authorization():
    client = Mock()
    client.current_user_playlists.return_value = {'items': [], 'next': None}
    api = connected_api(client)
    api.list_playlists()

    api.complete_auth('code')
    api.list_playlists()

    assert client.current_user_playlists.call_count == 2


@pytest.mark.parametrize(('playlist', 'expected'), [
    ({'owner': {'id': 'me'}}, True),
    ({'owner': {'id': 'other'}, 'collaborative': True}, True),
    ({'owner': {'id': 'other'}}, False),
])
def test_playlist_tracks_available_for_owned_or_collaborative(playlist, expected):
    assert web_api.playlist_tracks_available(playlist, 'me') is expected


def test_playlists_are_marked_with_track_availability():
    client = Mock()
    client.current_user_playlists.return_value = {'items': [
        {'uri': 'spotify:playlist:1', 'owner': {'id': 'me'}},
        {'uri': 'spotify:playlist:2', 'owner': {'id': 'other'}},
    ], 'next': None}

    playlists = connected_api(client).list_playlists()

    assert [p['tracks_available'] for p in playlists] == [True, False]


def test_search_marks_playlist_track_availability():
    client = Mock()
    client.search.return_value = {'playlists': {'items': [{'uri': 'spotify:playlist:2', 'owner': {'id': 'other'}}]}}

    results = connected_api(client).search('query')

    assert results[0]['tracks_available'] is False


def test_unshared_playlist_lists_no_tracks():
    error = Exception('Forbidden')
    error.http_status = 403
    client = Mock()
    client.playlist_items.side_effect = error

    assert connected_api(client).list_tracks('spotify:playlist:PID') == []


def test_other_playlist_errors_are_raised():
    error = Exception('Server error')
    error.http_status = 500
    client = Mock()
    client.playlist_items.side_effect = error

    with pytest.raises(Exception, match='Server error'):
        connected_api(client).list_tracks('spotify:playlist:PID')


def test_playlists_known_as_unshared_are_not_requested():
    client = Mock()
    client.current_user_playlists.return_value = {'items': [
        {'uri': 'spotify:playlist:theirs', 'owner': {'id': 'other'}},
    ], 'next': None}
    api = connected_api(client)
    api.list_playlists()

    assert api.list_tracks('spotify:playlist:theirs') == []
    client.playlist_items.assert_not_called()
