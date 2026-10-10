import { expect, test } from 'vitest';

import { buildActionData, getArgsValues } from '../../../utils';
import { searchResultToCommand } from './spotify-search';

test('Spotify tracks become provider-aware play_single cards', () => {
  const [command, args] = searchResultToCommand({
    type: 'track',
    uri: 'spotify:track:T',
    name: 'Song',
    artists: ['Artist'],
  });

  expect(command).toBe('play_single');
  expect(getArgsValues(buildActionData('play_music', command, args)))
    .toEqual(['spotify:track:T', 'spotify']);
});

test('Spotify albums and playlists become provider-aware play_album cards', () => {
  for (const type of ['album', 'playlist']) {
    const [command, args] = searchResultToCommand({
      type,
      uri: `spotify:${type}:ID`,
      name: 'Title',
      artists: ['A1', 'A2'],
    });

    expect(command).toBe('play_album');
    expect(getArgsValues(buildActionData('play_music', command, args)))
      .toEqual(['A1, A2', 'Title', `spotify:${type}:ID`, 'spotify']);
  }
});
