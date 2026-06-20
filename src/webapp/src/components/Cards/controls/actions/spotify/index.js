import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Chip,
  CircularProgress,
  Grid,
  IconButton,
  InputAdornment,
  List,
  TextField,
  Typography,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import request from '../../../../../utils/request';
import { getActionAndCommand, getArgsValues } from '../../../utils';
import SpotifyResultItem from './spotify-result-item';

const SEARCH_TYPES = 'track,album,playlist';
const SEARCH_LIMIT = 20;
const COMMAND = 'play_spotify';

const SelectSpotify = ({
  actionData,
  handleActionDataChange,
}) => {
  const { t } = useTranslation();
  const { command } = getActionAndCommand(actionData);
  const [selectedUri] = getArgsValues(actionData);

  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Ensure the command is set as soon as the Spotify action is chosen,
  // so the save button registers the card with `cmd_alias: 'play_spotify'`.
  useEffect(() => {
    if (command !== COMMAND) {
      handleActionDataChange('spotify', COMMAND, { uri: selectedUri });
    }
  }, [command, selectedUri, handleActionDataChange]);

  const handleSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }

    setIsLoading(true);
    setError(null);

    const { result, error } = await request('spotifySearch', {
      query: trimmed,
      types: SEARCH_TYPES,
      limit: SEARCH_LIMIT,
    });

    setIsLoading(false);
    setHasSearched(true);

    if (error) {
      setError(error);
      setResults([]);
      return;
    }

    setResults(Array.isArray(result) ? result : []);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      handleSearch();
    }
  };

  const handleSelect = (result) => {
    handleActionDataChange('spotify', COMMAND, { uri: result.uri });
  };

  return (
    <Grid container direction="column">
      <Grid item xs={12}>
        <TextField
          fullWidth
          size="small"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          label={t('cards.controls.actions.spotify.search-label')}
          placeholder={t('cards.controls.actions.spotify.search-placeholder')}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={handleSearch}
                  edge="end"
                  aria-label={t('cards.controls.actions.spotify.search-label')}
                >
                  <SearchIcon />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </Grid>

      {selectedUri &&
        <Grid item xs={12} sx={{ marginTop: '10px' }}>
          <Chip
            color="success"
            icon={<CheckCircleIcon />}
            label={t('cards.controls.actions.spotify.selected', { uri: selectedUri })}
          />
        </Grid>
      }

      {isLoading &&
        <Grid
          item
          xs={12}
          sx={{
            display: 'flex',
            justifyContent: 'center',
            marginTop: '20px',
            marginBottom: '20px',
          }}
        >
          <CircularProgress size={20} />
        </Grid>
      }

      {error && !isLoading &&
        <Grid item xs={12} sx={{ marginTop: '10px' }}>
          <Typography>
            {t('cards.controls.actions.spotify.search-error')}
          </Typography>
        </Grid>
      }

      {!isLoading && !error && hasSearched && results.length === 0 &&
        <Grid item xs={12} sx={{ marginTop: '10px' }}>
          <Typography>
            {t('cards.controls.actions.spotify.no-results')}
          </Typography>
        </Grid>
      }

      {!isLoading && results.length > 0 &&
        <Grid item xs={12}>
          <Box sx={{ maxHeight: '320px', overflowY: 'auto', width: '100%' }}>
            <List sx={{ width: '100%' }}>
              {results.map((result) => (
                <SpotifyResultItem
                  key={result.uri}
                  result={result}
                  selected={result.uri === selectedUri}
                  onSelect={handleSelect}
                />
              ))}
            </List>
          </Box>
        </Grid>
      }
    </Grid>
  );
};

export default SelectSpotify;
