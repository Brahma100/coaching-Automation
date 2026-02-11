import React from 'react';
import { useLocation } from 'react-router-dom';

import { InlineSkeletonText } from './Skeleton.jsx';
import { validateToken } from '../services/api';

function TokenGate({ token, sessionId, expectedType, onValid, children }) {
  const location = useLocation();
  const [loading, setLoading] = React.useState(true);
  const [tokenInfo, setTokenInfo] = React.useState(null);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      if (!token || !sessionId) {
        setError('Missing token.');
        setLoading(false);
        return;
      }
      try {
        const payload = await validateToken(token, sessionId, expectedType);
        if (mounted) {
          setTokenInfo(payload);
          setError('');
          if (onValid) onValid(payload);
        }
      } catch (err) {
        if (mounted) {
          setTokenInfo(null);
          setError(err?.response?.data?.detail || err?.message || 'Token is invalid or expired.');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [token, sessionId, expectedType, location.pathname]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <InlineSkeletonText />
      </div>
    );
  }

  if (error) {
    const next = `${location.pathname}${location.search}`;
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center">
          <h2 className="text-xl font-bold text-slate-900">Link expired</h2>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
          <a
            className="mt-4 inline-flex rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white"
            href={`/login?next=${encodeURIComponent(next)}`}
          >
            Go to Login
          </a>
        </div>
      </div>
    );
  }

  if (typeof children === 'function') {
    return children(tokenInfo || {});
  }

  return children;
}

export default TokenGate;
