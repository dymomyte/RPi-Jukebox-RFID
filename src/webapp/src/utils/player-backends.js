import { useEffect, useState } from 'react';

import request from './request';

// Names of the backends registered with the player coordinator, e.g. ['mpd', 'spotify'].
const usePlayerBackends = () => {
  const [backends, setBackends] = useState([]);

  useEffect(() => {
    let isCurrent = true;
    const fetchBackends = async () => {
      const { result } = await request('playerBackends');
      if (isCurrent && Array.isArray(result)) setBackends(result);
    };
    fetchBackends();
    return () => {
      isCurrent = false;
    };
  }, []);

  return backends;
};

export { usePlayerBackends };
