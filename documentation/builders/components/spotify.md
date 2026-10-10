# Spotify

The Jukebox can play Spotify tracks, albums and playlists from a card swipe or the Web App,
alongside the local music library. Playback is handled by
[go-librespot](https://github.com/devgianlu/go-librespot), controlled through its local REST API.
Browsing your playlists and albums and searching the Spotify catalog in the Web App use the
Spotify Web API.

Spotify is an **optional** player backend. The local music library (MPD) keeps working whether or
not Spotify is installed, and stays the default for existing cards.

## Prerequisites

* A Spotify **Premium** account. Spotify no longer allows playback without Premium, and
  username/password login no longer exists.
* Optional, for library browsing and search: a **Spotify Developer app** (free). See
  [Create a Spotify Developer app](#create-a-spotify-developer-app) below.
* Your Pi and the phone/computer you log in from need to be on the **same network**.

### Create a Spotify Developer app

1. Sign in at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) with
   your Premium account and create a new app.
2. Note the **Client ID**. The Jukebox uses the PKCE authorization flow, so no client secret is
   needed.
3. Add this exact **Redirect URI**:

   ```text
   http://127.0.0.1:8080/callback
   ```

   > [!IMPORTANT]
   > Use the IP address `127.0.0.1`, **not** `localhost` and **not** a hostname. Since Spotify's
   > OAuth migration (27 November 2025) only loopback IP redirect URIs are accepted.

4. Leave the app in **development mode** and add the Spotify account(s) that will use the box to
   the app's user **allowlist** (Dashboard → your app → User Management). In development mode only
   allowlisted accounts can authenticate.

## Install and enable Spotify

Run the setup script once. It detects your Pi's architecture, downloads a pinned go-librespot
release, writes its configuration, installs it as a systemd user service, installs the Python
requirements and enables the Spotify backend in the Jukebox configuration (`spotify.enable`).
It offers to connect the Spotify Web API right away; you can also do that later in the Web App.

```bash
cd ~/RPi-Jukebox-RFID/installation/components
./setup_spotify.sh
```

The script is idempotent - you can re-run it later (for example to update go-librespot). It will
not overwrite an existing go-librespot configuration or your stored login. If the Jukebox service
is running, the script stops it while updating the configuration and starts it again afterwards.

Audio is routed through PipeWire, so Spotify plays out of the **same speakers** and respects the
**same volume control** as your local library. See [Audio Output](../audio.md).

## Complete the one-time login

go-librespot advertises the box on your network as a Spotify Connect device (default name
`Phoniebox`). To log in:

1. Open the Spotify app on your phone or computer, signed in to your Premium account, on the
   same network as the Pi.
2. Start playing any track, open the **Connect to a device** menu, and select **Phoniebox**.
3. Audio switches to the Phoniebox. Your login is stored and reused after every reboot - you only
   do this once.

You can keep using Spotify Connect this way afterwards: when playback is started on the box from
a Spotify app, the Jukebox stops local playback and shows the Spotify track in the Web App.

Verify the backend is running:

```bash
# REST API should return playback status as JSON
curl http://localhost:3678/status

# Service status and logs
systemctl --user status go-librespot.service
journalctl --user-unit go-librespot.service -f
```

### Connect the Web API (library and search)

Open the Web App **Settings**. The **Spotify** card shows whether go-librespot and the Web API are
connected.

1. Enter the **Client ID** of your Developer app and save it.
2. Select **Connect Spotify** and approve the access in the page that opens.
3. Spotify redirects to a page starting with `http://127.0.0.1:8080/callback`, which usually fails
   to load on your phone or computer. Copy its full address, paste it into the Web App and select
   **Complete connection**.

The access token is stored and refreshed automatically.

## Link a card to Spotify content

Spotify content is assigned to cards like local music:

* **From the library:** in the Web App library, open the **Spotify** source and select one of your
  playlists or saved albums. Assign it to a card, or assign a single track from its track list.
* **By search:** in the card editor, choose **Play music** and use **Search Spotify** to find any
  track, album or playlist in the catalog.

Cards store the Spotify URI together with the provider `spotify`, for example in
`shared/settings/cards.yaml`:

```yaml
'0001234567':
  alias: play_album
  args: [Daft Punk, Discovery, 'spotify:album:2noRn2Aes5aoNVsU6iWThc', spotify]
'0001234568':
  alias: play_single
  args: ['spotify:track:4uLU6hMCjMI75M1A2tKUQC', spotify]
```

Share links such as `https://open.spotify.com/album/...` are accepted as well.

Cards registered with the `play_spotify` alias of earlier versions of this integration are
converted to `play_single` cards when you run `setup_spotify.sh`.

All player controls work the same for Spotify and local music: the Web App player, GPIO buttons,
volume, the stop-player and sleep timers, and the idle shutdown, which treats Spotify playback as
activity.

> [!NOTE]
> Like local album and song cards, Spotify cards always start playback from the beginning.
> The second-swipe actions currently only apply to `play_card` folder cards.

## Troubleshooting

* **"Premium required" / playback does not start.** Spotify playback requires Premium. Confirm the
  account selected during login is the Premium account.
* **Only one thing plays at a time.** The box has a single audio output. Starting Spotify stops
  local playback and vice versa - this is expected.
* **The Spotify library is empty / search returns nothing.** Check the Web API status in the
  settings. Confirm the Client ID, that the redirect URI in the Developer app is exactly
  `http://127.0.0.1:8080/callback` (IP, not `localhost`), and that the account is on the app's
  allowlist.
* **A playlist shows no tracks.** For apps in development mode, Spotify only returns the contents
  of playlists you own or collaborate on. Other playlists can still be played and assigned to cards.
* **The Web API needs to be connected again after an update.** The Jukebox requests read access to
  your playlists and saved albums. A token from an earlier version without these permissions is not
  used, so connect again in the settings.
* **Spotify stops when you log out of SSH.** The service runs as a user service. Enable lingering so
  it keeps running: `sudo loginctl enable-linger $USER`.
* **Device does not appear in the Spotify app.** Make sure the Pi and your phone/computer are on the
  same network, then check `journalctl --user-unit go-librespot.service -f`.

## See also

* [Concepts](../concepts.md)
* [Audio Output](../audio.md)
* [Card Database](../card-database.md)
* Developer notes: [Spotify backend](../../developers/spotify.md),
  [Player Backends](../../developers/player-backends.md)
