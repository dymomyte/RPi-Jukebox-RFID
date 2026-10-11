from unittest.mock import Mock, call

import pytest

import jukebox.publishing as publishing

from components.player.backends.spotify import SpotifyBackend, map_status
from components.player.backends.spotify.go_librespot_client import GoLibrespotError


PLAYING = {
    'stopped': False,
    'paused': False,
    'shuffle_context': False,
    'repeat_context': False,
    'repeat_track': False,
    'context_uri': 'spotify:album:AID',
    'play_origin_device_id': None,
    'track': {
        'uri': 'spotify:track:ID',
        'name': 'Song',
        'artist_names': ['A1', 'A2'],
        'album_name': 'Album',
        'album_cover_url': 'https://img/cover.jpg',
        'duration': 200000,
        'position': 12345,
    },
}


@pytest.fixture
def publisher(monkeypatch):
    publisher = Mock()
    monkeypatch.setattr(publishing, 'get_publisher', Mock(return_value=publisher))
    return publisher


def make_backend(raw=None, web_api=None):
    client = Mock()
    client.status.return_value = raw
    return SpotifyBackend(client, web_api)


def test_map_status_without_session_is_stopped():
    assert map_status(None) == {
        'state': 'stop',
        'random': '0',
        'repeat': '0',
        'single': '0',
        'provider': 'spotify',
    }


def test_map_status_uses_shared_playerstatus_shape():
    assert map_status(PLAYING) == {
        'state': 'play',
        'random': '0',
        'repeat': '0',
        'single': '0',
        'provider': 'spotify',
        'context_uri': 'spotify:album:AID',
        'songid': 'spotify:track:ID',
        'file': 'spotify:track:ID',
        'title': 'Song',
        'artist': 'A1, A2',
        'album': 'Album',
        'cover_url': 'https://img/cover.jpg',
        'elapsed': '12.345',
        'duration': '200.000',
    }


@pytest.mark.parametrize(('raw', 'expected'), [
    ({'paused': True}, {'state': 'pause'}),
    ({'stopped': True, 'track': PLAYING['track']}, {'state': 'stop'}),
    ({'shuffle_context': True}, {'random': '1', 'repeat': '0', 'single': '0'}),
    ({'repeat_context': True}, {'repeat': '1', 'single': '0'}),
    ({'repeat_track': True}, {'repeat': '1', 'single': '1'}),
])
def test_map_status_states_and_modes(raw, expected):
    status = map_status(raw)
    assert {key: status[key] for key in expected} == expected


def test_stopped_status_has_no_current_song():
    assert 'songid' not in map_status({'stopped': True, 'track': PLAYING['track']})


def test_inactive_backend_does_not_publish_status(publisher):
    backend = make_backend(PLAYING)

    backend._status_poll()

    publisher.send.assert_not_called()
    assert backend.playerstatus()['state'] == 'play'

    backend.set_active(True)
    publisher.send.assert_called_once_with('playerstatus', map_status(PLAYING))
    publisher.reset_mock()

    backend._status_poll()
    publisher.send.assert_called_once_with('playerstatus', map_status(PLAYING))


def test_unreachable_go_librespot_reports_stopped(publisher):
    backend = make_backend()
    backend.client.status.side_effect = GoLibrespotError('down')
    backend.set_active(True)
    publisher.reset_mock()

    backend._status_poll()

    assert backend.connected is False
    publisher.send.assert_called_once_with('playerstatus', map_status(None))


# go-librespot 0.7.4 leaves play_origin_device_id empty for Spotify Connect playback
@pytest.mark.parametrize('raw', [PLAYING, {**PLAYING, 'play_origin_device_id': 'phone'}])
def test_spotify_connect_playback_selects_backend(publisher, raw):
    backend = make_backend(raw)
    backend.on_external_playback = Mock()

    backend._status_poll()
    backend._status_poll()

    backend.on_external_playback.assert_called_once_with()


def test_spotify_connect_resume_selects_backend(publisher):
    backend = make_backend({**PLAYING, 'paused': True})
    backend.on_external_playback = Mock()
    backend._status_poll()

    backend.client.status.return_value = PLAYING
    backend._status_poll()

    backend.on_external_playback.assert_called_once_with()


@pytest.mark.parametrize(('raw', 'active'), [
    # Already the active backend
    (PLAYING, True),
    ({**PLAYING, 'paused': True}, False),
    (None, False),
])
def test_active_or_silent_playback_does_not_select_backend(publisher, raw, active):
    backend = make_backend(raw)
    backend.on_external_playback = Mock()
    backend._active = active

    backend._status_poll()

    backend.on_external_playback.assert_not_called()


def test_continued_playback_does_not_reselect_backend(publisher):
    # Polls that complete after the coordinator switched away from Spotify must
    # not switch back while Spotify is still reported as playing
    backend = make_backend(PLAYING)
    backend.on_external_playback = Mock()
    backend._active = True
    backend._status_poll()
    backend._active = False

    backend._status_poll()

    backend.on_external_playback.assert_not_called()


def test_seek_converts_seconds_to_milliseconds():
    backend = make_backend()
    backend.seek('12.3456')
    backend.client.seek.assert_called_once_with(12346)


def test_stop_never_raises():
    backend = make_backend()
    backend.client.stop.side_effect = GoLibrespotError('down')
    backend.stop()


def test_stop_skips_paused_player():
    # go-librespot 0.7.4 panics on /player/stop while paused
    backend = make_backend({**PLAYING, 'paused': True})
    backend.stop()
    backend.client.stop.assert_not_called()

    backend.client.status.return_value = PLAYING
    backend.stop()
    backend.client.stop.assert_called_once_with()


def test_stop_never_raises_when_status_fails():
    backend = make_backend()
    backend.client.status.side_effect = GoLibrespotError('down')
    backend.stop()


def test_pause_state():
    backend = make_backend()
    backend.pause()
    backend.pause(0)
    backend.client.pause.assert_called_once_with()
    backend.client.resume.assert_called_once_with()


@pytest.mark.parametrize(('raw', 'expected'), [
    ({}, call(context=True, track=False)),
    ({'repeat_context': True}, call(context=False, track=True)),
    ({'repeat_track': True}, call(context=False, track=False)),
])
def test_repeat_toggle_cycles_like_mpd(raw, expected):
    backend = make_backend(raw)
    backend._status_poll()

    backend.repeat()

    assert backend.client.set_repeat.call_args == expected


def test_shuffle_toggle():
    backend = make_backend({'shuffle_context': True})
    backend._status_poll()

    backend.shuffle()

    backend.client.set_shuffle.assert_called_once_with(False)


def test_play_content_normalizes_and_remembers_uri():
    backend = make_backend()

    backend.play_single('https://open.spotify.com/track/TID?si=x')
    backend.play_album('Artist', 'Album', 'spotify:playlist:PID')
    backend.replay()
    backend.play_album('Me', 'Liked Songs', 'spotify:user:me:collection')

    assert backend.client.load.call_args_list == [
        call('spotify:track:TID'),
        call('spotify:playlist:PID'),
        call('spotify:playlist:PID'),
        call('spotify:user:me:collection'),
    ]


def test_play_album_requires_content_uri():
    with pytest.raises(ValueError, match='no content URI'):
        make_backend().play_album('Artist', 'Album')


def test_replay_if_stopped():
    backend = make_backend({'stopped': True})
    backend.last_played_uri = 'spotify:album:AID'
    backend._status_poll()

    backend.replay_if_stopped()

    backend.client.load.assert_called_once_with('spotify:album:AID')


def test_volume_is_scaled_to_percent():
    backend = make_backend()
    backend.client.get_volume.return_value = {'value': 32768, 'max': 65535}

    assert backend.get_volume() == 50
    backend.set_volume(25)

    backend.client.set_volume.assert_called_once_with(16384)


def test_library_source_describes_spotify_views():
    assert make_backend().library_source() == {
        'id': 'spotify',
        'label': 'Spotify',
        'views': [
            {'id': 'playlists', 'label': 'Playlists', 'kind': 'items', 'content_types': ['playlist']},
            {'id': 'albums', 'label': 'Albums', 'kind': 'items', 'content_types': ['album']},
            {'id': 'songs', 'label': 'Songs', 'kind': 'songs', 'content_types': []},
            {'id': 'podcasts', 'label': 'Podcasts', 'kind': 'items', 'content_types': ['podcast']},
            {'id': 'audiobooks', 'label': 'Audiobooks', 'kind': 'items', 'content_types': ['audiobook']},
        ],
    }


def test_library_items_are_filtered_by_content_type():
    web_api = Mock()
    web_api.list_playlists.return_value = [{'content_type': 'playlist'}]
    web_api.list_saved_albums.return_value = [{'content_type': 'album'}]
    web_api.list_saved_podcasts.return_value = [{'content_type': 'podcast'}]
    web_api.list_saved_audiobooks.return_value = [{'content_type': 'audiobook'}]
    backend = make_backend(web_api=web_api)

    assert backend.list_library_items(['playlist']) == [{'content_type': 'playlist'}]
    assert backend.list_library_items(['album']) == [{'content_type': 'album'}]
    assert backend.list_library_items(['podcast', 'audiobook']) == [
        {'content_type': 'podcast'}, {'content_type': 'audiobook'}]
    assert [item['content_type'] for item in backend.list_library_items()] == [
        'playlist', 'album', 'podcast', 'audiobook']
    assert backend.list_library_items(['folder']) == []


def test_library_songs_are_the_liked_songs():
    web_api = Mock()
    web_api.list_saved_tracks.return_value = [{'file': 'spotify:track:T'}]

    assert make_backend(web_api=web_api).list_library_songs() == [{'file': 'spotify:track:T'}]


def test_catalog_lookups_use_content_uri():
    web_api = Mock()
    web_api.list_tracks.return_value = [{'file': 'spotify:track:T'}]
    web_api.get_song.return_value = {'file': 'spotify:track:T'}
    web_api.get_metadata.return_value = {'cover_url': 'https://img/cover.jpg'}
    backend = make_backend(web_api=web_api)

    assert backend.list_songs_by_artist_and_album('A', 'B', 'spotify:album:AID') == [{'file': 'spotify:track:T'}]
    assert backend.list_songs_by_artist_and_album('A', 'B') == []
    assert backend.get_song_by_url('spotify:track:T') == [{'file': 'spotify:track:T'}]
    assert backend.get_album_coverart('A', 'B', 'spotify:album:AID') == 'https://img/cover.jpg'
    assert backend.get_single_coverart('spotify:track:T') == 'https://img/cover.jpg'
    web_api.list_tracks.assert_called_once_with('spotify:album:AID')


def test_catalog_without_web_api_is_empty():
    backend = make_backend()
    assert backend.list_library_items() == []
    assert backend.list_library_songs() == []
    assert backend.get_song_by_url('spotify:track:T') == []
    assert backend.get_album_coverart('A', 'B', 'spotify:album:AID') is None
