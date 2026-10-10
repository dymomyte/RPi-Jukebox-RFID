"""Player plugin entry point with MPD as the default backend and optional Spotify backend."""

import jukebox.plugs as plugs

from .mpd_plugin import initialize_mpd_player
from .spotify_plugin import register_spotify_backend


player_ctrl = None


@plugs.initialize
def initialize():
    global player_ctrl
    player_ctrl = initialize_mpd_player(__name__)
    register_spotify_backend(player_ctrl, __name__)


@plugs.atexit
def atexit(**ignored_kwargs):
    return player_ctrl.exit()
