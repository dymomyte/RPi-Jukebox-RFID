import React from 'react';

import {
  Avatar,
  ListItem,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import AlbumIcon from '@mui/icons-material/Album';

const SpotifyResultItem = ({
  result,
  selected,
  onSelect,
}) => {
  const {
    uri,
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
          secondary={secondary || type}
          primaryTypographyProps={{ noWrap: true }}
          secondaryTypographyProps={{ noWrap: true }}
        />
      </ListItemButton>
    </ListItem>
  );
};

export default SpotifyResultItem;
