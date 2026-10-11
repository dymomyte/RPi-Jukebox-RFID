# Spotify Backend

Spotify playback is a [player backend](./player-backends.md) registered with the player
coordinator as `spotify`. It follows the backend contract, so cards, the Web App, timers, GPIO
buttons and all other components keep talking to `player.ctrl` and need no Spotify-specific code.
For end-user setup see the [builder guide](../builders/components/spotify.md).

## Overview

```text
RFID swipe / Web App ──► player.ctrl.play_album(..., content_uri='spotify:album:…', provider='spotify')
                               │
                               ▼  PlayerCoordinator: stops the active backend, selects 'spotify'
                         SpotifyBackend ──► go-librespot REST API (playback)
                               │        └─► Spotify Web API via spotipy (library, cover art)
                               ▼
              publishes 'playerstatus' (provider='spotify') while active
```

The code lives in `src/jukebox/components/player/`:

* `backends/spotify/__init__.py`: `SpotifyBackend` and the status mapping
* `backends/spotify/go_librespot_client.py`: REST client for go-librespot
* `backends/spotify/web_api.py`: Spotify Web API wrapper (spotipy, Authorization Code + PKCE)
* `backends/spotify/uri_utils.py`: normalizes share links to `spotify:<type>:<id>` URIs and
  accepts the Liked Songs collection URI `spotify:user:<user id>:collection`. Audiobook and chapter
  references map to show and episode URIs: Spotify serves audiobooks as shows with the same id.
* `backends/spotify/resume.py`: resume positions of podcasts, audiobooks and episodes
* `spotify_plugin.py`: registers the backend when `spotify.enable` is set, plus the
  `player.spotify` account plugin

## Registration

Both player entry points (`player.plugin` and the `playermpd` compatibility plugin) call
`register_spotify_backend()` after creating the coordinator with MPD. MPD therefore stays the
default backend, so legacy cards and calls without `provider` are unaffected. Registration is
skipped unless `spotify.enable` is true, and errors are logged instead of raised, so a broken
Spotify setup cannot keep MPD from loading.

## Backend Contract

| Contract | Spotify implementation |
| --- | --- |
| `play_single(song_url)` | Plays the Spotify URI (normally a track); episodes resume |
| `play_album(albumartist, album, content_uri)` | Plays the album, playlist, Liked Songs, podcast or audiobook `content_uri`; shows resume; raises without it |
| Transport, `seek(seconds)` | go-librespot; seek is converted to milliseconds in the backend |
| `shuffle`, `repeat` | Same options and toggle cycle as MPD, mapped to shuffle/repeat context/track |
| `playerstatus()` | MPD-shaped dict: `state`, `songid`, `file`, `title`, `artist`, `album`, `elapsed`/`duration` in seconds, `random`/`repeat`/`single`, `cover_url`, `provider` |
| `set_active(active)` | Status is polled continuously but published only while active |
| `library_source()` | Source `spotify` with `playlists`, `albums`, `podcasts` and `audiobooks` views (`kind: items`) and a `songs` view (`kind: songs`) |
| `list_library_items(content_types)` | The user's playlists, led by Liked Songs, saved albums, podcasts and audiobooks; playlists carry `tracks_available` |
| `list_library_songs()` | The user's Liked Songs as song entries |
| `list_songs_by_artist_and_album(..., content_uri)`, `get_song_by_url` | Track and episode listings and lookup through the Web API |
| `get_album_coverart`, `get_single_coverart` | Remote cover URLs from the Web API |

Methods without a Spotify equivalent (folder playback, `playlistinfo`, `queue_load`, ...) are not
implemented; the coordinator raises `NotImplementedError` for them while Spotify is active.
Folder playback always routes to the default backend.

`stop()` never raises, because the coordinator stops the active backend before switching to
another one, which must work even if go-librespot is down. It leaves a paused player paused:
go-librespot 0.7.4 crashes when `/player/stop` is called while paused.

## Resume

Shows (podcasts and audiobooks) and single episodes resume where they stopped. The position is
kept on the box, keyed by the played content URI, in the file configured as `spotify.resume_file`
(`shared/settings/spotify_resume.json`):

* The status poll records the current episode and position while such content plays. It skips
  status read before a load finished (`_load_generation`), so the previous content's position is
  never stored for the new one.
* The file is written atomically: at most every 30 seconds while playing, and at once on pause,
  stop, content or backend switches and shutdown. The 200 most recently played entries are kept.
* Playing saved content loads it paused at the saved episode (`skip_to_uri`), seeks, then resumes,
  so the start of the episode is not heard. go-librespot's `/player/play` ignores a start position.
* When playback stops within 10 seconds of the end of an episode, the entry is removed, so content
  heard to the end starts over. `replay` also starts over.
* Spotify Connect playback from another device stops the tracking.

Spotify's own resume points (`resume_point`) would need the `user-read-playback-position` scope and
go-librespot to report progress, so they are not used.

## Spotify Connect

go-librespot is also a Spotify Connect device, so playback can be started from any Spotify app.
The status poll detects playback that starts while the backend is inactive. The coordinator
activates a backend before it loads content, so such playback can only come from a Spotify app.
(go-librespot 0.7.4 does not report the controlling device in `play_origin_device_id`.) The poll
then selects the backend through the coordinator, which stops MPD. Only the transition into playing triggers this, so a poll that
completes after the coordinator switched away from a playing Spotify backend does not switch back.

## Spotify Account Plugin

Web API authorization and catalog search are not part of the player contract. They are registered
as the plugin `player.spotify`:

* `auth_status()`, `set_client_id(client_id)`, `start_auth()`, `complete_auth(code_or_url)`
* `search(query, types, limit)`: catalog search. The Web App card editor turns results into
  `play_album`/`play_single` card actions with `provider='spotify'`. The library search of the
  Spotify source shows them as songs, albums and playlists next to the matching saved items.

The Web App shows the Spotify settings and the card editor search only if
`player.ctrl.list_backends()` contains `spotify`.

## Pub/Sub Topics

* `playerstatus`: shared player status, published while Spotify is the active backend
* `spotify.auth_status`: Web API authorization and go-librespot connection state

## Configuration

Non-secret settings live in the `spotify:` block of `jukebox.yaml` (enable flag, go-librespot
host/port, poll interval, resume file, Web API redirect port and token cache file). The Web API client id is
kept in `shared/settings/spotify.yaml`, loaded through its own `cfghandler` handler like the card
database. PKCE needs no client secret. The token cache is
`shared/settings/spotify-token.json`.

## Spotify Web API Constraints

Development Mode apps are subject to Spotify's February 2026 restrictions:

* Playlist contents come from `/playlists/{id}/items` (spotipy >= 2.26) and are only returned for
  playlists the user owns or collaborates on. Entries carry the track as `item` (formerly `track`);
  both are accepted. For other playlists Spotify answers `403`, which the backend turns into an
  empty track listing. Playlist library items and search results carry `tracks_available`, so the
  Web App can explain the missing tracks and still offer to play the playlist or assign it.
* Search returns at most 10 results per type. Searches pass `market=from_token`, without which
  Spotify returns no audiobooks.
* The saved shows (`/me/shows`) include the saved audiobooks, so the podcast listing leaves out
  the ids listed by `/me/audiobooks` (which spotipy has no method for). Show and audiobook objects
  carry no publisher.
* `/shows/{id}` lists an audiobook's chapters as episodes, so podcasts and audiobooks share one
  listing.
* Batch lookups are gone; the backend only uses single-item endpoints.

Playlist, album and track listings are cached for five minutes (`LISTING_TTL`), cover and
metadata lookups per URI for the lifetime of the process.

## Known Limitations

* The coordinator holds its lock during catalog calls (`list_library_items`, track listings,
  cover lookups). Uncached Spotify listings take several Web API requests, during which playback
  commands such as card swipes wait. The listing cache keeps this to the first load. Cover lookups
  are cached per URI for the lifetime of the process, so the first card list after a restart
  makes one request per Spotify card. Releasing the lock for read-only catalog calls would be a
  coordinator change.
* `play_card` routes to the default backend only, so second-swipe actions are not available for
  Spotify cards. Supporting them needs a provider-aware `play_card` in the coordinator.

## go-librespot REST API

go-librespot is pinned and installed by `installation/components/setup_spotify.sh`. It runs as a
systemd **user** service that outputs to ALSA's default device, which pipewire-alsa routes into the
same PipeWire session as the rest of the Jukebox. Endpoints used by the backend:

| Action | Method / path | Body |
| --- | --- | --- |
| Load and play a URI | `POST /player/play` | `{ "uri": "...", "skip_to_uri": "...", "paused": false }` |
| Resume / pause / toggle / stop | `POST /player/resume`, `/player/pause`, `/player/playpause`, `/player/stop` | - |
| Next / previous | `POST /player/next`, `/player/prev` | optional `{ "uri": "..." }` for next |
| Seek | `POST /player/seek` | `{ "position": <ms>, "relative": false }` |
| Volume | `GET` / `POST /player/volume` | `{ "volume": <n>, "relative": false }` |
| Shuffle | `POST /player/shuffle_context` | `{ "shuffle_context": true }` |
| Repeat | `POST /player/repeat_context`, `/player/repeat_track` | `{ "repeat_context": true }`, `{ "repeat_track": true }` |
| Status | `GET /status` | - (`204` without an active session) |

## See also

* [Player Backends](./player-backends.md)
* [Jukebox Apps](./coreapps.md)
* [Spotify builder guide](../builders/components/spotify.md)
