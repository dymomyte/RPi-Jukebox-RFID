import { useEffect, useState } from "react";
import { useTranslation } from 'react-i18next';

import {
  Box,
  CircularProgress,
  Typography,
} from "@mui/material";

import request from '../../../../utils/request';
import { flatByAlbum } from '../../../../utils/utils';

import AlbumList from "./album-list";

const Albums = ({
  contentTypes,
  musicFilter,
  provider,
  title,
  view,
}) => {
  const { t } = useTranslation();

  const [albums, setAlbums] = useState([]);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const search = ({ albumartist, album }) => {
    if (musicFilter === '') return true;

    const lowerCaseMusicFilter = musicFilter.toLowerCase();

    return (albumartist || '').toLowerCase().includes(lowerCaseMusicFilter) ||
      (album || '').toLowerCase().includes(lowerCaseMusicFilter);
  };

  const contentTypesKey = contentTypes?.join(',') || '';

  useEffect(() => {
    let isCurrent = true;
    const fetchAlbumList = async () => {
      setIsLoading(true);
      setError(null);
      const { result, error: requestError } = await request('libraryItems', {
        provider,
        content_types: contentTypesKey ? contentTypesKey.split(',') : undefined,
      });
      if (!isCurrent) return;
      setIsLoading(false);

      if(result) setAlbums(result.reduce(flatByAlbum, []));
      if(requestError) setError(requestError);
    }

    fetchAlbumList();
    return () => {
      isCurrent = false;
    };
  }, [contentTypesKey, provider]);

  const visibleAlbums = albums.filter(search);

  // A titled section is only shown when it has matches
  if (title) {
    if (isLoading || error || !visibleAlbums.length) return null;
    return (
      <Box component="section" sx={{ width: '100%' }}>
        <Typography component="h2" variant="h6" sx={{ paddingX: 1 }}>
          {title}
        </Typography>
        <AlbumList albums={visibleAlbums} musicFilter={musicFilter} view={view} />
      </Box>
    );
  }

  return (
    <>
      {isLoading
        ? <CircularProgress />
        : <AlbumList
            albums={visibleAlbums}
            musicFilter={musicFilter}
            view={view}
      />}
      {error &&
        <Typography>{t('library.loading-error')}</Typography>
      }
    </>
  );
};

export default Albums;
