import sys
import os
# In case this is run locally
sys.path.append(os.path.abspath('../../src/jukebox'))

import components.spotify as spotify  # noqa: E402


def test_resolve_path_anchors_at_src_jukebox():
    # The credentials/token paths use ../../shared/... which, per project
    # convention (run_jukebox.py), is relative to src/jukebox -- NOT to this
    # component's own directory. Regression for paths landing in
    # src/jukebox/shared instead of the repo-root shared/.
    resolved = spotify._resolve_path('../../shared/settings/spotify.yaml').replace('\\', '/')
    assert resolved.endswith('/shared/settings/spotify.yaml')
    assert '/src/jukebox/shared/' not in resolved
    repo_root = resolved[:resolved.index('/shared/settings/spotify.yaml')]
    # The resolved repo root must be the tree that contains src/jukebox
    assert os.path.isdir(os.path.join(repo_root, 'src', 'jukebox'))


def test_resolve_path_passthrough_absolute():
    abs_path = os.path.abspath(os.sep + os.path.join('tmp', 'spotify.yaml'))
    assert spotify._resolve_path(abs_path) == abs_path


def test_auth_status_registered_at_package_level():
    # Registered RPC functions must live in the package __init__ (the plugs
    # loader only enlists functions whose __module__ is the package). Regression
    # for initialize() referencing spotify_web_api.auth_status (the helper
    # module), which has no such attribute.
    assert callable(spotify.auth_status)
    result = spotify.auth_status()
    assert {'web_api_connected', 'go_librespot_connected'} <= set(result)
