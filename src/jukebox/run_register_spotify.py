#!/usr/bin/env python
"""
Setup tool to register the Spotify player backend with the Jukebox.

Run this once on the box (``installation/components/setup_spotify.sh`` calls it) to:

1. Enable the Spotify backend (``spotify.enable``) in the Jukebox configuration.
2. Migrate cards of the former ``play_spotify`` alias to ``play_single`` cards
   with ``provider: spotify``.
3. Optionally connect the Spotify Web API, which the Web App uses to browse your
   playlists and albums and to search: store the Spotify app ``client_id`` and
   complete the one-time **Authorization Code + PKCE** login. The resulting token
   is cached and refreshed automatically.

The Web API connection can also be set up later from the Web App settings.

> [!NOTE]
> Requires a Spotify Developer app whose redirect URI is registered as
> ``http://127.0.0.1:<port>/callback`` (IP, not ``localhost``).
"""
import argparse
import logging
import os

import misc.inputminus as pyil
import jukebox.cfghandler
import jukebox.plugs
jukebox.plugs.ALLOW_DIRECT_IMPORTS = True
import components.hostif.linux as host  # noqa: E402
import components.player.spotify_plugin as spotify_plugin  # noqa: E402

# Create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logconsole = logging.StreamHandler()
logconsole.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)-8s: %(message)s',
                                          datefmt='%d.%m.%Y %H:%M:%S'))
logconsole.setLevel(logging.INFO)
logger.addHandler(logconsole)

cfg = jukebox.cfghandler.get_handler('jukebox')


def enable_backend(conffile: str):
    jukebox.cfghandler.load_yaml(cfg, conffile)
    cfg.setn('spotify', 'enable', value=True)
    jukebox.cfghandler.write_yaml(cfg, conffile, only_if_changed=True)
    print(f"Spotify backend enabled in '{conffile}'")


def migrate_cards():
    card_database = spotify_plugin.resolve_path(
        cfg.getn('rfid', 'card_database', default='../../shared/settings/cards.yaml'))
    migrated = spotify_plugin.migrate_play_spotify_cards(card_database)
    if migrated:
        print(f"Migrated {len(migrated)} 'play_spotify' card(s) to 'play_single': {', '.join(migrated)}")


def connect_web_api(client_id: str):
    if not client_id:
        client_id = input("Spotify app client id: ").strip()
    if not client_id:
        print("No client id given. Skipping the Web API setup.")
        return
    spotify_plugin.write_client_id(client_id)

    web_api = spotify_plugin.create_web_api()
    auth_url = web_api.start_auth().get('auth_url')
    if not auth_url:
        print("\nERROR: Could not build an authorization URL. Is 'spotipy' installed?")
        print("Install it with: pip install -r components/player/backends/spotify/requirements.txt")
        return

    print("\n" + "=" * 79)
    print("Open this URL in a browser on any device and approve the access:\n")
    print(f"  {auth_url}\n")
    print(f"Spotify then redirects to {web_api.redirect_uri}?code=...")
    print("That page may fail to load on your device. Copy its full address from the browser.")
    print("=" * 79 + "\n")
    redirect_url = input("Paste the redirect URL (or just the code): ").strip()

    if web_api.complete_auth(redirect_url).get('success'):
        print(f"\nSpotify Web API authorization successful. Token cached at '{web_api.cache_path}'")
    else:
        print("\nSpotify Web API authorization FAILED. Check the log output and try again,")
        print("or connect later from the Web App settings.")


def main():
    # The default config file relative to this files location and independent of working directory
    script_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    cfg_file_default = os.path.abspath(os.path.join(script_path, '../../shared/settings/jukebox.yaml'))

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conffile",
                        help=f"Jukebox configuration file [default: '{cfg_file_default}']",
                        metavar="FILE", default=cfg_file_default)
    parser.add_argument("--client-id",
                        help="Spotify app client id for the Web API (asked for interactively if not given)",
                        default=None)
    parser.add_argument("--skip-web-api",
                        help="Only enable the backend, do not set up the Web API",
                        action="store_true", default=False)
    parser.add_argument("-v", "--verbosity",
                        help="Increase verbosity to 'DEBUG'",
                        action="store_true", default=False)
    args = parser.parse_args()

    if args.verbosity is True:
        print("Setting logging level to DEBUG.")
        logconsole.setLevel(logging.DEBUG)

    if host.is_any_jukebox_service_active():
        pyil.msg_highlight('Jukebox service is running!')
        print("\nPlease stop jukebox-daemon service and restart tool")
        print("$ systemctl --user stop jukebox-daemon\n\n")
        print("Don't forget to start the service again :-)")
        return

    enable_backend(args.conffile)
    migrate_cards()

    if args.skip_web_api:
        return
    if args.client_id or pyil.input_yesno("\nConnect the Spotify Web API now (library browsing and search)?",
                                          blank=True, prompt_hint=True):
        connect_web_api(args.client_id)


if __name__ == '__main__':
    main()
