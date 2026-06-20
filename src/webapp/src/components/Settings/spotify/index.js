import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CircularProgress,
  Divider,
  Grid,
  TextField,
  Typography,
} from '@mui/material';

import PubSubContext from '../../../context/pubsub/context';
import request from '../../../utils/request';
import StatusIndicator from './status-indicator';

const SettingsSpotify = () => {
  const { t } = useTranslation();
  const {
    state: { 'spotify.auth_status': pushedAuthStatus },
  } = useContext(PubSubContext);

  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [authStatus, setAuthStatus] = useState({
    web_api_connected: false,
    go_librespot_connected: false,
  });

  const [authUrl, setAuthUrl] = useState(null);
  const [redirectInput, setRedirectInput] = useState('');

  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isSavingCredentials, setIsSavingCredentials] = useState(false);
  const [isStartingAuth, setIsStartingAuth] = useState(false);
  const [isCompletingAuth, setIsCompletingAuth] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchAuthStatus = async () => {
    const { result, error } = await request('spotifyAuthStatus');
    if (result) {
      setAuthStatus(result);
    }
    if (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoadingStatus(true);
      await fetchAuthStatus();
      setIsLoadingStatus(false);
    };

    init();
  }, []);

  // Live updates pushed over the `spotify.auth_status` pubsub topic.
  useEffect(() => {
    if (pushedAuthStatus) {
      setAuthStatus((current) => ({ ...current, ...pushedAuthStatus }));
    }
  }, [pushedAuthStatus]);

  const handleSaveCredentials = async () => {
    setIsSavingCredentials(true);
    setMessage(null);

    const { error } = await request('spotifySetCredentials', {
      client_id: clientId.trim(),
      client_secret: clientSecret.trim(),
    });

    setIsSavingCredentials(false);

    if (error) {
      console.error(error);
      setMessage({ type: 'error', key: 'settings.spotify.credentials.save-error' });
      return;
    }

    setMessage({ type: 'success', key: 'settings.spotify.credentials.save-success' });
  };

  const handleStartAuth = async () => {
    setIsStartingAuth(true);
    setMessage(null);

    const { result, error } = await request('spotifyStartAuth');

    setIsStartingAuth(false);

    if (error || !result?.auth_url) {
      console.error(error);
      setMessage({ type: 'error', key: 'settings.spotify.connect.start-error' });
      return;
    }

    setAuthUrl(result.auth_url);
    window.open(result.auth_url, '_blank', 'noopener,noreferrer');
  };

  const handleCompleteAuth = async () => {
    const value = redirectInput.trim();
    if (!value) {
      return;
    }

    setIsCompletingAuth(true);
    setMessage(null);

    const { result, error } = await request('spotifyCompleteAuth', {
      code_or_url: value,
    });

    setIsCompletingAuth(false);

    if (error || !result?.success) {
      console.error(error);
      setMessage({ type: 'error', key: 'settings.spotify.connect.complete-error' });
      return;
    }

    setMessage({ type: 'success', key: 'settings.spotify.connect.complete-success' });
    setAuthUrl(null);
    setRedirectInput('');
    await fetchAuthStatus();
  };

  return (
    <Card>
      <CardHeader title={t('settings.spotify.title')} />
      <Divider />
      <CardContent>
        <Grid container direction="column" spacing={2}>
          <Grid item>
            {isLoadingStatus
              ? <CircularProgress size={20} />
              : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <StatusIndicator
                    label={t('settings.spotify.status.web-api')}
                    connected={Boolean(authStatus.web_api_connected)}
                  />
                  <StatusIndicator
                    label={t('settings.spotify.status.go-librespot')}
                    connected={Boolean(authStatus.go_librespot_connected)}
                  />
                </Box>
              )
            }
          </Grid>

          <Grid item>
            <Typography variant="subtitle2" gutterBottom>
              {t('settings.spotify.credentials.title')}
            </Typography>
            <Grid container direction="column" spacing={1}>
              <Grid item>
                <TextField
                  fullWidth
                  size="small"
                  value={clientId}
                  onChange={(event) => setClientId(event.target.value)}
                  label={t('settings.spotify.credentials.client-id')}
                />
              </Grid>
              <Grid item>
                <TextField
                  fullWidth
                  size="small"
                  type="password"
                  value={clientSecret}
                  onChange={(event) => setClientSecret(event.target.value)}
                  label={t('settings.spotify.credentials.client-secret')}
                />
              </Grid>
              <Grid item>
                <Button
                  variant="outlined"
                  onClick={handleSaveCredentials}
                  disabled={isSavingCredentials || !clientId.trim() || !clientSecret.trim()}
                >
                  {isSavingCredentials
                    ? <CircularProgress size={20} />
                    : t('settings.spotify.credentials.save')
                  }
                </Button>
              </Grid>
            </Grid>
          </Grid>

          <Grid item>
            <Typography variant="subtitle2" gutterBottom>
              {t('settings.spotify.connect.title')}
            </Typography>
            <Grid container direction="column" spacing={1}>
              <Grid item>
                <Button
                  variant="contained"
                  onClick={handleStartAuth}
                  disabled={isStartingAuth}
                >
                  {isStartingAuth
                    ? <CircularProgress size={20} />
                    : t('settings.spotify.connect.button')
                  }
                </Button>
              </Grid>

              {authUrl &&
                <>
                  <Grid item>
                    <Typography variant="body2">
                      {t('settings.spotify.connect.paste-instructions')}
                    </Typography>
                  </Grid>
                  <Grid item>
                    <TextField
                      fullWidth
                      size="small"
                      value={redirectInput}
                      onChange={(event) => setRedirectInput(event.target.value)}
                      label={t('settings.spotify.connect.redirect-label')}
                    />
                  </Grid>
                  <Grid item>
                    <Button
                      variant="outlined"
                      onClick={handleCompleteAuth}
                      disabled={isCompletingAuth || !redirectInput.trim()}
                    >
                      {isCompletingAuth
                        ? <CircularProgress size={20} />
                        : t('settings.spotify.connect.complete')
                      }
                    </Button>
                  </Grid>
                </>
              }
            </Grid>
          </Grid>

          {message &&
            <Grid item>
              <Typography
                variant="body2"
                color={message.type === 'error' ? 'error' : 'textSecondary'}
              >
                {t(message.key)}
              </Typography>
            </Grid>
          }
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsSpotify;
