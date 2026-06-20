import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import PlayerContext from '../../context/player/context';
import PubSubContext from '../../context/pubsub/context';
import { getEffectivePlayerStatus } from './utils';
import {
  progressToTime,
  timeToProgress,
  toHHMMSS,
} from '../../utils/utils';

import Grid from '@mui/material/Grid';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';

import request from '../../utils/request';

const SeekBar = () => {
  const { t } = useTranslation();
  const { state } = useContext(PlayerContext);
  const { playerstatus } = state;
  const { state: { 'spotify.status': spotifyStatus } } = useContext(PubSubContext);

  // Reflect whichever backend is active (MPD or Spotify).
  const effectiveStatus = getEffectivePlayerStatus(playerstatus, spotifyStatus);
  const isSpotify = !!effectiveStatus.isSpotify;

  const [isSeeking, setIsSeeking] = useState(false);
  const [progress, setProgress] = useState(0);
  const [timeElapsed, setTimeElapsed] = useState(parseFloat(effectiveStatus?.elapsed) || 0);
  const timeTotal = parseFloat(effectiveStatus?.duration) || 0;

  const updateTimeAndProgress = (newTime) => {
    setTimeElapsed(newTime);
    setProgress(timeToProgress(timeTotal, newTime));
  };

  // Handle seek events when sliding the progress bar
  const handleSeekToPosition = (event, newPosition) => {
    setIsSeeking(true);
    updateTimeAndProgress(progressToTime(timeTotal, newPosition));
  };

  // Only send commend to backend when user committed to new position
  // We don't send it while seeking (too many useless requests)
  const playFromNewTime = () => {
    if (isSpotify) {
      // go-librespot seeks in milliseconds; MPD seeks in seconds.
      request('spotifySeek', { new_time: Math.round(timeElapsed * 1000) });
    } else {
      request('seek', { new_time: timeElapsed.toFixed(3) });
    }
    setIsSeeking(false);
  };

  useEffect(() => {
    // Avoid updating time and progress when user is seeking to new
    // song position
    if (!isSeeking) {
      updateTimeAndProgress(effectiveStatus?.elapsed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerstatus, spotifyStatus]);

  return <>
    <Grid container>
      <Grid item xs>
        <Slider
          aria-labelledby={t('player.seekbar.song-position')}
          disabled={!effectiveStatus?.title}
          onChange={handleSeekToPosition}
          onChangeCommitted={playFromNewTime}
          size="small"
          value={progress || 0}
        />
      </Grid>
    </Grid>
    <Grid
      alignItems="center"
      container
      direction="row"
      justifyContent="space-between"
      sx={ {
        marginTop: '-10px',
      }}
    >
      <Grid item>
        <Typography color="textSecondary">
          {toHHMMSS(parseInt(timeElapsed))}
        </Typography>
      </Grid>
      <Grid item>
        <Typography color="textSecondary">
          {toHHMMSS(parseInt(timeTotal))}
        </Typography>
      </Grid>
    </Grid>
  </>;
};

export default SeekBar;
