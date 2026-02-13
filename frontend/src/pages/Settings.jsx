import React from 'react';
import { FiBell, FiCalendar, FiMoon, FiPhone, FiShield, FiSun, FiUser } from 'react-icons/fi';

import useRole from '../hooks/useRole';
import useTheme from '../hooks/useTheme';
import { fetchTeacherProfile, fetchTodayBrief, setGlobalToastDurationSeconds, updateTeacherProfile } from '../services/api';

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

function Settings() {
  const { isDark, toggleTheme } = useTheme();
  const { isAdmin } = useRole();
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [brief, setBrief] = React.useState(null);
  const [notificationsOn, setNotificationsOn] = React.useState(true);
  const [profile, setProfile] = React.useState(null);
  const [deleteMinutes, setDeleteMinutes] = React.useState(15);
  const [enableAutoDeleteNotesOnExpiry, setEnableAutoDeleteNotesOnExpiry] = React.useState(false);
  const [toastDurationSeconds, setToastDurationSeconds] = React.useState(5);
  const [savingProfile, setSavingProfile] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [briefPayload, profilePayload] = await Promise.all([fetchTodayBrief(), fetchTeacherProfile()]);
        if (mounted) {
          setBrief(briefPayload || null);
          setProfile(profilePayload || null);
          setDeleteMinutes(profilePayload?.notification_delete_minutes ?? 15);
          setEnableAutoDeleteNotesOnExpiry(Boolean(profilePayload?.enable_auto_delete_notes_on_expiry));
          setToastDurationSeconds(profilePayload?.ui_toast_duration_seconds ?? 5);
          setGlobalToastDurationSeconds(profilePayload?.ui_toast_duration_seconds ?? 5);
          setError('');
        }
      } catch (err) {
        if (mounted) {
          setError(err?.response?.data?.detail || err?.message || 'Could not load profile insights');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const payload = await updateTeacherProfile({
        notification_delete_minutes: Number(deleteMinutes),
        enable_auto_delete_notes_on_expiry: Boolean(enableAutoDeleteNotesOnExpiry),
        ui_toast_duration_seconds: Number(toastDurationSeconds),
      });
      setProfile((prev) => ({
        ...(prev || {}),
        notification_delete_minutes: payload.notification_delete_minutes,
        enable_auto_delete_notes_on_expiry: Boolean(payload.enable_auto_delete_notes_on_expiry),
        ui_toast_duration_seconds: payload.ui_toast_duration_seconds ?? 5,
      }));
      setToastDurationSeconds(payload.ui_toast_duration_seconds ?? 5);
      setGlobalToastDurationSeconds(payload.ui_toast_duration_seconds ?? 5);
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Could not update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">My Profile</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account preferences and view your current coaching dashboard identity.
        </p>
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
              TS
            </div>
            <div>
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">Teacher</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">K-12 Coach</p>
            </div>
          </div>

          <div className="mt-5 space-y-3 text-sm">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiUser className="h-4 w-4" />
              <span>Role: TEACHER</span>
            </div>
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiShield className="h-4 w-4" />
              <span>Access: Protected Session</span>
            </div>
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <FiPhone className="h-4 w-4" />
              <span>Phone: Hidden for privacy</span>
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
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Notifications</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{notificationsOn ? 'Enabled' : 'Muted'}</p>
              <button
                type="button"
                onClick={() => setNotificationsOn((prev) => !prev)}
                className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
              >
                <FiBell className="h-4 w-4" />
                {notificationsOn ? 'Mute Alerts' : 'Enable Alerts'}
              </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Auto-delete (min)</p>
              <p className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">{deleteMinutes} minutes</p>
              <div className="mt-3 flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={240}
                  value={deleteMinutes}
                  onChange={(event) => setDeleteMinutes(event.target.value)}
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
                  onChange={(event) => setEnableAutoDeleteNotesOnExpiry(event.target.checked)}
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
                  onChange={(event) => setToastDurationSeconds(event.target.value)}
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
