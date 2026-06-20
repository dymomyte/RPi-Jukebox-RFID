import sys
import os

# Ensure the jukebox source tree is importable (mirrors the repo-root conftest)
sys.path.append(os.path.abspath('src/jukebox'))
sys.path.append(os.path.abspath('../../src/jukebox'))

# The Spotify component uses @plugs.register / @plugs.initialize / @plugs.atexit
# decorators which, under the normal plugin loader, require the package to be
# registered via plugs.load(). When importing the package directly in unit
# tests we enable ALLOW_DIRECT_IMPORTS so these decorators become no-ops /
# self-register, exactly as the run_register_* CLI tools do.
import jukebox.plugs  # noqa: E402
jukebox.plugs.ALLOW_DIRECT_IMPORTS = True
