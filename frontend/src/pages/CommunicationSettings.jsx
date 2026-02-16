import React from 'react';
import { FiCheckCircle, FiMessageSquare, FiRefreshCw, FiSave, FiZap } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';

import {
  EVENT_OPTIONS,
  healthCheckRequested,
  loadRequested,
  saveRequested,
  setDeleteTimer,
  setProvider,
  setProviderConfigField,
  setQuietEnd,
  setQuietStart,
  setTestMessage,
  testRequested,
  toggleEvent,
} from '../store/slices/communicationSettingsSlice.js';

function CommunicationSettings() {
  const dispatch = useDispatch();
  const {
    loading,
    saving,
    testing,
    healthLoading,
    provider,
    providerConfig,
    enabledEvents,
    quietStart,
    quietEnd,
    deleteTimer,
    connection,
    testMessage,
    feedback,
    error,
    communicationMode,
    externalDashboardUrl,
  } = useSelector((state) => state.communicationSettings || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const updateConfigField = (key, value) => {
    dispatch(setProviderConfigField({ key, value }));
  };

  const providerFields = provider === 'telegram'
    ? [
        { key: 'bot_token', label: 'Bot Token' },
        { key: 'chat_id', label: 'Default Chat ID' },
      ]
    : [
        { key: 'phone_number_id', label: 'Phone Number ID' },
        { key: 'access_token', label: 'Access Token' },
        { key: 'webhook_verify_token', label: 'Webhook Verify Token' },
        { key: 'to', label: 'Test Recipient Number' },
      ];

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">Settings → Communication</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Configure chat providers, event routing, quiet hours, and test connection health.
        </p>
      </div>

      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {feedback ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{feedback}</div> : null}
      {communicationMode === 'embedded' ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">
          Embedded Communication Mode Active
        </div>
      ) : null}
      {communicationMode === 'remote' && externalDashboardUrl ? (
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          External communication service active.{' '}
          <a href={externalDashboardUrl} target="_blank" rel="noreferrer" className="font-semibold underline">
            Open Communication Dashboard
          </a>
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          Loading communication settings...
        </div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Provider Selection</p>
                <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                  connection?.healthy
                    ? 'bg-emerald-100 text-emerald-700 animate-pulse'
                    : 'bg-amber-100 text-amber-700 animate-pulse'
                }`}>
                  <FiCheckCircle className="h-3 w-3" />
                  {connection?.healthy ? 'Connected' : 'Not Connected'}
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {['telegram', 'whatsapp'].map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => dispatch(setProvider(item))}
                    className={`rounded-xl border p-4 text-left transition ${
                      provider === item
                        ? 'border-[#2f7bf6] bg-[#eaf1ff] dark:border-[#66a3ff] dark:bg-slate-800'
                        : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900'
                    }`}
                  >
                    <p className="text-sm font-bold uppercase text-slate-900 dark:text-slate-100">{item}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Tap to activate provider</p>
                  </button>
                ))}
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => dispatch(healthCheckRequested())}
                  disabled={healthLoading}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
                >
                  <FiRefreshCw className="h-4 w-4" />
                  {healthLoading ? 'Refreshing...' : 'Refresh Health'}
                </button>
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Health: {connection?.status || 'unknown'} · {connection?.message || 'No message'}
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <p className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">Connection Settings</p>
              <div className="space-y-3">
                {providerFields.map((field) => (
                  <label key={field.key} className="block">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{field.label}</span>
                    <input
                      type={field.key.includes('token') ? 'password' : 'text'}
                      value={providerConfig?.[field.key] || ''}
                      onChange={(event) => updateConfigField(field.key, event.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <p className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">Enable / Disable Events</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {EVENT_OPTIONS.map((eventType) => {
                const active = enabledEvents.includes(eventType);
                return (
                  <button
                    key={eventType}
                    type="button"
                    onClick={() => dispatch(toggleEvent(eventType))}
                    className={`rounded-xl border p-3 text-left transition ${
                      active
                        ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20'
                        : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900'
                    }`}
                  >
                    <p className="text-xs font-bold text-slate-900 dark:text-slate-100">{eventType}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{active ? 'Enabled' : 'Disabled'}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Quiet Hours</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <input
                  type="time"
                  value={quietStart}
                  onChange={(event) => dispatch(setQuietStart(event.target.value))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                />
                <input
                  type="time"
                  value={quietEnd}
                  onChange={(event) => dispatch(setQuietEnd(event.target.value))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Delete Timer (minutes)</p>
              <input
                type="number"
                min={1}
                max={240}
                value={deleteTimer}
                onChange={(event) => dispatch(setDeleteTimer(event.target.value))}
                className="mt-3 w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Test Message</p>
              <input
                type="text"
                value={testMessage}
                onChange={(event) => dispatch(setTestMessage(event.target.value))}
                className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
              <button
                type="button"
                onClick={() => dispatch(testRequested())}
                disabled={testing}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                <FiMessageSquare className="h-4 w-4" />
                {testing ? 'Sending...' : 'Test Message'}
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <button
              type="button"
              onClick={() => dispatch(saveRequested())}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              <FiSave className="h-4 w-4" />
              {saving ? 'Saving...' : 'Save Communication Settings'}
            </button>
            <span className="ml-3 inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
              <FiZap className="h-3 w-3" />
              Toggle cards + animated status badge enabled
            </span>
          </div>
        </>
      )}
    </section>
  );
}

export default CommunicationSettings;
