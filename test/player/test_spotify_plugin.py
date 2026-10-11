import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import jukebox.cfghandler
import jukebox.plugs as plugs
import jukebox.publishing as publishing

from components.player import spotify_plugin
from components.player.backends.spotify import SpotifyBackend
from components.player.coordinator import PlayerCoordinator


@pytest.fixture
def config(monkeypatch, tmp_path):
    cfg = jukebox.cfghandler.ConfigHandler('jukebox-test')
    cfg.config_dict({'spotify': {
        'enable': True,
        'credentials_file': str(tmp_path / 'spotify.yaml'),
        'web_api': {'token_cache_file': str(tmp_path / 'spotify-token.json')},
    }})
    monkeypatch.setattr(spotify_plugin, 'cfg', cfg)
    monkeypatch.setattr(spotify_plugin, 'cfg_credentials', jukebox.cfghandler.ConfigHandler('spotify-test'))
    return cfg


@pytest.fixture
def registered(monkeypatch, config):
    monkeypatch.setattr(publishing, 'get_publisher', Mock(return_value=Mock()))
    monkeypatch.setattr(SpotifyBackend, 'start', Mock())
    monkeypatch.setattr(plugs, 'register', Mock())
    monkeypatch.setattr(plugs, 'loaded_as', Mock(return_value='player'))
    return plugs.register


def mpd_backend():
    return SimpleNamespace(stop=Mock(), exit=Mock(), set_active=Mock(), play_album=Mock())


def test_resolve_path_anchors_at_src_jukebox():
    resolved = spotify_plugin.resolve_path('../../shared/settings/spotify.yaml')
    repo_root = resolved[:resolved.index(os.path.join(os.sep, 'shared', 'settings'))]
    assert os.path.isdir(os.path.join(repo_root, 'src', 'jukebox'))
    assert spotify_plugin.resolve_path('/tmp/spotify.yaml') == '/tmp/spotify.yaml'


def test_disabled_spotify_registers_nothing(config):
    config.setn('spotify', 'enable', value=False)
    coordinator = PlayerCoordinator()

    assert spotify_plugin.register_spotify_backend(coordinator, 'components.player.plugin') is None
    assert coordinator.list_backends() == []


def test_enabled_spotify_registers_backend_and_account(registered):
    coordinator = PlayerCoordinator()
    coordinator.register_backend('mpd', mpd_backend())

    backend = spotify_plugin.register_spotify_backend(coordinator, 'components.player.plugin')

    assert coordinator.list_backends() == ['mpd', 'spotify']
    assert coordinator.get_default_backend() == 'mpd'
    assert coordinator.get_active_backend() == 'mpd'
    backend.start.assert_called_once_with()
    account, = registered.call_args.args
    assert isinstance(account, spotify_plugin.SpotifyAccount)
    assert registered.call_args.kwargs == {'name': 'spotify', 'package': 'player'}


def test_registration_errors_do_not_propagate(registered, monkeypatch):
    monkeypatch.setattr(spotify_plugin, 'create_web_api', Mock(side_effect=RuntimeError('broken')))
    coordinator = PlayerCoordinator()
    coordinator.register_backend('mpd', mpd_backend())

    assert spotify_plugin.register_spotify_backend(coordinator, 'components.player.plugin') is None
    assert coordinator.list_backends() == ['mpd']


def test_spotify_cards_switch_backends_through_coordinator(registered):
    mpd = mpd_backend()
    coordinator = PlayerCoordinator()
    coordinator.register_backend('mpd', mpd)
    backend = spotify_plugin.register_spotify_backend(coordinator, 'components.player.plugin')
    backend.client = Mock()
    backend.client.status.return_value = {'stopped': False, 'paused': False}

    coordinator.play_album('Artist', 'Album', 'spotify:album:AID', 'spotify')

    mpd.stop.assert_called_once_with()
    mpd.set_active.assert_called_with(False)
    backend.client.load.assert_called_once_with('spotify:album:AID')
    assert coordinator.get_active_backend() == 'spotify'

    coordinator.stop()
    backend.client.stop.assert_called_once_with()

    coordinator.play_album('Artist', 'Local Album')

    assert backend.client.stop.call_count == 2
    mpd.play_album.assert_called_once_with('Artist', 'Local Album')
    assert coordinator.get_active_backend() == 'mpd'


def test_spotify_connect_playback_selects_backend(registered):
    mpd = mpd_backend()
    coordinator = PlayerCoordinator()
    coordinator.register_backend('mpd', mpd)
    backend = spotify_plugin.register_spotify_backend(coordinator, 'components.player.plugin')
    backend.client = Mock()
    # Spotify Connect playback, which go-librespot reports without play_origin_device_id
    backend.client.status.return_value = {'stopped': False, 'paused': False, 'play_origin_device_id': None}

    backend._status_poll()

    mpd.stop.assert_called_once_with()
    assert coordinator.get_active_backend() == 'spotify'


def test_client_id_round_trip(config):
    assert spotify_plugin.read_client_id() is None

    spotify_plugin.write_client_id('abc123')

    assert spotify_plugin.read_client_id() == 'abc123'


def test_account_set_client_id_rebuilds_web_api(registered, config):
    web_api = Mock(client_id='new', is_connected=Mock(return_value=False))
    account = spotify_plugin.SpotifyAccount(Mock(connected=True), web_api)

    status = account.set_client_id(' new ')

    web_api.set_client_id.assert_called_once_with('new')
    assert spotify_plugin.read_client_id() == 'new'
    assert status == {'client_id_configured': True, 'web_api_connected': False, 'go_librespot_connected': True}


def test_play_spotify_cards_are_migrated(tmp_path):
    cards = tmp_path / 'cards.yaml'
    cards.write_text(
        "'A':\n  alias: play_spotify\n  args: spotify:track:T\n"
        "'B':\n  alias: play_spotify\n  args: ['https://open.spotify.com/album/AID']\n"
        "'C':\n  alias: play_card\n  args: [folder]\n"
        "'D':\n  alias: play_spotify\n"
    )

    assert spotify_plugin.migrate_play_spotify_cards(str(cards)) == ['A', 'B']

    migrated = jukebox.cfghandler.ConfigHandler('cards-test')
    jukebox.cfghandler.load_yaml(migrated, str(cards))
    assert migrated['A'] == {'alias': 'play_single', 'args': ['spotify:track:T', 'spotify']}
    assert migrated['B'] == {'alias': 'play_single', 'args': ['https://open.spotify.com/album/AID', 'spotify']}
    assert migrated['C'] == {'alias': 'play_card', 'args': ['folder']}
    # Without a URI there is nothing to play, so the card is left for the user to fix
    assert migrated['D'] == {'alias': 'play_spotify'}
    assert spotify_plugin.migrate_play_spotify_cards(str(cards)) == []
    assert spotify_plugin.migrate_play_spotify_cards(str(tmp_path / 'missing.yaml')) == []
