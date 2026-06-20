# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Helpers for normalizing and parsing Spotify URIs.

Spotify content can be referenced in two common forms:

* Spotify URI:  ``spotify:track:6rqhFgbbKwnb9MLmUQDhG6``
* Share link:   ``https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6?si=abc``

go-librespot and the Web API both expect the ``spotify:<type>:<id>`` form.
This module converts share links to that canonical form and passes through
URIs that are already canonical.
"""
import re

# Share link, e.g. https://open.spotify.com/track/<id>?si=...
# Also supports the localized form https://open.spotify.com/intl-de/track/<id>
_SHARE_LINK_RE = re.compile(
    r'^https?://open\.spotify\.com/(?:intl-[a-z]{2}/)?'
    r'(?P<type>track|album|playlist|artist|show|episode)/(?P<id>[A-Za-z0-9]+)',
    re.IGNORECASE,
)

# Already canonical, e.g. spotify:track:<id> (also spotify:user:x:playlist:<id>)
_URI_RE = re.compile(
    r'^spotify:(?:[A-Za-z0-9]+:)*'
    r'(?P<type>track|album|playlist|artist|show|episode):(?P<id>[A-Za-z0-9]+)$',
    re.IGNORECASE,
)


def normalize_uri(uri: str) -> str:
    """Normalize a Spotify reference to canonical ``spotify:<type>:<id>`` form.

    :param uri: A Spotify URI or an ``open.spotify.com`` share link
    :return: Canonical ``spotify:<type>:<id>`` URI
    :raises ValueError: if the input cannot be recognized as a Spotify reference
    """
    if not uri or not isinstance(uri, str):
        raise ValueError(f"Not a valid Spotify reference: {uri!r}")

    candidate = uri.strip()

    match = _URI_RE.match(candidate)
    if match:
        # Pass through, but drop any leading user-context segments
        return f"spotify:{match.group('type').lower()}:{match.group('id')}"

    match = _SHARE_LINK_RE.match(candidate)
    if match:
        return f"spotify:{match.group('type').lower()}:{match.group('id')}"

    raise ValueError(f"Not a valid Spotify reference: {uri!r}")


def parse_uri(uri: str):
    """Split a Spotify reference into its ``(type, id)`` tuple.

    Accepts share links and URIs (normalized internally).

    :param uri: A Spotify URI or share link
    :return: Tuple ``(type, id)`` e.g. ``('track', '6rqhFgbbKwnb9MLmUQDhG6')``
    :raises ValueError: if the input cannot be parsed
    """
    normalized = normalize_uri(uri)
    _, uri_type, uri_id = normalized.split(':')
    return uri_type, uri_id
