import React, { forwardRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { isNil, reject } from 'ramda';

import {
  Avatar,
  Chip,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Stack,
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

// Session-lifetime cache of resolved Spotify metadata, keyed by URI. Avoids
// re-fetching (and the placeholder flash) when navigating back to the Cards
// page. The backend also caches per URI, so a reload only re-hits Spotify once.
const metaCache = new Map();

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

  const [meta, setMeta] = useState(() => (uri && metaCache.get(uri)) || null);

  useEffect(() => {
    let active = true;
    if (isSpotify && uri && !metaCache.has(uri)) {
      request('spotifyGetMetadata', { uri }).then(({ result }) => {
        if (result && result.name) {
          metaCache.set(uri, result);
          if (active) setMeta(result);
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
  const chips = [];

  if (isSpotify) {
    // Always flag the card as Spotify-linked.
    chips.push(
      <Chip
        key="spotify"
        label="Spotify"
        color="success"
        size="small"
        sx={{ flexShrink: 0 }}
      />
    );
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
        chips.push(
          <Chip
            key="type"
            label={meta.type}
            color={TYPE_COLORS[meta.type] || 'default'}
            size="small"
            sx={{ flexShrink: 0, textTransform: 'capitalize' }}
          />
        );
      }
    } else {
      // Loading, or unresolved (e.g. Web API not authorised yet).
      secondary = 'Spotify';
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
      {chips.length > 0 && (
        <Stack direction="row" spacing={1} sx={{ ml: 1, flexShrink: 0 }}>
          {chips}
        </Stack>
      )}
    </ListItem>
  );
};

export default CardListItem;
