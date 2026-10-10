from unittest import mock

import pytest
import requests

from components.player.backends.spotify.go_librespot_client import GoLibrespotClient, GoLibrespotError


def make_client():
    client = GoLibrespotClient(host='testhost', port=1234)
    client._session = mock.MagicMock()
    return client


def ok_response(json_body=None, status_code=200):
    response = mock.MagicMock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.json.return_value = json_body if json_body is not None else {}
    return response


def test_base_url():
    client = GoLibrespotClient(host='myhost', port=9999)
    assert client.base_url == 'http://myhost:9999'


def test_load_builds_play_request():
    client = make_client()
    client._session.post.return_value = ok_response()
    client.load('spotify:track:ID', play=True)
    args, kwargs = client._session.post.call_args
    assert args[0] == 'http://testhost:1234/player/play'
    assert kwargs['json'] == {'uri': 'spotify:track:ID', 'paused': False}


def test_load_paused_with_skip_to_uri():
    client = make_client()
    client._session.post.return_value = ok_response()
    client.load('spotify:album:AID', play=False, skip_to_uri='spotify:track:T')
    _, kwargs = client._session.post.call_args
    assert kwargs['json'] == {'uri': 'spotify:album:AID', 'paused': True, 'skip_to_uri': 'spotify:track:T'}


def test_seek_uses_position_field_in_milliseconds():
    client = make_client()
    client._session.post.return_value = ok_response()
    client.seek(42000)
    args, kwargs = client._session.post.call_args
    assert args[0] == 'http://testhost:1234/player/seek'
    assert kwargs['json'] == {'position': 42000, 'relative': False}


@pytest.mark.parametrize(('method', 'path'), [
    ('pause', '/player/pause'),
    ('resume', '/player/resume'),
    ('playpause', '/player/playpause'),
    ('prev', '/player/prev'),
    ('next', '/player/next'),
    ('stop', '/player/stop'),
])
def test_transport_endpoints(method, path):
    client = make_client()
    client._session.post.return_value = ok_response()
    getattr(client, method)()
    args, _ = client._session.post.call_args
    assert args[0] == f'http://testhost:1234{path}'


def test_shuffle_and_repeat_endpoints():
    client = make_client()
    client._session.post.return_value = ok_response()

    client.set_shuffle(True)
    client.set_repeat(context=False, track=True)

    assert client._session.post.call_args_list == [
        mock.call('http://testhost:1234/player/shuffle_context', json={'shuffle_context': True}, timeout=2.0),
        mock.call('http://testhost:1234/player/repeat_context', json={'repeat_context': False}, timeout=2.0),
        mock.call('http://testhost:1234/player/repeat_track', json={'repeat_track': True}, timeout=2.0),
    ]


def test_status_returns_json():
    client = make_client()
    client._session.get.return_value = ok_response({'paused': True})
    assert client.status() == {'paused': True}
    args, _ = client._session.get.call_args
    assert args[0] == 'http://testhost:1234/status'


def test_status_without_session_returns_none():
    client = make_client()
    response = ok_response(status_code=204)
    response.json.side_effect = ValueError('no body')
    client._session.get.return_value = response
    assert client.status() is None


def test_request_error_raises_golibrespot_error():
    client = make_client()
    client._session.post.side_effect = requests.ConnectionError('boom')
    with pytest.raises(GoLibrespotError):
        client.pause()
    client._session.get.side_effect = requests.ConnectionError('boom')
    with pytest.raises(GoLibrespotError):
        client.status()
