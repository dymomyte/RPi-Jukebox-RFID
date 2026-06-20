import React, { useContext, useEffect, useState } from 'react';

import Grid from '@mui/material/Grid';

import Cover from './cover';
import Controls from './controls';
import Display from './display';
import SeekBar from './seekbar';
import Volume from './volume';

import AppSettingsContext from '../../context/appsettings/context';
import PlayerContext from '../../context/player/context';
import PubSubContext from '../../context/pubsub/context';
import request from '../../utils/request';
import { getEffectivePlayerStatus } from './utils';

const Player = () => {
  const { state: { playerstatus } } = useContext(PlayerContext);
  const { state: { 'spotify.status': spotifyStatus } } = useContext(PubSubContext);

  const effectiveStatus = getEffectivePlayerStatus(playerstatus, spotifyStatus);
  const { file, cover_url, isSpotify } = effectiveStatus;

  const [coverImage, setCoverImage] = useState(undefined);
  const [backgroundImage, setBackgroundImage] = useState('none');

  const {
    settings,
  } = useContext(AppSettingsContext);

  const { show_covers } = settings;

  useEffect(() => {
    const applyCover = (src) => {
      setCoverImage(src);
      setBackgroundImage([
        'linear-gradient(to bottom, rgba(18, 18, 18, 0.5), rgba(18, 18, 18, 1))',
        `url(${src})`
      ].join(','));
    };

    const getCoverArt = async () => {
      const { result } = await request('getSingleCoverArt', { song_url: file });
      if (result) {
        applyCover(`/cover-cache/${result}`);
      };
    }

    if (!show_covers) {
      return;
    }

    // Spotify covers are served as remote URLs by the Web API; pass them
    // through directly instead of going through the local cover cache.
    if (isSpotify && cover_url) {
      applyCover(cover_url);
    } else if (file) {
      getCoverArt();
    }
  }, [file, cover_url, isSpotify, show_covers]);

  return (
    <Grid
      container
      id="player"
      sx={{
        backgroundImage,
        backgroundPosition: 'center',
      }}
    >
      <Grid
        container
        sx={{
          paddingTop: '30px',
          paddingLeft: '30px',
          paddingRight: '30px',
          minHeight: 'calc(100vh - 64px - 10px)',
          backdropFilter: 'blur(25px)',
        }}
      >
        <Grid item xs={12} sm={5}>
          <Cover coverImage={coverImage} />
        </Grid>
        <Grid item xs={12} sm={7}>
          <Display />
          <SeekBar />
          <Controls />
          <Volume />
        </Grid>
      </Grid>
    </Grid>
  );
};

export default Player;
