// Merge the MPD `playerstatus` with the `spotify.status` topic.
//
// When Spotify is the active backend (its state is 'play') we surface the
// Spotify metadata; otherwise we fall back to the regular MPD player status.
// The Spotify payload is normalised into the same shape the rest of the
// Player components already consume (title, artist, album, songid, file, ...).
const normalizeSpotifyStatus = (spotifyStatus) => {
  const { state, track, elapsed_ms } = spotifyStatus;
  // The `spotify.status` payload nests the track fields under `track`
  // ({uri, name, artists, album, cover_url, duration_ms}); flatten them into
  // the shape the Player components consume (title, artist, songid, ...).
  const {
    uri,
    name,
    artists,
    album,
    cover_url,
    duration_ms,
  } = track || {};

  const resolvedArtist = Array.isArray(artists) ? artists.join(', ') : undefined;

  return {
    ...spotifyStatus,
    state,
    // `songid`/`file` are used as "is something playing" markers downstream.
    songid: uri,
    file: uri,
    title: name,
    artist: resolvedArtist,
    album,
    cover_url,
    duration: duration_ms ? duration_ms / 1000 : undefined,
    elapsed: elapsed_ms ? elapsed_ms / 1000 : undefined,
    isSpotify: true,
  };
};

// Spotify is the "active" backend whenever it has a loaded track that is
// playing or paused (only one backend plays at a time due to arbitration).
// While paused we still surface Spotify so the controls can resume it.
const isSpotifyActive = (spotifyStatus) => (
  !!spotifyStatus
  && (spotifyStatus.state === 'play' || spotifyStatus.state === 'pause')
  && !!spotifyStatus.track
);

const getEffectivePlayerStatus = (playerstatus = {}, spotifyStatus) => {
  if (isSpotifyActive(spotifyStatus)) {
    return normalizeSpotifyStatus(spotifyStatus);
  }

  return playerstatus || {};
};

export {
  getEffectivePlayerStatus,
  isSpotifyActive,
  normalizeSpotifyStatus,
};
