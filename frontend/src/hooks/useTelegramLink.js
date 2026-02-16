import React from 'react';

import { fetchTelegramLinkStatus, startTelegramLink } from '../services/api';

function useTelegramLink() {
  const [status, setStatus] = React.useState({
    loading: true,
    linked: false,
    chatIdMasked: '',
    botUsername: '',
    error: '',
    checking: false,
    starting: false,
  });
  const pollTimerRef = React.useRef(null);
  const pollDeadlineRef = React.useRef(0);

  const stopPolling = React.useCallback(() => {
    if (pollTimerRef.current) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollDeadlineRef.current = 0;
  }, []);

  const refreshStatus = React.useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setStatus((prev) => ({ ...prev, checking: true, error: '' }));
    }
    try {
      const data = await fetchTelegramLinkStatus();
      setStatus((prev) => ({
        ...prev,
        loading: false,
        checking: false,
        linked: Boolean(data?.linked),
        chatIdMasked: data?.chat_id_masked || '',
        botUsername: data?.bot_username || '',
        error: '',
      }));
      if (data?.linked) {
        stopPolling();
      }
      return data;
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Could not load Telegram link status';
      setStatus((prev) => ({
        ...prev,
        loading: false,
        checking: false,
        error: detail,
      }));
      return null;
    }
  }, [stopPolling]);

  const startPolling = React.useCallback(() => {
    stopPolling();
    pollDeadlineRef.current = Date.now() + (2 * 60 * 1000);
    pollTimerRef.current = window.setInterval(async () => {
      if (Date.now() >= pollDeadlineRef.current) {
        stopPolling();
        return;
      }
      await refreshStatus({ silent: true });
    }, 4000);
  }, [refreshStatus, stopPolling]);

  const beginLink = React.useCallback(async () => {
    setStatus((prev) => ({ ...prev, starting: true, error: '' }));
    try {
      const data = await startTelegramLink(600);
      const deepLink = data?.deep_link || '';
      if (deepLink && typeof window !== 'undefined') {
        window.open(deepLink, '_blank', 'noopener,noreferrer');
      }
      setStatus((prev) => ({ ...prev, starting: false, error: '' }));
      startPolling();
      return data;
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Could not start Telegram linking';
      setStatus((prev) => ({
        ...prev,
        starting: false,
        error: detail,
      }));
      return null;
    }
  }, [startPolling]);

  React.useEffect(() => {
    refreshStatus();
    return () => stopPolling();
  }, [refreshStatus, stopPolling]);

  return {
    status,
    refreshStatus,
    beginLink,
  };
}

export default useTelegramLink;
