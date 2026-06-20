# Spotify backend

This note describes the architecture of the optional Spotify playback backend. For end-user setup
see the [builder guide](../builders/components/spotify.md).

## Overview

Spotify support is added as a **sibling player package alongside MPD**, not as a refactor of the
existing player. The local-file player (`playermpd`) is untouched. A card swipe that should play
Spotify is dispatched through the same [RPC](../builders/concepts.md) path as any other card, only
the target package and alias differ.

```text
RFID swipe ──► reader dispatch ──► plugs.call('spotify', 'ctrl', 'play_spotify', args=[uri])
                                          │
   card YAML: {alias: play_spotify,       ▼
               args: ['spotify:track:...']}   components/spotify  (module 'spotify', plugin 'ctrl')
                                          │   • REST client -> go-librespot http://localhost:3678
   webapp search ──► plugs.call('spotify', 'search', ...) ──► Spotify Web API (spotipy)
                                          │
   status: poll go-librespot GET /status ──► publish 'playerstatus' (+ 'spotify.status')
```

## Components

The `spotify` package lives in `src/jukebox/components/spotify/` and is registered as the named
module `spotify` in `jukebox.yaml` (`modules.named.spotify: spotify`).

* **Playback control** is exposed as the plugin `spotify.ctrl.*`. It mirrors the player contract so
  cards and the Web App behave consistently: `play_spotify(uri)` / `play_uri(uri)`, `play`, `pause`,
  `toggle`, `next`, `prev`, `stop`, `seek`, `playerstatus`. These call go-librespot's local REST API
  (see [go-librespot endpoints](#go-librespot-rest-api)).
* **Search / metadata** are exposed as module-level functions `spotify.search`, `spotify.get_metadata`,
  `spotify.auth_status`, etc., backed by the Spotify Web API via the `spotipy` library
  (Authorization Code + PKCE). This is an optional Python dependency declared in
  `src/jukebox/components/spotify/requirements.txt` and installed by `setup_spotify.sh` (and in CI).
* **Status publishing** mirrors the `playermpd` poll pattern: a timer polls go-librespot `GET /status`,
  maps it to the `playerstatus` schema, and publishes it, plus a richer `spotify.status` topic.

If go-librespot is unreachable or Spotify is not configured, the component logs a clear "Spotify
disabled" warning and registers nothing functional rather than raising - consistent with the
project's "failing packages are ignored at start-up, check the logs" philosophy (see
[Concepts](../builders/concepts.md)).

## Card alias

The card alias `play_spotify` is defined in `src/jukebox/components/rpc_command_alias.py` and maps to
`{package: 'spotify', plugin: 'ctrl', method: 'play_spotify'}`. Cards reference it with the target
URI as an argument:

```yaml
alias: play_spotify
args:
  - 'spotify:track:...'
```

Share links of the form `https://open.spotify.com/<type>/<id>` are normalised to
`spotify:<type>:<id>` before being passed to go-librespot.

## MPD <-> Spotify mutual exclusion

The box has a single audio output and a single Spotify connection, so only one backend can play at a
time. Arbitration uses `plugs.call_ignore_errors`, which no-ops cleanly if the other backend is not
loaded:

* Starting Spotify playback calls `plugs.call_ignore_errors('player', 'ctrl', 'stop')`.
* Starting local (MPD) playback calls `plugs.call_ignore_errors('spotify', 'ctrl', 'stop')`.

This keeps `playermpd` decoupled from Spotify - it knows nothing about the Spotify package beyond the
ignore-errors stop call.

## Pub/Sub topics

* `playerstatus` - shared player status, published while Spotify is the active backend so the Web App
  and other subscribers see a consistent shape regardless of backend.
* `spotify.status` - richer Spotify-specific state.
* `spotify.auth_status` - Web API authentication state (connected / needs re-auth).

## Configuration

Non-secret configuration lives under a `spotify:` block in `jukebox.yaml` (go-librespot host/port,
Web API enable flag, poll interval, redirect port). Secrets - the Web API `client_id` /
`client_secret` and the cached token - are kept out of the main config in
`shared/settings/spotify.yaml`, loaded via a second `cfghandler` handler (the same pattern used for
the cards database).

## go-librespot REST API

go-librespot is pinned and installed by `installation/components/setup_spotify.sh` (currently
**v0.7.4**). It runs as a systemd **user** service so it shares the user's PulseAudio session and the
same sink the Jukebox configures (`run_configure_audio.py`). The REST API listens on
`http://localhost:3678` by default. Endpoints used by `spotify.ctrl`:

| Action | Method / path | Body |
|--------|---------------|------|
| Load and play a URI | `POST /player/play` | `{ "uri": "...", "skip_to_uri": "...", "paused": false }` |
| Resume | `POST /player/resume` | - |
| Pause | `POST /player/pause` | - |
| Toggle | `POST /player/playpause` | - |
| Next | `POST /player/next` | optional `{ "uri": "..." }` |
| Previous | `POST /player/prev` | - |
| Seek | `POST /player/seek` | `{ "position": <ms>, "relative": false }` |
| Volume | `POST /player/volume` | `{ "volume": <n>, "relative": false }` |
| Status | `GET /status` | - |

## See also

* [Jukebox Apps](./coreapps.md)
* [Concepts](../builders/concepts.md)
* [Spotify builder guide](../builders/components/spotify.md)
