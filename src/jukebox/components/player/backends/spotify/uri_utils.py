# RPi-Jukebox-RFID Version 3
# Copyright (c) See file LICENSE in project root folder
"""Helpers for normalizing and parsing Spotify URIs.

Spotify content can be referenced in two common forms:

* Spotify URI:  ``spotify:track:6rqhFgbbKwnb9MLmUQDhG6``
* Share link:   ``https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6?si=abc``

go-librespot and the Web API both expect the ``spotify:<type>:<id>`` form.
This module converts share links to that canonical form and passes through
URIs that are already canonical.

A user's Liked Songs have no id of their own and use the collection URI
``spotify:user:<user id>:collection``, which go-librespot plays as a context.

Spotify serves audiobooks as shows and their chapters as episodes, with the same
ids. Audiobook and chapter references therefore normalize to show and episode URIs.
"""
import re

# Share link, e.g. https://open.spotify.com/track/<id>?si=...
# Also supports the localized form https://open.spotify.com/intl-de/track/<id>
_SHARE_LINK_RE = re.compile(
    r'^https?://open\.spotify\.com/(?:intl-[a-z]{2}/)?'
    r'(?P<type>track|album|playlist|artist|show|episode|audiobook|chapter)/(?P<id>[A-Za-z0-9]+)',
    re.IGNORECASE,
)

# Already canonical, e.g. spotify:track:<id> (also spotify:user:x:playlist:<id>)
_URI_RE = re.compile(
    r'^spotify:(?:[A-Za-z0-9]+:)*'
    r'(?P<type>track|album|playlist|artist|show|episode|audiobook|chapter):(?P<id>[A-Za-z0-9]+)$',
    re.IGNORECASE,
)


# Audiobooks and their chapters play as shows and episodes with the same id
_TYPE_ALIASES = {'audiobook': 'show', 'chapter': 'episode'}

# A user's Liked Songs, e.g. spotify:user:<user id>:collection
_COLLECTION_RE = re.compile(r'^spotify:user:(?P<id>[^:\s]+):collection$', re.IGNORECASE)


def collection_uri(user_id: str) -> str:
    """Return the URI of the Liked Songs of ``user_id``."""
    return f"spotify:user:{user_id}:collection"


def normalize_uri(uri: str) -> str:
    """Normalize a Spotify reference to canonical ``spotify:<type>:<id>`` form.

    :param uri: A Spotify URI or an ``open.spotify.com`` share link
    :return: Canonical ``spotify:<type>:<id>`` URI
    :raises ValueError: if the input cannot be recognized as a Spotify reference
    """
    if not uri or not isinstance(uri, str):
        raise ValueError(f"Not a valid Spotify reference: {uri!r}")

    candidate = uri.strip()

    match = _COLLECTION_RE.match(candidate)
    if match:
        return collection_uri(match.group('id'))

    # Pass URIs through, but drop any leading user-context segments
    match = _URI_RE.match(candidate) or _SHARE_LINK_RE.match(candidate)
    if match:
        uri_type = match.group('type').lower()
        return f"spotify:{_TYPE_ALIASES.get(uri_type, uri_type)}:{match.group('id')}"

    raise ValueError(f"Not a valid Spotify reference: {uri!r}")


def parse_uri(uri: str):
    """Split a Spotify reference into its ``(type, id)`` tuple.

    Accepts share links and URIs (normalized internally).

    :param uri: A Spotify URI or share link
    :return: Tuple ``(type, id)`` e.g. ``('track', '6rqhFgbbKwnb9MLmUQDhG6')``,
        or ``('collection', <user id>)`` for Liked Songs
    :raises ValueError: if the input cannot be parsed
    """
    normalized = normalize_uri(uri)
    match = _COLLECTION_RE.match(normalized)
    if match:
        return 'collection', match.group('id')
    _, uri_type, uri_id = normalized.split(':')
    return uri_type, uri_id
