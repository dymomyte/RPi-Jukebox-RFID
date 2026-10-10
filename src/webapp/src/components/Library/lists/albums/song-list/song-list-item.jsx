import { memo, useContext } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  Box,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
} from '@mui/material';

import noCover from '../../../../../assets/noCover.jpg';

import AppSettingsContext from '../../../../../context/appsettings/context';
import { toHHMMSS } from '../../../../../utils/utils';
import request from '../../../../../utils/request'

const SongListItem = ({
  isSelecting,
  registerMusicToCard,
  // Songs from mixed sources (e.g. search results) show their own cover
  showCover = false,
  song,
}) => {
  const { t } = useTranslation();
  const { settings } = useContext(AppSettingsContext);

  const command = 'play_single';
  const {
    artist,
    cover_url,
    duration,
    file,
    provider,
    title,
  } = song;

  const playSingle = () => {
    request(command, { song_url: file, provider })
  }

  const registerSongToCard = () => (
    registerMusicToCard(command, { song_url: file, provider })
  );

  return (
    <ListItem disablePadding>
      <ListItemButton
        role={undefined}
        onClick={() => (isSelecting ? registerSongToCard() : playSingle())}
      >
        {showCover && settings.show_covers &&
          <ListItemAvatar>
            {/* A child image, as Avatar preloads its src and defeats lazy loading in long lists */}
            <Avatar variant="rounded">
              <Box
                component="img"
                alt="Cover"
                loading="lazy"
                src={cover_url || noCover}
                sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </Avatar>
          </ListItemAvatar>
        }
        <ListItemText
          primary={title || t('library.albums.unknown-title')}
          secondary={`${artist || t('library.albums.unknown-artist')} • ${toHHMMSS(duration)}`}
        />
      </ListItemButton>
    </ListItem>
  );
}

export default memo(SongListItem);
