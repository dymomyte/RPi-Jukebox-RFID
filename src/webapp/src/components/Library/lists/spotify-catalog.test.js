import { expect, test } from 'vitest';

import { groupResults } from './spotify-catalog';

test('groupResults shapes Spotify search results like library songs and items', () => {
  const grouped = groupResults([
    { type: 'track', uri: 'spotify:track:T', name: 'Song', artists: ['A1', 'A2'], duration_ms: 1500, cover_url: 'art' },
    { type: 'album', uri: 'spotify:album:A', name: 'Album', artists: ['Band'], cover_url: 'cover' },
    { type: 'playlist', uri: 'spotify:playlist:P', name: 'Mix', artists: ['Owner'], tracks_available: false },
  ]);

  expect(grouped.tracks).toEqual([
    { provider: 'spotify', file: 'spotify:track:T', title: 'Song', artist: 'A1, A2', duration: 1.5, cover_url: 'art' },
  ]);
  expect(grouped.albums).toEqual([{
    provider: 'spotify',
    content_uri: 'spotify:album:A',
    albumartist: 'Band',
    album: 'Album',
    cover_url: 'cover',
    tracks_available: undefined,
  }]);
  expect(grouped.playlists[0]).toMatchObject({ content_uri: 'spotify:playlist:P', tracks_available: false });
});
