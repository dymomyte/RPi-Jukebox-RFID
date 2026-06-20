import sys
import os
from unittest import mock
# In case this is run locally
sys.path.append(os.path.abspath('../../src/jukebox'))

import pytest  # noqa: E402
import requests  # noqa: E402
from components.spotify.go_librespot_client import GoLibrespotClient, GoLibrespotError  # noqa: E402


def _make_client():
    client = GoLibrespotClient(host='testhost', port=1234)
    client._session = mock.MagicMock()
    return client


def _ok_response(json_body=None):
    resp = mock.MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def test_base_url():
    client = GoLibrespotClient(host='myhost', port=9999)
    assert client.base_url == 'http://myhost:9999'


def test_load_builds_play_request():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    client.load('spotify:track:ID', play=True)
    client._session.post.assert_called_once()
    args, kwargs = client._session.post.call_args
    assert args[0] == 'http://testhost:1234/player/play'
    assert kwargs['json'] == {'uri': 'spotify:track:ID', 'paused': False}


def test_load_paused():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    client.load('spotify:track:ID', play=False)
    _, kwargs = client._session.post.call_args
    assert kwargs['json']['paused'] is True


def test_load_skip_to_uri():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    client.load('spotify:album:AID', play=True, skip_to_uri='spotify:track:T')
    _, kwargs = client._session.post.call_args
    assert kwargs['json']['skip_to_uri'] == 'spotify:track:T'


def test_seek_uses_position_field():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    client.seek(42000)
    args, kwargs = client._session.post.call_args
    assert args[0] == 'http://testhost:1234/player/seek'
    assert kwargs['json'] == {'position': 42000, 'relative': False}


def test_pause_next_prev_stop_endpoints():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    for method, path in [
        (client.pause, '/player/pause'),
        (client.resume, '/player/resume'),
        (client.playpause, '/player/playpause'),
        (client.prev, '/player/prev'),
        (client.stop, '/player/stop'),
    ]:
        client._session.post.reset_mock()
        method()
        args, _ = client._session.post.call_args
        assert args[0] == f'http://testhost:1234{path}'


def test_next_with_uri():
    client = _make_client()
    client._session.post.return_value = _ok_response()
    client.next('spotify:track:X')
    args, kwargs = client._session.post.call_args
    assert args[0] == 'http://testhost:1234/player/next'
    assert kwargs['json'] == {'uri': 'spotify:track:X'}


def test_status_returns_json():
    client = _make_client()
    client._session.get.return_value = _ok_response({'paused': True})
    assert client.status() == {'paused': True}
    args, _ = client._session.get.call_args
    assert args[0] == 'http://testhost:1234/status'


def test_request_error_raises_golibrespot_error():
    client = _make_client()
    client._session.post.side_effect = requests.ConnectionError('boom')
    with pytest.raises(GoLibrespotError):
        client.pause()


def test_is_reachable_true_false():
    client = _make_client()
    client._session.get.return_value = _ok_response({'ok': True})
    assert client.is_reachable() is True

    client._session.get.side_effect = requests.ConnectionError('down')
    assert client.is_reachable() is False
