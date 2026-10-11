import { useContext, useEffect, useState } from 'react';
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
import CancelIcon from '@mui/icons-material/Cancel';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import PubSubContext from '../../context/pubsub/context';
import request from '../../utils/request';

const StatusIndicator = ({ label, connected }) => {
  const { t } = useTranslation();

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      {connected
        ? <CheckCircleIcon color="success" fontSize="small" />
        : <CancelIcon color="disabled" fontSize="small" />
      }
      <Typography variant="body2">
        {`${label}: ${connected
          ? t('settings.spotify.status.connected')
          : t('settings.spotify.status.disconnected')}`}
      </Typography>
    </Box>
  );
};

const SettingsSpotify = () => {
  const { t } = useTranslation();
  const {
    state: { 'spotify.auth_status': pushedAuthStatus },
  } = useContext(PubSubContext);

  const [authStatus, setAuthStatus] = useState({});
  const [clientId, setClientId] = useState('');
  const [authUrl, setAuthUrl] = useState(null);
  const [redirectInput, setRedirectInput] = useState('');
  const [busy, setBusy] = useState(null);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    const fetchAuthStatus = async () => {
      const { result } = await request('spotifyAuthStatus');
      if (result) setAuthStatus(result);
    };
    fetchAuthStatus();
  }, []);

  // Live updates pushed over the `spotify.auth_status` topic
  useEffect(() => {
    if (pushedAuthStatus) setAuthStatus(pushedAuthStatus);
  }, [pushedAuthStatus]);

  const run = async (name, command, kwargs, onResult) => {
    setBusy(name);
    setMessage(null);
    const { result, error } = await request(command, kwargs);
    setBusy(null);
    onResult(result, error);
  };

  const saveClientId = () => run(
    'save',
    'spotifySetClientId',
    { client_id: clientId.trim() },
    (result, error) => {
      if (error) {
        setMessage({ type: 'error', key: 'settings.spotify.client-id.save-error' });
        return;
      }
      setAuthStatus(result);
      setClientId('');
      setMessage({ type: 'success', key: 'settings.spotify.client-id.save-success' });
    },
  );

  const startAuth = () => run('start', 'spotifyStartAuth', {}, (result, error) => {
    if (error || !result?.auth_url) {
      setMessage({ type: 'error', key: 'settings.spotify.connect.start-error' });
      return;
    }
    setAuthUrl(result.auth_url);
    window.open(result.auth_url, '_blank', 'noopener,noreferrer');
  });

  const completeAuth = () => run(
    'complete',
    'spotifyCompleteAuth',
    { code_or_url: redirectInput.trim() },
    (result, error) => {
      if (error || !result?.success) {
        setMessage({ type: 'error', key: 'settings.spotify.connect.complete-error' });
        return;
      }
      setAuthUrl(null);
      setRedirectInput('');
      setMessage({ type: 'success', key: 'settings.spotify.connect.complete-success' });
    },
  );

  const progressOr = (name, label) => (
    busy === name ? <CircularProgress size={20} /> : label
  );

  return (
    <Card>
      <CardHeader
        title={t('settings.spotify.title')}
        subheader={t('settings.spotify.subheader')}
      />
      <Divider />
      <CardContent>
        <Grid container spacing={2} sx={{ flexDirection: 'column' }}>
          <Grid>
            <StatusIndicator
              label={t('settings.spotify.status.go-librespot')}
              connected={Boolean(authStatus.go_librespot_connected)}
            />
            <StatusIndicator
              label={t('settings.spotify.status.web-api')}
              connected={Boolean(authStatus.web_api_connected)}
            />
          </Grid>

          <Grid container spacing={1} sx={{ flexDirection: 'column' }}>
            <Typography variant="subtitle2">
              {t('settings.spotify.client-id.title')}
            </Typography>
            <TextField
              fullWidth
              size="small"
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              label={t('settings.spotify.client-id.label')}
              helperText={authStatus.client_id_configured
                ? t('settings.spotify.client-id.configured')
                : t('settings.spotify.client-id.missing')}
            />
            <Box>
              <Button
                variant="outlined"
                onClick={saveClientId}
                disabled={Boolean(busy) || !clientId.trim()}
              >
                {progressOr('save', t('settings.spotify.client-id.save'))}
              </Button>
            </Box>
          </Grid>

          <Grid container spacing={1} sx={{ flexDirection: 'column' }}>
            <Typography variant="subtitle2">
              {t('settings.spotify.connect.title')}
            </Typography>
            <Box>
              <Button
                variant="contained"
                onClick={startAuth}
                disabled={Boolean(busy) || !authStatus.client_id_configured}
              >
                {progressOr('start', t('settings.spotify.connect.button'))}
              </Button>
            </Box>
            {authUrl &&
              <>
                <Typography variant="body2">
                  {t('settings.spotify.connect.paste-instructions')}
                </Typography>
                <TextField
                  fullWidth
                  size="small"
                  value={redirectInput}
                  onChange={(event) => setRedirectInput(event.target.value)}
                  label={t('settings.spotify.connect.redirect-label')}
                />
                <Box>
                  <Button
                    variant="outlined"
                    onClick={completeAuth}
                    disabled={Boolean(busy) || !redirectInput.trim()}
                  >
                    {progressOr('complete', t('settings.spotify.connect.complete'))}
                  </Button>
                </Box>
              </>
            }
          </Grid>

          {message &&
            <Typography
              variant="body2"
              color={message.type === 'error' ? 'error' : 'textSecondary'}
            >
              {t(message.key)}
            </Typography>
          }
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SettingsSpotify;
