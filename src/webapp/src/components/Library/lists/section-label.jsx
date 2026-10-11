import { Typography } from '@mui/material';

// Spotify's palette, with dark text that stays readable in light and dark themes
const COLORS = {
  library: '#1db954',
  songs: '#5aa9f8',
  albums: '#b388f0',
  playlists: '#1db954',
  podcasts: '#f59b23',
  audiobooks: '#f573a0',
};

const SectionLabel = ({ kind, children }) => (
  <Typography
    component="h2"
    variant="subtitle1"
    sx={{
      display: 'inline-block',
      marginX: 2,
      paddingX: 2,
      paddingY: 0.5,
      borderRadius: 999,
      backgroundColor: COLORS[kind],
      color: '#101010',
      fontWeight: 700,
      lineHeight: 1.5,
    }}
  >
    {children}
  </Typography>
);

export default SectionLabel;
