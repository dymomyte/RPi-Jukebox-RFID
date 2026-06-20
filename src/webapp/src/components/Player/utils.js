// Merge the MPD `playerstatus` with the `spotify.status` topic.
//
// When Spotify is the active backend (its state is 'play') we surface the
// Spotify metadata; otherwise we fall back to the regular MPD player status.
// The Spotify payload is normalised into the same shape the rest of the
// Player components already consume (title, artist, album, songid, file, ...).
const normalizeSpotifyStatus = (spotifyStatus) => {
  const {
    state,
    uri,
    title,
    artists,
    artist,
    album,
    cover_url,
    duration_ms,
    elapsed_ms,
  } = spotifyStatus;

  const resolvedArtist = Array.isArray(artists)
    ? artists.join(', ')
    : artist;

  return {
    ...spotifyStatus,
    state,
    // `songid`/`file` are used as "is something playing" markers downstream.
    songid: uri,
    file: uri,
    title,
    artist: resolvedArtist,
    album,
    cover_url,
    duration: duration_ms ? duration_ms / 1000 : undefined,
    elapsed: elapsed_ms ? elapsed_ms / 1000 : undefined,
    isSpotify: true,
  };
};

const getEffectivePlayerStatus = (playerstatus = {}, spotifyStatus) => {
  if (spotifyStatus && spotifyStatus.state === 'play') {
    return normalizeSpotifyStatus(spotifyStatus);
  }

  return playerstatus || {};
};

export {
  getEffectivePlayerStatus,
  normalizeSpotifyStatus,
};
