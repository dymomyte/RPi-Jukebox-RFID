import { expect, test } from 'vitest';

import { describeCard } from './card-description';

const t = (key, { defaultValue } = {}) => ({
  'cards.list.folder': 'Folder',
  'cards.controls.command-selector.commands.change_volume': 'Change volume by',
  'cards.controls.select-command-aliases.actions.audio': 'Audio & Volume',
}[key] || defaultValue || key);

const card = (from_alias, args) => ({ from_alias, action: { args } });

test('album cards name the album and artist and look up the cover', () => {
  expect(describeCard(card('play_album', ['Julia Donaldson', 'The Gruffalo', 'spotify:show:S', 'spotify']), t))
    .toEqual({
      type: 'album',
      title: 'The Gruffalo',
      subtitle: 'Julia Donaldson',
      provider: 'spotify',
      lookup: { albumartist: 'Julia Donaldson', album: 'The Gruffalo', content_uri: 'spotify:show:S' },
    });
});

test('song cards are named after the file until looked up', () => {
  expect(describeCard(card('play_single', ['Daft Punk/Discovery/01 One More Time.mp3']), t)).toMatchObject({
    type: 'single', title: '01 One More Time', provider: 'mpd',
  });
  expect(describeCard(card('play_single', ['spotify:track:T', 'spotify']), t)).toMatchObject({
    type: 'single', title: undefined, provider: 'spotify', lookup: { song_url: 'spotify:track:T' },
  });
});

test('folder cards name the folder', () => {
  expect(describeCard(card('play_folder', ['Kids/Mulan (1998)/']), t)).toEqual({
    type: 'folder', title: 'Mulan (1998)', subtitle: 'Folder', provider: 'mpd',
  });
});

test('other actions use their readable command name', () => {
  expect(describeCard(card('change_volume', [5]), t)).toEqual({
    type: 'action', group: 'audio', title: 'Change volume by', subtitle: 'Audio & Volume · 5',
  });
});

test('unknown cards fall back to their alias or function', () => {
  expect(describeCard({ func: "some.plugin.call('x')" }, t)).toMatchObject({
    type: 'unknown', title: "some.plugin.call('x')",
  });
});
