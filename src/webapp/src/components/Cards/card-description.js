import { findActionByCommand } from './utils';

const lastPathSegment = (path = '') => (
  path.replace(/\/+$/, '').split('/').pop() || path
);

const fileTitle = (file = '') => (
  lastPathSegment(file).replace(/\.[^.]+$/, '')
);

// Describes what a card does in words, from what is stored on the card. Music
// cards also say what to look up for their title or cover.
const describeCard = (card = {}, t) => {
  const alias = card.from_alias;
  const args = card.action?.args || [];

  if (alias === 'play_album') {
    const [albumartist, album, content_uri, provider = 'mpd'] = args;
    return {
      type: 'album',
      title: album,
      subtitle: albumartist,
      provider: provider || 'mpd',
      lookup: { albumartist, album, content_uri },
    };
  }

  if (alias === 'play_single') {
    const [song_url, provider = 'mpd'] = args;
    const isLocal = !provider || provider === 'mpd';
    return {
      type: 'single',
      // Local songs are named after their file until the lookup returns
      title: isLocal ? fileTitle(song_url) : undefined,
      subtitle: undefined,
      provider: provider || 'mpd',
      lookup: { song_url },
    };
  }

  if (alias === 'play_folder') {
    return {
      type: 'folder',
      title: lastPathSegment(args[0]),
      subtitle: t('cards.list.folder'),
      provider: 'mpd',
    };
  }

  const group = alias && findActionByCommand(alias);
  if (group) {
    const details = args.filter((arg) => arg !== null && arg !== undefined && arg !== '').join(', ');
    return {
      type: 'action',
      group,
      title: t(`cards.controls.command-selector.commands.${alias}`, { defaultValue: alias }),
      subtitle: [t(`cards.controls.select-command-aliases.actions.${group}`), details].filter(Boolean).join(' · '),
    };
  }

  return {
    type: 'unknown',
    title: alias || card.func,
    subtitle: undefined,
  };
};

export { describeCard, fileTitle };
