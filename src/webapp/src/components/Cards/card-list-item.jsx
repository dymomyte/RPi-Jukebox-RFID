import { memo, useContext, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  Box,
  Chip,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Skeleton,
} from '@mui/material';

import AlbumIcon from '@mui/icons-material/Album';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import FolderIcon from '@mui/icons-material/Folder';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';
import SyncIcon from '@mui/icons-material/Sync';
import TimerIcon from '@mui/icons-material/Timer';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';

import AppSettingsContext from '../../context/appsettings/context';
import request from '../../utils/request';
import { describeCard } from './card-description';

const ICONS = {
  album: AlbumIcon,
  single: MusicNoteIcon,
  folder: FolderIcon,
  audio: VolumeUpIcon,
  host: PowerSettingsNewIcon,
  timers: TimerIcon,
  synchronisation: SyncIcon,
};

// Same palette as the library's section pills
const SOURCE_COLORS = {
  spotify: '#1db954',
  mpd: '#9e9e9e',
};

const coverSource = (result) => (
  result.startsWith('http') ? result : `/cover-cache/${result}`
);

// Looks up the title, artist and cover a music card does not store itself
const useCardMusic = (description, provider, showCovers) => {
  const [music, setMusic] = useState({});
  const { type, lookup } = description;
  const { albumartist, album, content_uri, song_url } = lookup || {};

  useEffect(() => {
    let isCurrent = true;
    const update = (values) => {
      if (isCurrent) setMusic((current) => ({ ...current, ...values }));
    };

    const lookUpAlbum = async () => {
      if (!showCovers) return;
      const { result } = await request('getAlbumCoverArt', { albumartist, album, content_uri, provider });
      if (result && result !== 'CACHE_PENDING') update({ cover: coverSource(result) });
    };

    const lookUpSingle = async () => {
      const { result } = await request('getSongByUrl', { song_url, provider });
      const song = result?.[0] || {};
      update({ title: song.title, artist: song.artist, isLoaded: true });
      if (!showCovers) return;
      if (song.cover_url) {
        update({ cover: song.cover_url });
        return;
      }
      const { result: cover } = await request('getSingleCoverArt', { song_url, provider });
      if (cover) update({ cover: coverSource(cover) });
    };

    setMusic({});
    if (type === 'album') lookUpAlbum();
    if (type === 'single' && song_url) lookUpSingle();
    return () => {
      isCurrent = false;
    };
  }, [type, albumartist, album, content_uri, song_url, provider, showCovers]);

  return music;
};

const CardListItem = ({ cardId, card }) => {
  const { t } = useTranslation();
  const { settings } = useContext(AppSettingsContext);
  const description = describeCard(card, t);
  const { type, group, provider } = description;
  const music = useCardMusic(description, provider, settings.show_covers);

  const isLoadingTitle = type === 'single' && !music.isLoaded && !description.title;
  const title = music.title || description.title || description.lookup?.song_url;
  const subtitle = music.artist || description.subtitle;
  const Icon = ICONS[type] || ICONS[group] || BookmarkIcon;

  return (
    <ListItem disablePadding>
      <ListItemButton
        component={Link}
        nativeButton={false}
        state={{ id: cardId, ...card }}
        to={`/cards/${cardId}/edit`}
      >
        <ListItemAvatar>
          <Avatar variant="rounded">
            {music.cover
              ? (
                <Box
                  component="img"
                  alt={t('cards.list.cover')}
                  loading="lazy"
                  src={music.cover}
                  sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              )
              : <Icon />
            }
          </Avatar>
        </ListItemAvatar>
        {/* No intrinsic width, so long titles truncate instead of widening the page */}
        <ListItemText
          primary={isLoadingTitle ? <Skeleton width="60%" /> : title}
          secondary={
            // A long subtitle truncates, the card id always stays readable
            <Box component="span" sx={{ display: 'flex', minWidth: 0 }}>
              {subtitle &&
                <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', minWidth: 0 }}>
                  {subtitle}
                </Box>
              }
              <Box component="span" sx={{ flexShrink: 0 }}>
                {subtitle && '\u00a0·\u00a0'}
                {`${t('cards.list.card')}\u00a0`}
                <Box component="span">{cardId}</Box>
              </Box>
            </Box>
          }
          sx={{ minWidth: 0, width: 0 }}
          slotProps={{
            primary: { noWrap: true },
            secondary: { noWrap: true },
          }}
        />
        {provider &&
          <Chip
            label={t(`library.sources.${provider}`, { defaultValue: provider })}
            size="small"
            sx={{
              marginLeft: 1,
              flexShrink: 0,
              backgroundColor: SOURCE_COLORS[provider] || SOURCE_COLORS.mpd,
              color: '#101010',
              fontWeight: 700,
            }}
          />
        }
      </ListItemButton>
    </ListItem>
  );
};

export default memo(CardListItem);
