import json
from unittest.mock import Mock, call

import pytest

import jukebox.publishing as publishing

from components.player.backends.spotify import SpotifyBackend, resume
from components.player.backends.spotify.go_librespot_client import GoLibrespotError
from components.player.backends.spotify.resume import ResumeStore

SHOW = 'spotify:show:SHOW'
EPISODE = 'spotify:episode:EP2'


def episode_status(uri=EPISODE, position=60000, duration=600000, paused=False, stopped=False):
    return {
        'stopped': stopped,
        'paused': paused,
        'track': {'uri': uri, 'name': 'Chapter', 'position': position, 'duration': duration},
    }


@pytest.fixture(autouse=True)
def publisher(monkeypatch):
    monkeypatch.setattr(publishing, 'get_publisher', Mock(return_value=Mock()))


def make_backend(store=None):
    client = Mock()
    client.status.return_value = None
    return SpotifyBackend(client, resume_store=store or ResumeStore())


def test_store_persists_and_reloads(tmp_path):
    path = tmp_path / 'resume.json'
    store = ResumeStore(str(path))
    store.update(SHOW, EPISODE, 60000, 600000)
    store.save(force=True)

    assert ResumeStore(str(path)).get(SHOW)['position_ms'] == 60000
    assert set(json.loads(path.read_text())[SHOW]) == {'episode', 'position_ms', 'duration_ms', 'updated'}


def test_store_throttles_writes_while_playing(tmp_path, monkeypatch):
    path = tmp_path / 'resume.json'
    clock = Mock(return_value=1000.0)
    monkeypatch.setattr(resume.time, 'monotonic', clock)
    store = ResumeStore(str(path))

    store.update(SHOW, EPISODE, 1000, 600000)
    store.save()
    assert not path.exists()

    clock.return_value += resume.SAVE_INTERVAL
    store.save()
    assert path.exists()


def test_store_tolerates_a_broken_file(tmp_path):
    path = tmp_path / 'resume.json'
    path.write_text('{not json')
    assert ResumeStore(str(path)).get(SHOW) is None


def test_store_drops_the_least_recently_played(monkeypatch):
    monkeypatch.setattr(resume, 'MAX_ENTRIES', 2)
    clock = Mock(side_effect=[1, 2, 3])
    monkeypatch.setattr(resume.time, 'time', clock)
    store = ResumeStore()
    for uri in ('spotify:show:A', 'spotify:show:B', 'spotify:show:C'):
        store.update(uri, EPISODE, 1000, 600000)

    assert store.get('spotify:show:A') is None
    assert store.get('spotify:show:C') is not None


def test_playing_show_tracks_episode_and_position():
    backend = make_backend()
    backend.play_album('Author', 'Book', SHOW)
    backend.client.load.assert_called_once_with(SHOW)

    backend.client.status.return_value = episode_status(position=61000)
    backend._status_poll()

    assert backend.resume_store.get(SHOW)['episode'] == EPISODE
    assert backend.resume_store.get(SHOW)['position_ms'] == 61000


def test_show_resumes_at_saved_episode_and_position():
    store = ResumeStore()
    store.update(SHOW, EPISODE, 61000, 600000)
    backend = make_backend(store)

    backend.play_album('Author', 'Book', 'https://open.spotify.com/audiobook/SHOW')

    assert backend.client.method_calls == [
        call.load(SHOW, play=False, skip_to_uri=EPISODE),
        call.seek(61000),
        call.resume(),
    ]


def test_single_episode_resumes_at_saved_position():
    store = ResumeStore()
    store.update(EPISODE, EPISODE, 30000, 600000)
    backend = make_backend(store)

    backend.play_single(EPISODE)

    assert backend.client.method_calls == [
        call.load(EPISODE, play=False, skip_to_uri=None),
        call.seek(30000),
        call.resume(),
    ]


def test_music_is_not_tracked():
    backend = make_backend()
    backend.play_album('Artist', 'Album', 'spotify:album:AID')
    backend.client.status.return_value = episode_status()
    backend._status_poll()

    assert backend.resume_store.get('spotify:album:AID') is None


def test_status_read_before_a_load_is_not_tracked():
    backend = make_backend()
    backend.play_album('Author', 'Book A', 'spotify:show:A')

    def status_during_load():
        # Book B is loaded while the status of book A is read
        backend.play_album('Author', 'Book B', 'spotify:show:B')
        return episode_status(uri='spotify:episode:OF_A', position=99000)
    backend.client.status.side_effect = status_during_load
    backend._status_poll()

    assert backend.resume_store.get('spotify:show:B') is None


def test_finished_show_starts_over():
    backend = make_backend()
    backend.play_album('Author', 'Book', SHOW)
    backend.client.status.return_value = episode_status(position=595000, duration=600000)
    backend._status_poll()
    backend.client.status.return_value = {'stopped': True, 'paused': False, 'track': None}
    backend._status_poll()

    assert backend.resume_store.get(SHOW) is None


def test_stopped_show_keeps_its_position():
    backend = make_backend()
    backend.play_album('Author', 'Book', SHOW)
    backend.client.status.return_value = episode_status(position=60000)
    backend._status_poll()
    backend.client.status.return_value = {'stopped': True, 'paused': False, 'track': None}
    backend._status_poll()

    assert backend.resume_store.get(SHOW)['position_ms'] == 60000


def test_failed_resume_plays_from_the_beginning():
    store = ResumeStore()
    store.update(SHOW, 'spotify:episode:GONE', 61000, 600000)
    backend = make_backend(store)
    backend.client.load.side_effect = [GoLibrespotError('not in context'), None]

    backend.play_album('Author', 'Book', SHOW)

    assert backend.client.load.call_args_list[-1] == call(SHOW)
    assert store.get(SHOW) is None


def test_replay_starts_over():
    store = ResumeStore()
    store.update(SHOW, EPISODE, 61000, 600000)
    backend = make_backend(store)
    backend.play_album('Author', 'Book', SHOW)
    backend.client.reset_mock()

    backend.replay()

    backend.client.load.assert_called_once_with(SHOW)
    assert store.get(SHOW) is None


def test_switching_backend_or_connect_playback_stops_tracking():
    backend = make_backend()
    backend.play_album('Author', 'Book', SHOW)
    backend.set_active(False)
    backend.client.status.return_value = episode_status()
    backend._status_poll()

    assert backend.resume_store.get(SHOW) is None


def test_switching_content_saves_the_position_at_once(tmp_path):
    path = tmp_path / 'resume.json'
    backend = make_backend(ResumeStore(str(path)))
    backend.play_album('Author', 'Book', SHOW)
    backend.client.status.return_value = episode_status(position=61000)
    backend._status_poll()

    backend.play_single('spotify:track:T')

    assert json.loads(path.read_text())[SHOW]['position_ms'] == 61000
