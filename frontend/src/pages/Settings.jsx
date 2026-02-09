import React from 'react';
import { FiBell, FiCalendar, FiMoon, FiPhone, FiShield, FiSun, FiUser } from 'react-icons/fi';

import useTheme from '../hooks/useTheme';
import { fetchTodayBrief } from '../services/api';

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
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [brief, setBrief] = React.useState(null);
  const [notificationsOn, setNotificationsOn] = React.useState(true);

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const payload = await fetchTodayBrief();
        if (mounted) {
          setBrief(payload || null);
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
