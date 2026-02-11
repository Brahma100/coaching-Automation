import React from 'react';
import { useLocation } from 'react-router-dom';

function useQueryParam(name) {
  const location = useLocation();
  return React.useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get(name);
  }, [location.search, name]);
}

export default useQueryParam;
