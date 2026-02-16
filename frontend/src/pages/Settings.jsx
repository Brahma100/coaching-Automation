import React from 'react';
import { FiBell, FiCalendar, FiGrid, FiMoon, FiPhone, FiShield, FiSun, FiUser } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import useRole from '../hooks/useRole';
import useTheme from '../hooks/useTheme';
import useTelegramLink from '../hooks/useTelegramLink';
import {
  loadRequested,
  saveLifecycleRulesRequested,
  saveProfileRequested,
  setDeleteMinutes,
  setEnableAutoDeleteNotesOnExpiry,
  setLifecycleNotificationsEnabled,
  setNotificationsOn,
  setToastDurationSeconds,
} from '../store/slices/settingsSlice.js';

function formatDateTime(value) {
  if (!value) return 'Not available';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(parsed);
}

function formatRuleScope(scope) {
  const value = String(scope || '').trim().toLowerCase();
  if (value === 'batch') return 'Batch';
  if (value === 'global') return 'Global';
  if (value === 'default') return 'Default';
  return 'Unknown';
}

function formatRoleLabel(role) {
  const value = String(role || '').trim().toLowerCase();
  if (value === 'admin') return 'Admin';
  if (value === 'teacher') return 'Teacher';
  if (value === 'student') return 'Student';
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : 'User';
}

function maskPhone(value) {
  const digits = String(value || '').replace(/\D/g, '');
  if (!digits) return 'Not available';
  if (digits.length <= 4) return `****${digits}`;
  return `******${digits.slice(-4)}`;
}

function profileInitials(profile) {
  const role = formatRoleLabel(profile?.role || 'user').toUpperCase();
  return role.slice(0, 2);
}

function Settings() {
  const dispatch = useDispatch();
  const { isDark, toggleTheme } = useTheme();
  const { isAdmin } = useRole();
  const { status: telegramLink, beginLink, refreshStatus } = useTelegramLink();
  const {
    loading,
    error,
    brief,
    notificationsOn,
    profile,
    deleteMinutes,
    enableAutoDeleteNotesOnExpiry,
    toastDurationSeconds,
    savingProfile,
    lifecycleNotificationsEnabled,
    savingLifecycleRules,
    lifecycleRuleConfig,
  } = useSelector((state) => state.settings || {});
  const [adminStartOnBrain, setAdminStartOnBrain] = React.useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem('admin.start_on_brain') === '1';
  });

  React.useEffect(() => {
    dispatch(loadRequested({ isAdmin }));
  }, [dispatch, isAdmin]);

  const saveLifecycleRules = () => {
    dispatch(saveLifecycleRulesRequested());
  };

  const saveProfile = () => {
    dispatch(saveProfileRequested());
  };

  const toggleAdminStartOnBrain = (value) => {
    const nextValue = Boolean(value);
    setAdminStartOnBrain(nextValue);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('admin.start_on_brain', nextValue ? '1' : '0');
    }
  };

  const roleLabel = formatRoleLabel(profile?.role || (isAdmin ? 'admin' : 'teacher'));
  const profilePhone = maskPhone(profile?.phone);
  const profileTimezone = String(profile?.timezone || '').trim() || 'Not configured';
  const profileSubtitle = roleLabel === 'Teacher' ? 'Coaching Faculty' : (roleLabel === 'Admin' ? 'Center Administrator' : 'Student Portal User');

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">My Profile</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account preferences and view your current coaching dashboard identity.
        </p>
        <div className="mt-4">
          <div className="flex flex-wrap gap-2">
            <Link
              to="/settings/communication"
              className="inline-flex items-center rounded-lg bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white"
            >
              Open Communication Settings
            </Link>
            <Link
              to="/settings/automation-rules"
              className="inline-flex items-center rounded-lg bg-[#1d4ed8] px-3 py-2 text-sm font-semibold text-white"
            >
              Open Automation Rules
            </Link>
            <Link
              to="/settings/integrations"
              className="inline-flex items-center rounded-lg bg-[#0369a1] px-3 py-2 text-sm font-semibold text-white"
            >
              Open Integrations
            </Link>
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[340px,1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-4">
            <div className="grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-[#ffd6a8] to-[#f08d5f] text-lg font-extrabold text-white">
              {profileInitials(profile)}
            </div>
            <div>
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">{roleLabel}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{profileSubtitle}</p>
            </div>
          </div>

          <div className="mt-5 space-y-3 text-sm">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiUser className="h-4 w-4" />
              <span>Role: {String(profile?.role || roleLabel).toUpperCase()}</span>
            </div>
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiShield className="h-4 w-4" />
              <span>Timezone: {profileTimezone}</span>
            </div>
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiPhone className="h-4 w-4" />
              <span>Phone: {profilePhone}</span>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Theme</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{isDark ? 'Dark Mode' : 'Light Mode'}</p>
              <button
                type="button"
                onClick={toggleTheme}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white"
              >
                {isDark ? <FiSun className="h-4 w-4" /> : <FiMoon className="h-4 w-4" />}
                Switch Theme
              </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Telegram Link</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
                {telegramLink.loading ? 'Checking...' : (telegramLink.linked ? 'Linked' : 'Not linked')}
              </p>
              {telegramLink.linked ? (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Linked chat: {telegramLink.chatIdMasked || 'Hidden'}
                </p>
              ) : (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Link Telegram to receive OTP and all coaching notifications.
                </p>
              )}
              {telegramLink.error ? (
                <p className="mt-2 text-xs text-rose-600 dark:text-rose-300">{telegramLink.error}</p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={beginLink}
                  disabled={telegramLink.starting}
                  className="rounded-lg bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {telegramLink.starting ? 'Opening Telegram...' : (telegramLink.linked ? 'Relink Telegram' : 'Link Telegram')}
                </button>
                <button
                  type="button"
                  onClick={() => refreshStatus()}
                  disabled={telegramLink.checking}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200"
                >
                  {telegramLink.checking ? 'Checking...' : 'Refresh Status'}
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Notifications</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{notificationsOn ? 'Enabled' : 'Muted'}</p>
              <button
                type="button"
                onClick={() => dispatch(setNotificationsOn(!notificationsOn))}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
              >
                <FiBell className="h-4 w-4" />
                {notificationsOn ? 'Mute Alerts' : 'Enable Alerts'}
              </button>
            </div>

            {isAdmin ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Student Lifecycle Alerts</p>
                <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
                  {lifecycleNotificationsEnabled ? 'Enabled' : 'Disabled'}
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Rule scope: {formatRuleScope(lifecycleRuleConfig?.scope)}
                </p>
                <label className="mt-3 inline-flex cursor-pointer items-center gap-3 text-sm text-slate-700 dark:text-slate-200">
                  <input
                    type="checkbox"
                    checked={lifecycleNotificationsEnabled}
                    onChange={(event) => dispatch(setLifecycleNotificationsEnabled(event.target.checked))}
                    className="h-4 w-4 rounded border-slate-300 text-[#2f7bf6] focus:ring-[#2f7bf6]"
                  />
                  Notify for create/delete/enroll/unenroll/batch-delete events
                </label>
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={saveLifecycleRules}
                    disabled={savingLifecycleRules}
                    className="rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    Save
                  </button>
                </div>
              </div>
            ) : null}

            {isAdmin ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Admin Start Page</p>
                <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
                  {adminStartOnBrain ? 'Operational Brain' : 'Dashboard'}
                </p>
                <label className="mt-3 inline-flex cursor-pointer items-center gap-3 text-sm text-slate-700 dark:text-slate-200">
                  <input
                    type="checkbox"
                    checked={adminStartOnBrain}
                    onChange={(event) => toggleAdminStartOnBrain(event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-[#2f7bf6] focus:ring-[#2f7bf6]"
                  />
                  <FiGrid className="h-4 w-4" />
                  Start admin login on /brain
                </label>
              </div>
            ) : null}

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Auto-delete (min)</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{deleteMinutes} minutes</p>
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={240}
                  value={deleteMinutes}
                  onChange={(event) => dispatch(setDeleteMinutes(event.target.value))}
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                />
                <button
                  type="button"
                  onClick={saveProfile}
                  disabled={savingProfile}
                  className="rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Save
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Notes Auto Delete</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
                {enableAutoDeleteNotesOnExpiry ? 'Enabled' : 'Disabled'}
              </p>
              <label className="mt-3 inline-flex cursor-pointer items-center gap-3 text-sm text-slate-700 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={enableAutoDeleteNotesOnExpiry}
                  onChange={(event) => dispatch(setEnableAutoDeleteNotesOnExpiry(event.target.checked))}
                  className="h-4 w-4 rounded border-slate-300 text-[#2f7bf6] focus:ring-[#2f7bf6]"
                />
                Enable Auto Delete Notes on Expiry
              </label>
              <div className="mt-3">
                <button
                  type="button"
                  onClick={saveProfile}
                  disabled={savingProfile}
                  className="rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Save
                </button>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Toast Duration</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{toastDurationSeconds} sec</p>
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={toastDurationSeconds}
                  onChange={(event) => dispatch(setToastDurationSeconds(event.target.value))}
                  className="w-24 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                />
                <button
                  type="button"
                  onClick={saveProfile}
                  disabled={savingProfile}
                  className="rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  Save
                </button>
              </div>
            </div>

            {isAdmin ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Google Drive</p>
                <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">Connect OAuth</p>
                <a
                  href="/backend/api/drive/oauth/start"
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex items-center rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200"
                >
                  Connect Google Drive
                </a>
              </div>
            ) : null}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center gap-2">
              <FiCalendar className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Today&apos;s Brief Snapshot</h3>
            </div>
            {loading ? (
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Loading profile data...</p>
            ) : (
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Classes Today</p>
                  <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{brief?.class_schedule?.count ?? 0}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Pending Actions</p>
                  <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{brief?.pending_actions?.count ?? 0}</p>
                </div>
                <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">High Risk Students</p>
                  <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{brief?.high_risk_students?.count ?? 0}</p>
                </div>
              </div>
            )}
            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
              Last updated: {formatDateTime(brief?.generated_at || brief?.date)}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export default Settings;
