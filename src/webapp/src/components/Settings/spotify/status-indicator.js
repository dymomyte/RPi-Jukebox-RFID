import React from 'react';
import { useTranslation } from 'react-i18next';

import { Box, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

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

export default StatusIndicator;
