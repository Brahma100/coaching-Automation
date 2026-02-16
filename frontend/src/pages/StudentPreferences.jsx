import React from 'react';
import { useBlocker } from 'react-router-dom';
import { FiBell, FiBookOpen, FiCheckCircle, FiHeart, FiInfo } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  clearSuccess,
  loadRequested,
  saveRequested,
  togglePreference,
} from '../store/slices/studentPreferencesSlice.js';

function StudentPreferences() {
  const dispatch = useDispatch();
  const {
    loading,
    saving,
    error,
    success,
    values,
    initialValues,
  } = useSelector((state) => state.studentPreferences || {});
  const isDirty = JSON.stringify(values || {}) !== JSON.stringify(initialValues || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  React.useEffect(() => {
    if (isDirty && success) {
      dispatch(clearSuccess());
    }
  }, [dispatch, isDirty, success]);

  React.useEffect(() => {
    if (!isDirty) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const blocker = useBlocker(isDirty);

  React.useEffect(() => {
    if (blocker.state === 'blocked') {
      const discard = window.confirm('Discard unsaved changes?');
      if (discard) {
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker]);

  return (
    <main className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-3xl space-y-6">
        <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Student Settings</p>
          <h1 className="mt-2 text-3xl font-extrabold text-slate-900 dark:text-slate-100">
            Notification Preferences
          </h1>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            Control how and when we notify you.
          </p>
        </header>

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {success}
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
            <FiInfo className="h-4 w-4 text-slate-400" />
            <p className="text-sm">Adjust what you receive. You can change this anytime.</p>
          </div>

          {loading ? (
            <div className="mt-6 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <InlineSkeletonText />
              <span>Loading preferences...</span>
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              <PreferenceRow
                title="Daily Summary"
                description="Get a short summary at night if there is something important."
                icon={<FiBell className="h-5 w-5" />}
                checked={values.enable_daily_digest}
                onChange={() => dispatch(togglePreference('enable_daily_digest'))}
              />

              <PreferenceRow
                title="Homework Reminders"
                description="Reminders when homework is assigned or due."
                icon={<FiBookOpen className="h-5 w-5" />}
                checked={values.enable_homework_reminders}
                onChange={() => dispatch(togglePreference('enable_homework_reminders'))}
              />

              <PreferenceRow
                title="Motivation Messages"
                description="Occasional encouragement based on consistency."
                icon={<FiHeart className="h-5 w-5" />}
                checked={values.enable_motivation_messages}
                onChange={() => dispatch(togglePreference('enable_motivation_messages'))}
              />

              <div className="rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                We keep messages calm and focused. You won&apos;t receive more than a couple of updates per day.
              </div>
            </div>
          )}
        </section>

        {isDirty ? (
          <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
              <FiCheckCircle className="h-4 w-4 text-slate-400" />
              Unsaved changes
            </div>
            <button
              type="button"
              onClick={() => dispatch(saveRequested())}
              disabled={saving}
              className="rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {saving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        ) : null}
      </div>
    </main>
  );
}

function PreferenceRow({ title, description, icon, checked, onChange }) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-800/60 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-white text-slate-700 shadow-sm dark:bg-slate-900 dark:text-slate-200">
          {icon}
        </div>
        <div>
          <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
        </div>
      </div>
      <label className="relative inline-flex cursor-pointer items-center gap-3">
        <input type="checkbox" className="peer sr-only" checked={checked} onChange={onChange} />
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {checked ? 'On' : 'Off'}
        </span>
        <div className="relative h-7 w-12 rounded-full bg-slate-200 transition motion-reduce:transition-none peer-checked:bg-emerald-500 dark:bg-slate-700">
          <span className="absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow-sm transition motion-reduce:transition-none peer-checked:translate-x-5" />
        </div>
      </label>
    </div>
  );
}

export default StudentPreferences;
