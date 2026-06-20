import React from 'react';
import { useTranslation } from 'react-i18next';

import {
  List,
  Typography
} from '@mui/material';

import CardListItem from './card-list-item';

const CardsList = ({ cardsList }) => {
  const { t } = useTranslation();

  return (
    cardsList && Object.keys(cardsList).length > 0
      ? <List sx={{ width: '100%' }}>
          {Object.keys(cardsList).map((cardId) => (
            <CardListItem
              key={cardId}
              cardId={cardId}
              card={cardsList[cardId]}
            />
          ))}
        </List>
      : <Typography>{t('cards.list.no-cards-registered')}</Typography>
  );
}

export default React.memo(CardsList);
