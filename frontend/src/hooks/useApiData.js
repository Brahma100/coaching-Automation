import React from 'react';

import api from '../services/api';

function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;

  // FastAPI validation errors: detail is often an array of { loc, msg, type, ... }.
  if (Array.isArray(detail) && detail.length) {
    const formatted = detail
      .slice(0, 3)
      .map((item) => {
        if (!item || typeof item !== 'object') return String(item);
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== 'body').join('.')
          : '';
        const msg = typeof item.msg === 'string' ? item.msg : '';
        if (loc && msg) return `${loc}: ${msg}`;
        if (msg) return msg;
        return JSON.stringify(item);
      })
      .filter(Boolean)
      .join(' • ');

    return formatted || 'Request failed';
  }

  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail);
    } catch {
      return 'Request failed';
    }
  }

  if (typeof err?.message === 'string' && err.message.trim()) return err.message;
  return 'Request failed';
}

function useApiData(url, options = {}) {
  const {
    fetcher,
    deps = [],
    initialData = null,
    auto = true,
    transform,
    onError
  } = options;
  const [data, setData] = React.useState(initialData);
  const [loading, setLoading] = React.useState(auto);
  const [error, setError] = React.useState('');

  const runFetch = React.useCallback(
    async (...args) => {
      setLoading(true);
      setError('');
      try {
        const result = fetcher ? await fetcher(...args) : (await api.get(url)).data;
        const payload = transform ? transform(result) : result;
        setData(payload);
        return payload;
      } catch (err) {
        const message = formatApiError(err);
        setError(message);
        if (onError) onError(err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [fetcher, url, transform, onError]
  );

  React.useEffect(() => {
    if (!auto) return undefined;
    runFetch().catch(() => null);
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return {
    data,
    loading,
    error,
    setData,
    setError,
    refetch: runFetch
  };
}

export default useApiData;
