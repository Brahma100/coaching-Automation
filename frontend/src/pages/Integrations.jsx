import React from 'react';
import { Link } from 'react-router-dom';

import { connectIntegration, disconnectIntegration, fetchIntegrations } from '../services/api';

function providerLabel(provider) {
  const value = String(provider || '').trim().toLowerCase();
  if (value === 'telegram') return 'Telegram';
  if (value === 'whatsapp') return 'WhatsApp';
  return value || 'Provider';
}

function Integrations() {
  const [rows, setRows] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [busyProvider, setBusyProvider] = React.useState('');

  const load = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await fetchIntegrations();
      setRows(Array.isArray(payload?.rows) ? payload.rows : []);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load integrations');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const handleConnect = async (provider) => {
    setBusyProvider(String(provider || ''));
    setError('');
    try {
      await connectIntegration(provider, {});
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Could not connect integration');
    } finally {
      setBusyProvider('');
    }
  };

  const handleDisconnect = async (provider) => {
    setBusyProvider(String(provider || ''));
    setError('');
    try {
      await disconnectIntegration(provider);
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Could not disconnect integration');
    } finally {
      setBusyProvider('');
    }
  };

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">Settings → Integrations</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Connect providers only when features need them. Existing dashboard flows remain unchanged.
        </p>
        <div className="mt-3">
          <Link to="/settings" className="text-sm font-semibold text-[#2f7bf6]">
            Back to Settings
          </Link>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        {(rows || []).map((row) => {
          const provider = String(row?.provider || '');
          const connected = Boolean(row?.connected);
          const busy = busyProvider === provider;
          return (
            <article key={provider} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{providerLabel(provider)}</h3>
                <span
                  className={`rounded-full px-2 py-1 text-xs font-semibold ${
                    connected ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                  }`}
                >
                  {connected ? 'Connected' : 'Not connected'}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                {connected
                  ? `Connected at ${row?.connected_at || 'recently'}`
                  : `Connect ${providerLabel(provider)} to enable dependent features.`}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {!connected ? (
                  <button
                    type="button"
                    onClick={() => handleConnect(provider)}
                    disabled={busy}
                    className="rounded-lg bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    {busy ? 'Connecting...' : `Connect ${providerLabel(provider)}`}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleDisconnect(provider)}
                    disabled={busy}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200"
                  >
                    {busy ? 'Disconnecting...' : 'Disconnect'}
                  </button>
                )}
                {provider === 'telegram' ? (
                  <Link
                    to="/settings/communication"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                  >
                    Open Communication Settings
                  </Link>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>

      {loading ? <p className="text-sm text-slate-500 dark:text-slate-400">Loading integrations...</p> : null}
    </section>
  );
}

export default Integrations;
