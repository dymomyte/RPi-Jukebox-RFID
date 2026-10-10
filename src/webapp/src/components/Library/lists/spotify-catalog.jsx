import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  CircularProgress,
  List,
  Stack,
  Typography,
} from '@mui/material';

import request from '../../../utils/request';
import AlbumListItem from './albums/album-list/album-list-item';
import SongListItem from './albums/song-list/song-list-item';
import SectionLabel from './section-label';

const SEARCH_TYPES = 'track,album,playlist';
const SEARCH_DELAY_MS = 400;
const MIN_QUERY_LENGTH = 2;

// Search results use the library's song and item shapes, so they play and
// assign to cards like any other library entry
const toSong = ({ uri, name, artists = [], duration_ms, cover_url }) => ({
  provider: 'spotify',
  file: uri,
  title: name,
  artist: artists.join(', '),
  duration: duration_ms == null ? undefined : duration_ms / 1000,
  cover_url,
});

const toItem = ({ uri, name, artists = [], cover_url, tracks_available }) => ({
  provider: 'spotify',
  content_uri: uri,
  albumartist: artists.join(', '),
  album: name,
  cover_url,
  tracks_available,
});

const groupResults = (results) => ({
  tracks: results.filter(({ type }) => type === 'track').map(toSong),
  albums: results.filter(({ type }) => type === 'album').map(toItem),
  playlists: results.filter(({ type }) => type === 'playlist').map(toItem),
});

const Section = ({ kind, title, children }) => (
  <Box component="section" sx={{ width: '100%' }}>
    <SectionLabel kind={kind}>{title}</SectionLabel>
    <List sx={{ width: '100%' }}>
      {children}
    </List>
  </Box>
);

const SpotifyCatalog = ({ isSelecting, query, registerMusicToCard }) => {
  const { t } = useTranslation();
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const trimmed = query.trim();

  useEffect(() => {
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setError(null);
      return undefined;
    }

    let isCurrent = true;
    setIsLoading(true);
    const timer = setTimeout(async () => {
      const { result, error: requestError } = await request('spotifySearch', {
        query: trimmed,
        types: SEARCH_TYPES,
      });
      if (!isCurrent) return;
      setIsLoading(false);
      setError(requestError || null);
      setResults(Array.isArray(result) ? result : []);
    }, SEARCH_DELAY_MS);

    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [trimmed]);

  if (trimmed.length < MIN_QUERY_LENGTH) return null;
  if (isLoading) return <CircularProgress />;
  if (error) return <Typography>{t('library.spotify.search-error')}</Typography>;
  if (!results.length) return <Typography>{t('library.spotify.no-results')}</Typography>;

  const { tracks, albums, playlists } = groupResults(results);

  return (
    <Stack spacing={2} sx={{ width: '100%' }}>
      {tracks.length > 0 &&
        <Section kind="songs" title={t('library.spotify.songs')}>
          {tracks.map((song) => (
            <SongListItem
              key={song.file}
              isSelecting={isSelecting}
              registerMusicToCard={registerMusicToCard}
              showCover
              song={song}
            />
          ))}
        </Section>
      }
      {albums.length > 0 &&
        <Section kind="albums" title={t('library.spotify.albums')}>
          {albums.map((item) => (
            <AlbumListItem key={item.content_uri} view="albums" {...item} />
          ))}
        </Section>
      }
      {playlists.length > 0 &&
        <Section kind="playlists" title={t('library.spotify.playlists')}>
          {playlists.map((item) => (
            <AlbumListItem key={item.content_uri} view="playlists" {...item} />
          ))}
        </Section>
      }
    </Stack>
  );
};

export { groupResults };
export default SpotifyCatalog;
