# AGENTS.md

Guidance for AI coding agents working in the **RPi-Jukebox-RFID Version 3** (aka *future3*) repository.
This is a complete rewrite of the Phoniebox jukebox: a Raspberry Pi RFID-triggered music box.
Read this before making changes — it captures architecture, conventions, and workflows that are
not obvious from any single file.

## What this project is

A music jukebox that plays audio when RFID cards/tags are swiped. It runs on Raspberry Pi OS but
the core is portable enough to develop on Linux/macOS/WSL and in Docker. It has two main parts:

- **Jukebox Core** — a long-running Python daemon (`src/jukebox`) that owns all logic and hardware.
- **Web App** — a React single-page app (`src/webapp`) that controls the box from a browser.

Actual audio playback is delegated to **MPD (Music Player Daemon)**; audio routing goes through
**PulseAudio**. The Jukebox does not decode audio itself.

## Architecture: three core concepts

The whole system hangs on three ideas. Understand these and the codebase makes sense.

1. **Plugin interface** (`src/jukebox/jukebox/plugs.py`)
   - Components in `src/jukebox/components/*` are Python packages loaded dynamically at startup,
     driven by the `modules:` section of the config (`resources/default-settings/jukebox.default.yaml`).
   - Functions/classes are exposed to the outside world by decorating them with
     `@plugs.register` (functions) or `@plugs.tag` (methods on a registered class instance).
   - A package is registered under a *name* that may differ from its Python module name — this is how
     a feature (e.g. `player`) can be backed by a swappable implementation (e.g. `playermpd`).
   - Failing plugins are **ignored at load time** so the box still boots. If functionality is
     missing, check the logs for load errors first.

2. **RPC server** (`src/jukebox/jukebox/rpc/`, ZMQ on port **5556**)
   - The *only* way to trigger actions in the core. The Web App, the CLI tool, RFID card swipes,
     and GPIO buttons all go through the same RPC path — calling registered plugin functions.
   - When adding user-facing actions, you expose them as plugin calls; you do not add ad-hoc APIs.

3. **Publishing message queue** (`src/jukebox/jukebox/publishing/`, ZMQ on port **5557**)
   - Complementary to RPC: the core *publishes* state and state changes (volume, player status,
     card IDs, plugin load results, etc.). The Web App subscribes to these topics
     (see `src/webapp/src/config.js` `SUBSCRIPTIONS`).

Both ZMQ channels run over **WebSockets**, which is why on the Pi `pyzmq` must be compiled from
source (stock packages lack WebSocket support). On a regular machine, `pip install pyzmq` is fine.

Entry point: `src/jukebox/run_jukebox.py` → `jukebox/daemon.py` (`JukeBox` class) loads plugins,
starts the RPC server, and handles graceful shutdown via signal handlers.

## Repository layout

```text
src/jukebox/                Jukebox Core (Python daemon)
  run_jukebox.py            Main entry point (run via ../../run_jukebox.sh)
  run_*.py                  Other core apps (rpc tool, audio config, rfid register, sniffer)
  jukebox/                  Core library: plugs, daemon, cfghandler, rpc/, publishing/, utils
  components/               Pluggable feature packages (player, rfid, volume, gpio, mqtt, timers, ...)
  misc/                     Logging, colors, helpers
src/webapp/                 React Web App (Create React App, react-scripts 5)
  src/                      components/, context/, sockets/, commands/, config.js
src/cli_client/             Command-line client
documentation/              All docs (builders/ = users, developers/ = contributors)
installation/               Install scripts and routines for Raspberry Pi OS
resources/default-settings/ Default YAML config + example configs (the source of truth for config shape)
shared/                     Runtime data (settings, audio, artifacts) — mostly gitignored
test/                       pytest suite (currently sparse: cfghandler, evdev, gpioz)
tools/                      Dev helper scripts (run_rpc_tool.sh, run_publicity_sniffer.sh)
ci/, docker/                CI helpers and Docker dev environment
```

## Environment & commands

The core targets **Python 3.9+** (minimum is 3.9; CI tests 3.9–3.13). All Python work happens
inside a virtualenv at the project root `.venv`. The wrapper scripts (`run_*.sh`) activate it
automatically and fix the working directory — **prefer them over calling tools directly.**

> Note: the `run_*.sh` scripts are bash and assume a Linux/macOS/WSL/Docker environment with a
> `.venv` present. On a bare Windows host they won't run as-is; use WSL or Docker for development
> (see `documentation/developers/development-environment.md` and `docker.md`).

```bash
# Run the core daemon (from repo root)
./run_jukebox.sh                 # add -v / -vv / -vvv for more logging, -h for help

# Lint Python — REQUIRED before any PR touching .py files
./run_flake8.sh

# Run the Python tests
./run_pytest.sh

# Lint Markdown (docs changes)
./run_markdownlint.sh

# Web App (in src/webapp)
npm install
npm start                        # dev server
npm run build                    # production build
npm test                         # react-scripts test
```

CI (`.github/workflows/pythonpackage_future3.yml`) runs `run_pytest.sh` with coverage **and**
`run_flake8.sh` across Python 3.9–3.13. Lint or test failures fail the build, so run both locally.

## Coding conventions

### Python

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/). Enforced by flake8 (`.flake8`):
  **max line length 127**, **max complexity 12**. A few continuation-line/binary-operator rules are
  ignored — see `.flake8` for the exact list. `__init__.py` may have unused imports (F401 ignored).
- Write docstrings. Module docstrings double as API docs (see `components/volume/__init__.py` for
  the house style: Features / Publishes / Integration sections). Docs are generated via pydoc-markdown.

### Files & folder names

This is the #1 difference from Version 2 — follow it strictly:

- all **lower case**
- separate words with **underscores `_`**, never dashes (dashes break Python module imports)
- descriptive, general → specific (e.g. `dot_matrix_module_MAX7219`); product IDs kept verbatim and last
- Directories named `scratch*` are gitignored and flake8-excluded — use them for local throwaway work.

### Web App

React 17 + MUI 5 + Emotion, i18next for translations, ZMQ over WebSocket via `jszmq`.
ESLint config is `react-app` (CRA defaults).

## Git & contribution workflow

- Default working branch is **`future3/develop`** — base topic branches and PRs on it.
  Only touch `future3/main` if a fix genuinely must land there. Version 2 lives on other branches.
- Make atomic commits. Check `git diff --check` for stray whitespace.
- Trivial/non-issue commits may be prefixed `(docs)`, `(maint)`, or `(packaging)`.
- Issues/PRs for v3 must carry the `future3` label.
- Before submitting: run `./run_flake8.sh` (and `./run_pytest.sh`) and fix all findings.
- Optional git hooks live in `.githooks/` (`cp .githooks/pre-commit .git/hooks/.`).

## Working effectively in this repo

- **Adding a feature to the core?** It almost always belongs in `src/jukebox/components/` as a
  plugin package, with public actions decorated via `@plugs.register`/`@plugs.tag`, and wired into
  the `modules:` config. Look at an existing component (`volume`, `timers`, `playermpd`) first.
- **Adding hardware support (RFID/GPIO)?** RFID readers follow a template:
  `src/jukebox/components/rfid/hardware/template_new_reader/` and the docs under
  `documentation/developers/rfid/`. Each reader is a self-contained subpackage with its own
  `requirements.txt`.
- **Changing config?** `resources/default-settings/jukebox.default.yaml` is the canonical shape;
  config is read via `jukebox/cfghandler.py` (ruamel.yaml). The live config is `shared/settings/jukebox.yaml`.
- **Adding a user action to the Web App?** Trace it through: a registered core plugin function
  (RPC) plus a subscription/command in `src/webapp/src/` (`config.js`, `commands/`, `sockets/`).
- **Tests are sparse.** Add pytest tests under `test/` when you add testable logic; mirror the
  existing structure (`test/cfghandler/`, `test/evdev/`, `test/gpioz/`). `conftest.py` puts
  `src/jukebox` on `sys.path`; `pytest.ini` sets `testpaths = test`.
- **Debugging a running box?** Use `tools/run_rpc_tool.sh` (interactive RPC client, tab-completion)
  and `tools/run_publicity_sniffer.sh` (prints all published messages).

## Documentation

Docs are split by audience: `documentation/builders/` (users/installers) and
`documentation/developers/` (contributors). Start at `documentation/README.md`. Key developer reads:
`developers/coreapps.md`, `developers/python.md`, `builders/concepts.md`, `builders/rpc-commands.md`.
Markdown is linted (`.markdownlint-cli2.yaml`) — run `./run_markdownlint.sh` for doc changes.
