import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Grid,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  TextField,
  Typography,
} from '@mui/material';
import AlbumIcon from '@mui/icons-material/Album';
import SearchIcon from '@mui/icons-material/Search';

import request from '../../../../../utils/request';

const SEARCH_TYPES = 'track,album,playlist';

// Colour-code the result type so tracks / albums / playlists are
// distinguishable at a glance. Values map to MUI Chip palette colours.
const TYPE_COLORS = {
  track: 'info',
  album: 'secondary',
  playlist: 'success',
};

// Spotify content is played through the provider-neutral player commands:
// tracks with play_single, albums and playlists with play_album.
const searchResultToCommand = ({ type, uri, name, artists = [] }) => (
  type === 'track'
    ? ['play_single', { song_url: uri, provider: 'spotify' }]
    : ['play_album', {
        albumartist: artists.join(', '),
        album: name,
        content_uri: uri,
        provider: 'spotify',
      }]
);

const SpotifySearchResult = ({ result, onSelect }) => {
  const { t } = useTranslation();
  const {
    album,
    artists = [],
    cover_url,
    name,
    type,
  } = result;

  const secondary = [artists.join(', '), type === 'track' ? album : null]
    .filter(Boolean)
    .join(' • ');

  return (
    <ListItem disablePadding>
      <ListItemButton onClick={() => onSelect(result)} aria-label={name}>
        <ListItemAvatar>
          <Avatar variant="rounded" src={cover_url || undefined} alt={name}>
            <AlbumIcon />
          </Avatar>
        </ListItemAvatar>
        <ListItemText
          primary={name}
          secondary={secondary}
          slotProps={{
            primary: { noWrap: true },
            secondary: { noWrap: true },
          }}
        />
        <Chip
          label={t(`cards.controls.actions.play-music.spotify.types.${type}`)}
          color={TYPE_COLORS[type] || 'default'}
          size="small"
          sx={{ ml: 1, flexShrink: 0 }}
        />
      </ListItemButton>
    </ListItem>
  );
};

const SpotifySearch = ({ onSelect }) => {
  const { t } = useTranslation();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) return;

    setIsLoading(true);
    setError(null);
    const { result, error: requestError } = await request('spotifySearch', {
      query: trimmed,
      types: SEARCH_TYPES,
    });
    setIsLoading(false);
    setHasSearched(true);

    if (requestError) setError(requestError);
    setResults(Array.isArray(result) ? result : []);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSearch();
    }
  };

  const handleSelect = (result) => {
    const [command, args] = searchResultToCommand(result);
    onSelect(command, args);
    setResults([]);
    setHasSearched(false);
  };

  return (
    <Grid container size={12} sx={{ flexDirection: 'column', marginTop: '20px' }}>
      <TextField
        fullWidth
        size="small"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleKeyDown}
        label={t('cards.controls.actions.play-music.spotify.search-label')}
        slotProps={{
          input: {
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={handleSearch}
                  edge="end"
                  aria-label={t('cards.controls.actions.play-music.spotify.search-label')}
                >
                  <SearchIcon />
                </IconButton>
              </InputAdornment>
            ),
          },
        }}
      />

      {isLoading &&
        <Box sx={{ display: 'flex', justifyContent: 'center', margin: '20px 0' }}>
          <CircularProgress size={20} />
        </Box>
      }

      {!isLoading && error &&
        <Typography sx={{ marginTop: '10px' }}>
          {t('cards.controls.actions.play-music.spotify.search-error')}
        </Typography>
      }

      {!isLoading && !error && hasSearched && results.length === 0 &&
        <Typography sx={{ marginTop: '10px' }}>
          {t('cards.controls.actions.play-music.spotify.no-results')}
        </Typography>
      }

      {!isLoading && results.length > 0 &&
        <Box sx={{ maxHeight: '320px', overflowY: 'auto', width: '100%' }}>
          <List sx={{ width: '100%' }}>
            {results.map((result) => (
              <SpotifySearchResult
                key={result.uri}
                result={result}
                onSelect={handleSelect}
              />
            ))}
          </List>
        </Box>
      }
    </Grid>
  );
};

export { searchResultToCommand };
export default SpotifySearch;
