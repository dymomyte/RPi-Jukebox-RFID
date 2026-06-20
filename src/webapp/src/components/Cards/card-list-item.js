import React, { forwardRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { isNil, reject } from 'ramda';

import {
  Avatar,
  Chip,
  ListItem,
  ListItemAvatar,
  ListItemText,
} from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';

import request from '../../utils/request';

const SPOTIFY_ALIAS = 'play_spotify';
// Match the colour-coding used by the Spotify search results.
const TYPE_COLORS = {
  track: 'info',
  album: 'secondary',
  playlist: 'success',
};

const EditCardLink = forwardRef((props, ref) => {
  const { data } = props;
  const location = {
    pathname: `/cards/${data.id}/edit`,
    state: data,
  };

  return <Link ref={ref} to={location} {...props} />;
});

// A single card row. Spotify cards resolve their URI to a friendly
// "Name — Artist" label (with cover art + type chip); everything else keeps
// the original "alias, args" description.
const CardListItem = ({ cardId, card }) => {
  const isSpotify = card.from_alias === SPOTIFY_ALIAS;
  const uri = isSpotify
    ? (Array.isArray(card.action?.args) ? card.action.args[0] : card.action?.args)
    : null;

  const [meta, setMeta] = useState(null);

  useEffect(() => {
    let active = true;
    if (isSpotify && uri) {
      request('spotifyGetMetadata', { uri }).then(({ result }) => {
        if (active && result && result.name) {
          setMeta(result);
        }
      });
    }
    return () => { active = false; };
  }, [isSpotify, uri]);

  // Original behaviour for non-Spotify (and as the pre-resolve fallback).
  const fallbackDescription = card.from_alias
    ? reject(isNil, [card.from_alias, card.action?.args]).join(', ')
    : card.func;

  let secondary = fallbackDescription;
  let avatar = <Avatar><BookmarkIcon /></Avatar>;
  let chip = null;

  if (isSpotify) {
    if (meta) {
      const artistLine = (meta.artists || []).join(', ');
      secondary = artistLine ? `${meta.name} — ${artistLine}` : meta.name;
      if (meta.cover_url) {
        avatar = (
          <Avatar variant="rounded" src={meta.cover_url} alt={meta.name}>
            <BookmarkIcon />
          </Avatar>
        );
      }
      if (meta.type) {
        chip = (
          <Chip
            label={meta.type}
            color={TYPE_COLORS[meta.type] || 'default'}
            size="small"
            sx={{ ml: 1, flexShrink: 0, textTransform: 'capitalize' }}
          />
        );
      }
    } else {
      // Loading, or unresolved (e.g. Web API not authorised yet).
      secondary = 'Spotify';
      chip = (
        <Chip
          label="Spotify"
          color="success"
          size="small"
          variant="outlined"
          sx={{ ml: 1, flexShrink: 0 }}
        />
      );
    }
  }

  return (
    <ListItem
      button
      component={EditCardLink}
      data={{ id: cardId, ...card }}
    >
      <ListItemAvatar>
        {avatar}
      </ListItemAvatar>
      <ListItemText
        primary={cardId}
        secondary={secondary}
        primaryTypographyProps={{ noWrap: true }}
        secondaryTypographyProps={{ noWrap: true }}
      />
      {chip}
    </ListItem>
  );
};

export default CardListItem;
