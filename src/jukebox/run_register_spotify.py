#!/usr/bin/env python
"""
Setup tool to register Spotify (Web API) with the Jukebox.

Run this once on the box to:

1. Store the Spotify application ``client_id`` / ``client_secret`` (secrets file
   under ``shared/settings/``).
2. Complete the one-time **Authorization Code + PKCE** login: the tool prints an
   auth URL, runs a tiny local listener on ``127.0.0.1:<port>`` to catch the
   redirect, and caches the resulting token (auto-refreshed thereafter by
   spotipy).

This is the dependable headless path; the same flow can also be driven from the
Web App Settings page.

> [!NOTE]
> Requires a Spotify Developer app whose redirect URI is registered as
> ``http://127.0.0.1:<port>/callback`` (IP, not ``localhost`` -- per the
> 27 Nov 2025 OAuth migration).
"""
import argparse
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import misc.inputminus as pyil
import jukebox.cfghandler
import jukebox.plugs
jukebox.plugs.ALLOW_DIRECT_IMPORTS = True
import components.hostif.linux as host  # noqa: E402
import components.spotify as spotify  # noqa: E402
from components.spotify.spotify_web_api import SpotifyWebApi  # noqa: E402

# Create logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logconsole = logging.StreamHandler()
logconsole.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)-8s: %(message)s',
                                           datefmt='%d.%m.%Y %H:%M:%S'))
logconsole.setLevel(logging.INFO)
logger.addHandler(logconsole)

cfg = jukebox.cfghandler.get_handler('jukebox')


class _RedirectHandler(BaseHTTPRequestHandler):
    """Single-shot HTTP handler that captures the OAuth redirect ``code``."""
    captured_url = None

    def do_GET(self):  # noqa: N802 (http.server API)
        _RedirectHandler.captured_url = self.path
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'<html><body><h2>Spotify authorization received.</h2>'
                         b'<p>You can close this window and return to the terminal.</p>'
                         b'</body></html>')

    def log_message(self, *args):
        # Silence the default stderr logging
        pass


def _capture_redirect(port: int, timeout: float = 300.0):
    """Run a one-shot local listener and return the captured redirect URL.

    :param port: Port to listen on (must match the registered redirect URI)
    :param timeout: Seconds to wait for the redirect before giving up
    :return: The full redirect path (incl. query) or None on timeout
    """
    server = HTTPServer(('127.0.0.1', port), _RedirectHandler)
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout)
    server.server_close()
    return _RedirectHandler.captured_url


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client-id", help="Spotify application client id", default=None)
    parser.add_argument("--client-secret", help="Spotify application client secret", default=None)
    parser.add_argument("-p", "--port", type=int, default=8080,
                        help="Redirect listener port (default: 8080). Must match the "
                             "redirect URI registered in your Spotify app.")
    parser.add_argument("-v", "--verbosity", action="store_true", default=False,
                        help="Increase verbosity to 'DEBUG'")
    args = parser.parse_args()

    if args.verbosity:
        logconsole.setLevel(logging.DEBUG)

    if host.is_any_jukebox_service_active():
        pyil.msg_highlight('Jukebox service is running!')
        print("\nPlease stop jukebox-daemon service and restart tool")
        print("$ systemctl --user stop jukebox-daemon\n\n")
        print("Don't forget to start the service again :-)")
        return

    client_id = args.client_id
    client_secret = args.client_secret
    if not client_id:
        client_id = input("Spotify client_id: ").strip()
    if not client_secret:
        client_secret = input("Spotify client_secret (optional for PKCE, press Enter to skip): ").strip()

    # Persist credentials via the component helper (writes the secrets yaml)
    spotify.write_credentials(client_id, client_secret or None)

    cache_path = os.path.abspath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '../../shared/settings/spotify-token.json'))

    web_api = SpotifyWebApi(client_id=client_id, client_secret=client_secret or None,
                            redirect_port=args.port, cache_path=cache_path)

    auth = web_api.start_auth()
    auth_url = auth.get('auth_url')
    if not auth_url:
        print("\nERROR: Could not build an authorization URL. Is 'spotipy' installed?")
        print("Install component requirements: pip install -r components/spotify/requirements.txt")
        return

    print("\n" + "=" * 70)
    print("Open this URL in a browser (on any device that can reach this box):\n")
    print(f"  {auth_url}\n")
    print(f"After approving, Spotify redirects to http://127.0.0.1:{args.port}/callback")
    print("This tool is listening for that redirect now...")
    print("=" * 70 + "\n")

    redirect_url = _capture_redirect(args.port)
    if redirect_url is None:
        print("Timed out waiting for the redirect. You can paste the full redirect URL manually.")
        redirect_url = input("Paste redirect URL (or just the code): ").strip()
    else:
        # Reconstruct a full URL so spotipy can parse the code
        query = urlparse(redirect_url).query
        code = parse_qs(query).get('code', [''])[0]
        redirect_url = code or redirect_url

    result = web_api.complete_auth(redirect_url)
    if result.get('success'):
        print("\nSpotify Web API authorization successful. Token cached at:")
        print(f"  {cache_path}")
    else:
        print("\nSpotify Web API authorization FAILED. Check the logs and try again.")


if __name__ == '__main__':
    main()
