# AGENTS.md

Guidance for AI coding agents working in the **RPi-Jukebox-RFID Version 3** (aka *future3*) repository.
This is a complete rewrite of the Phoniebox jukebox: a Raspberry Pi RFID-triggered music box.
Read this before making changes — it captures architecture, conventions, and workflows that are
not obvious from any single file.

## What this project is

A music jukebox that plays audio when RFID cards/tags are swiped. It runs on Raspberry Pi OS (Trixie)
but the core is portable enough to develop on Linux/macOS/WSL and in Docker. It has two main parts:

- **Jukebox Core** — a long-running Python daemon (`src/jukebox`) that owns all logic and hardware.
- **Web App** — a React single-page app (`src/webapp`) that controls the box from a browser.

Actual audio playback is delegated to player backends: **MPD (Music Player Daemon)** for the local
library and, optionally, **go-librespot** for Spotify. Audio routing goes through **PipeWire**.
The Jukebox does not decode audio itself.

## Architecture: core concepts

1. **Plugin interface** (`src/jukebox/jukebox/plugs.py`)
   - Components in `src/jukebox/components/*` are Python packages loaded dynamically at startup,
     driven by the `modules:` section of the config (`resources/default-settings/jukebox.default.yaml`).
   - Functions/classes are exposed to the outside world by decorating them with
     `@plugs.register` (functions) or `@plugs.tag` (methods on a registered class instance).
   - A package is registered under a *name* that may differ from its Python module name — e.g. the
     `player` package is loaded from `player.plugin`.
   - Failing plugins are **ignored at load time** so the box still boots. If functionality is
     missing, check the logs for load errors first.

2. **RPC** (`src/jukebox/jukebox/rpc/`)
   - The *only* way to trigger actions in the core. The Web App, the CLI tool, RFID card swipes,
     and GPIO buttons all go through the same RPC path — calling registered plugin functions.
   - The Web App uses `POST /api/v1/rpc` on the HTTP API (port **5556**, behind nginx). Native
     ZeroMQ clients use TCP port **5555**.
   - When adding user-facing actions, you expose them as plugin calls; you do not add ad-hoc APIs.

3. **Publishing** (`src/jukebox/jukebox/publishing/`)
   - Complementary to RPC: the core *publishes* state and state changes (volume, player status,
     card IDs, plugin load results, etc.). The Web App subscribes over the native WebSocket
     `WS /api/v1/events` (see `src/webapp/src/config.js` `SUBSCRIPTIONS`); native ZeroMQ
     subscribers use TCP port **5558**.

4. **Player coordinator** (`src/jukebox/components/player/`)
   - `player.ctrl` is a provider-neutral facade that routes calls to registered backends
     (`backends/mpd.py`, `backends/spotify/`). Content calls take an optional `provider`; calls
     without it go to the default backend (MPD). Switching backends stops the previous one.
   - Read `documentation/developers/player-backends.md` before touching playback. New content
     sources should be backends behind the coordinator, not sibling plugins.

Entry point: `src/jukebox/run_jukebox.py` → `jukebox/daemon.py` (`JukeBox` class) loads plugins,
starts the RPC server, and handles graceful shutdown via signal handlers.

## Repository layout

```text
src/jukebox/                Jukebox Core (Python daemon)
  run_jukebox.py            Main entry point (run via ../../run_jukebox.sh)
  run_*.py                  Other core apps (rpc tool, audio config, rfid/spotify registration, sniffer)
  jukebox/                  Core library: plugs, daemon, cfghandler, rpc/, publishing/, utils
  components/               Pluggable feature packages (player, rfid, volume, gpio, mqtt, timers, ...)
  misc/                     Logging, colors, helpers
src/webapp/                 React Web App (Vite, React 19, MUI 9)
  src/                      components/, context/, sockets/, commands/, config.js
  e2e/                      Playwright tests with a mocked backend
src/cli_client/             Command-line client
documentation/              All docs (builders/ = users, developers/ = contributors)
installation/               Install scripts, routines and optional components for Raspberry Pi OS
resources/default-settings/ Default YAML config + example configs (the source of truth for config shape)
shared/                     Runtime data (settings, audio, artifacts) — mostly gitignored
test/                       pytest suite, mirroring the component structure
tools/                      Dev helper scripts (run_rpc_tool.sh, run_publicity_sniffer.sh)
ci/, docker/                CI helpers and Docker dev environment
```

## Environment & commands

All Python work happens inside a virtualenv at the project root `.venv`. The wrapper scripts
(`run_*.sh`) activate it automatically and fix the working directory — **prefer them over calling
tools directly.** CI tests Python 3.11 and 3.13.

> Note: the `run_*.sh` scripts are bash and assume a Linux/macOS/WSL/Docker environment with a
> `.venv` present. Use WSL or Docker on Windows
> (see `documentation/developers/development-environment.md` and `docker.md`).

```bash
# Run the core daemon (from repo root)
./run_jukebox.sh                 # add -v / -vv / -vvv for more logging, -h for help

# Lint Python — REQUIRED before any PR touching .py files
./run_flake8.sh

# Run the Python tests
./run_pytest.sh

# Lint Markdown (docs changes; uses the Web App's node_modules)
./run_markdownlint.sh

# Web App (in src/webapp, Node.js 22)
npm ci
npm run dev                      # dev server on port 3000, proxies /api/ to localhost:5556
npm run lint
npm test                         # vitest
npm run test:e2e                 # playwright (npx playwright install chromium first)
npm run build                    # production build to src/webapp/build
```

CI (`.github/workflows/`) runs pytest with coverage and flake8, and lints, tests and builds the
Web App. Lint or test failures fail the build, so run them locally. Runtime devices install
prebuilt Web App bundles from CI and need no Node.js.

## Coding conventions

### Python

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/). Enforced by flake8 (`.flake8`):
  **max line length 127**, **max complexity 12**. A few continuation-line/binary-operator rules are
  ignored — see `.flake8` for the exact list. `__init__.py` may have unused imports (F401 ignored).
- Write docstrings. Module docstrings double as API docs (see `components/volume/__init__.py` for
  the house style: Features / Publishes / Integration sections). Docs are generated via pydoc-markdown.
- Optional component dependencies go into a `requirements.txt` next to the component and are added
  to the CI install step.

### Files & folder names

This is the #1 difference from Version 2 — follow it strictly:

- all **lower case**
- separate words with **underscores `_`**, never dashes (dashes break Python module imports)
- descriptive, general → specific (e.g. `dot_matrix_module_MAX7219`); product IDs kept verbatim and last
- Directories named `scratch*` are gitignored and flake8-excluded — use them for local throwaway work.

### Web App

React 19 + MUI 9 + Emotion, i18next for translations (`public/locales/{en,de}`), built with Vite.
Use the MUI v9 APIs (`Grid size`, `slotProps`). ESLint config is `eslint.config.js`.

## Git & contribution workflow

- Default working branch is **`future3/develop`** — base topic branches and PRs on it.
  Only touch `future3/main` if a fix genuinely must land there. Version 2 lives on other branches.
- Make atomic commits. Check `git diff --check` for stray whitespace.
- Trivial/non-issue commits may be prefixed `(docs)`, `(maint)`, or `(packaging)`.
- Issues/PRs for v3 must carry the `future3` label.
- Before submitting: run `./run_flake8.sh` and `./run_pytest.sh` and fix all findings.
- Optional git hooks live in `.githooks/` (`cp .githooks/pre-commit .git/hooks/.`).

## Working effectively in this repo

- **Adding a feature to the core?** It almost always belongs in `src/jukebox/components/` as a
  plugin package, with public actions decorated via `@plugs.register`/`@plugs.tag`, and wired into
  the `modules:` config. Look at an existing component (`volume`, `timers`) first.
- **Adding a music source?** Implement a player backend and register it with the coordinator
  (see `components/player/spotify_plugin.py` for an optional backend). Publish `playerstatus` in
  the shared shape, only while active, and store `provider` + a stable `content_uri` in cards.
- **Adding hardware support (RFID/GPIO)?** RFID readers follow a template:
  `src/jukebox/components/rfid/hardware/template_new_reader/` and the docs under
  `documentation/developers/rfid/`. Each reader is a self-contained subpackage with its own
  `requirements.txt`.
- **Changing config?** `resources/default-settings/jukebox.default.yaml` is the canonical shape;
  config is read via `jukebox/cfghandler.py` (ruamel.yaml). The live config is `shared/settings/jukebox.yaml`.
- **Adding a user action to the Web App?** Trace it through: a registered core plugin function
  (RPC) plus a command in `src/webapp/src/commands/` and, for state, a subscription in `config.js`.
- **Tests:** add pytest tests under `test/` mirroring the component structure. `conftest.py` puts
  `src/jukebox` on `sys.path`; `pytest.ini` sets `testpaths = test`. Web App unit tests live next
  to the code (`*.test.js[x]`), e2e tests in `src/webapp/e2e/`.
- **Debugging a running box?** Use `tools/run_rpc_tool.sh` (interactive RPC client, tab-completion)
  and `tools/run_publicity_sniffer.sh` (prints all published messages).

## Documentation

Docs are split by audience: `documentation/builders/` (users/installers) and
`documentation/developers/` (contributors). Start at `documentation/README.md`. Key developer reads:
`developers/coreapps.md`, `developers/python.md`, `developers/player-backends.md`,
`developers/webapp.md`, `builders/concepts.md`, `builders/rpc-commands.md`.
Markdown is linted (`.markdownlint-cli2.yaml`) — run `./run_markdownlint.sh` for doc changes.
