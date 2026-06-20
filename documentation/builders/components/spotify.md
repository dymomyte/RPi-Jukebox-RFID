# Spotify

The Jukebox can play Spotify tracks, albums and playlists from a card swipe, alongside the
local music library. Playback is handled by [go-librespot](https://github.com/devgianlu/go-librespot),
controlled through its local REST API, while search and metadata for the Web App come from the
Spotify Web API.

Spotify is an **optional** component. The local-file player (MPD) keeps working whether or not
Spotify is installed.

## Prerequisites

* A Spotify **Premium** account. Spotify no longer allows playback without Premium, and
  username/password login no longer exists.
* A **Spotify Developer app** (free) to get API credentials for search and metadata. See
  [Create a Spotify Developer app](#create-a-spotify-developer-app) below.
* Your Pi and the phone/computer you log in from need to be on the **same network**.

### Create a Spotify Developer app

1. Sign in at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) with
   your Premium account and create a new app.
2. Note the **Client ID** and **Client Secret**.
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

## Install go-librespot

Run the setup script once. It detects your Pi's architecture, downloads a pinned go-librespot
release, writes its configuration, and installs it as a systemd user service.

```bash
cd ~/RPi-Jukebox-RFID/installation/components
./setup_spotify.sh
```

The script is idempotent - you can re-run it later (for example to update go-librespot). It will
not overwrite an existing configuration or your stored login.

Audio is routed through PulseAudio, so Spotify plays out of the **same speakers** and respects the
**same volume control** as your local library. See [Audio Output](../audio.md).

## Complete the one-time login

go-librespot advertises the box on your network as a Spotify Connect device (default name
`Phoniebox`). To log in:

1. Open the Spotify app on your phone or computer, signed in to your Premium account, on the
   same network as the Pi.
2. Start playing any track, open the **Connect to a device** menu, and select **Phoniebox**.
3. Audio switches to the Phoniebox. Your login is stored and reused after every reboot - you only
   do this once.

Verify the backend is running:

```bash
# REST API should return playback status as JSON
curl http://localhost:3678/status

# Service status and logs
systemctl --user status go-librespot.service
journalctl --user -u go-librespot.service -f
```

### Authorise the Web API (search)

To enable search and browsing in the Web App, enter the **Client ID** and **Client Secret** from
your Developer app in the Web App's Spotify settings, then follow the prompt to authorise. This is
a separate, one-time step from the Spotify Connect login above. The access token is stored and
refreshed automatically.

## Link a card to a Spotify track

1. In the Web App, open the **Spotify search** panel.
2. Search for a track, album or playlist and select a result.
3. Register the result to a card, just like you would for local content.

Swipe the card to play. As with local content, the configured second-swipe behaviour applies.

## Troubleshooting

* **"Premium required" / playback does not start.** Spotify playback requires Premium. Confirm the
  account selected during login is the Premium account, and that it is on the Developer app's
  allowlist.
* **Only one thing plays at a time.** The box has a single audio output and a single Spotify
  connection. Starting Spotify stops local playback and vice versa - you cannot play local files
  and Spotify simultaneously. This is expected.
* **Search returns nothing / authorisation fails.** Check the Client ID and Client Secret, and that
  the redirect URI in the Developer app is exactly `http://127.0.0.1:8080/callback` (IP, not
  `localhost`). In development mode the logged-in account must be on the app's allowlist.
* **Token expired / needs re-auth.** Tokens refresh automatically, but if the refresh token is
  revoked (for example after changing your Spotify password) re-run the Web API authorisation in
  the Web App settings.
* **Spotify stops when you log out of SSH.** The service runs as a user service. Enable lingering so
  it keeps running: `sudo loginctl enable-linger $USER`.
* **Device does not appear in the Spotify app.** Make sure the Pi and your phone/computer are on the
  same network, then check `journalctl --user -u go-librespot.service -f`.

## See also

* [Concepts](../concepts.md)
* [Audio Output](../audio.md)
* [Card Database](../card-database.md)
* Developer architecture note: [Spotify (developers)](../../developers/spotify.md)
