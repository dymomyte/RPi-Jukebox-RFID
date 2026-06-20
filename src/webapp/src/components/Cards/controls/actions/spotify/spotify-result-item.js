import React from 'react';

import {
  Avatar,
  Chip,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import AlbumIcon from '@mui/icons-material/Album';

// Colour-code the result type so tracks / albums / playlists are
// distinguishable at a glance. Values map to MUI Chip palette colours.
const TYPE_COLORS = {
  track: 'info',
  album: 'secondary',
  playlist: 'success',
};

const SpotifyResultItem = ({
  result,
  selected,
  onSelect,
}) => {
  const {
    name,
    artists = [],
    album,
    cover_url,
    type,
  } = result;

  const secondary = [artists.join(', '), album]
    .filter(Boolean)
    .join(' • ');

  return (
    <ListItem disablePadding>
      <ListItemButton
        selected={selected}
        onClick={() => onSelect(result)}
        aria-label={name}
      >
        <ListItemAvatar>
          <Avatar
            variant="rounded"
            src={cover_url || undefined}
            alt={name}
          >
            <AlbumIcon />
          </Avatar>
        </ListItemAvatar>
        <ListItemText
          primary={name}
          secondary={secondary}
          primaryTypographyProps={{ noWrap: true }}
          secondaryTypographyProps={{ noWrap: true }}
        />
        {type && (
          <Chip
            label={type}
            color={TYPE_COLORS[type] || 'default'}
            size="small"
            variant="filled"
            sx={{
              ml: 1,
              flexShrink: 0,
              textTransform: 'capitalize',
            }}
          />
        )}
      </ListItemButton>
    </ListItem>
  );
};

export default SpotifyResultItem;
