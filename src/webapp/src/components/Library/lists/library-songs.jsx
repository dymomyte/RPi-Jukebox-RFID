import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  CircularProgress,
  List,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';
import SongListItem from './albums/song-list/song-list-item';
import SectionLabel from './section-label';

const matchesFilter = (musicFilter) => {
  const query = musicFilter.toLowerCase();
  return ({ title, artist, album }) => (
    !query || [title, artist, album].some((text) => (text || '').toLowerCase().includes(query))
  );
};

const LibrarySongs = ({
  isSelecting,
  musicFilter,
  provider,
  registerMusicToCard,
  title,
}) => {
  const { t } = useTranslation();
  const [songs, setSongs] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isCurrent = true;
    const fetchSongs = async () => {
      setIsLoading(true);
      setError(null);
      const { result, error: requestError } = await request('librarySongs', { provider });
      if (!isCurrent) return;
      setIsLoading(false);
      if (result) setSongs(result);
      if (requestError) setError(requestError);
    };

    fetchSongs();
    return () => {
      isCurrent = false;
    };
  }, [provider]);

  const visibleSongs = songs.filter(matchesFilter(musicFilter));
  const list = (
    <List sx={{ width: '100%' }}>
      {visibleSongs.map((song) => (
        <SongListItem
          key={song.file}
          isSelecting={isSelecting}
          registerMusicToCard={registerMusicToCard}
          showCover
          song={song}
        />
      ))}
    </List>
  );

  // A titled section is only shown when it has matches
  if (title) {
    if (isLoading || error || !visibleSongs.length) return null;
    return (
      <Box component="section" sx={{ width: '100%' }}>
        <SectionLabel kind="library">{title}</SectionLabel>
        {list}
      </Box>
    );
  }

  if (isLoading) return <CircularProgress />;
  if (error) return <Typography>{t('library.loading-error')}</Typography>;
  if (visibleSongs.length) return list;
  if (musicFilter) return <Typography>{`☝️  ${t('library.albums.no-music')}`}</Typography>;
  return <Typography>{`${t('library.albums.empty-library')} 🙈`}</Typography>;
};

export default LibrarySongs;
