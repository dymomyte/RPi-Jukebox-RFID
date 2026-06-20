import sys
import os
# In case this is run locally
sys.path.append(os.path.abspath('../../src/jukebox'))

import pytest  # noqa: E402
from components.spotify import uri_utils  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    # Share links normalize to canonical spotify: URIs (si param dropped)
    ('https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6?si=abc123',
     'spotify:track:6rqhFgbbKwnb9MLmUQDhG6'),
    ('http://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3',
     'spotify:album:1DFixLWuPkv3KT3TnV35m3'),
    ('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',
     'spotify:playlist:37i9dQZF1DXcBWIGoYBM5M'),
    # Localized intl- prefix
    ('https://open.spotify.com/intl-de/track/6rqhFgbbKwnb9MLmUQDhG6?si=x',
     'spotify:track:6rqhFgbbKwnb9MLmUQDhG6'),
    # Already canonical -> pass through
    ('spotify:track:6rqhFgbbKwnb9MLmUQDhG6',
     'spotify:track:6rqhFgbbKwnb9MLmUQDhG6'),
    ('spotify:album:1DFixLWuPkv3KT3TnV35m3',
     'spotify:album:1DFixLWuPkv3KT3TnV35m3'),
    # User-context playlist URI collapses to canonical
    ('spotify:user:someone:playlist:37i9dQZF1DXcBWIGoYBM5M',
     'spotify:playlist:37i9dQZF1DXcBWIGoYBM5M'),
    # Whitespace tolerated
    ('  spotify:track:6rqhFgbbKwnb9MLmUQDhG6  ',
     'spotify:track:6rqhFgbbKwnb9MLmUQDhG6'),
])
def test_normalize_uri(raw, expected):
    assert uri_utils.normalize_uri(raw) == expected


@pytest.mark.parametrize("bad", [
    '',
    None,
    'not a uri',
    'https://example.com/track/abc',
    'spotify:track:',
    'spotify:unknown:abc',
])
def test_normalize_uri_invalid(bad):
    with pytest.raises(ValueError):
        uri_utils.normalize_uri(bad)


def test_parse_uri():
    assert uri_utils.parse_uri('https://open.spotify.com/track/ID123?si=x') == ('track', 'ID123')
    assert uri_utils.parse_uri('spotify:album:AID') == ('album', 'AID')
