import React from 'react';
import { motion } from 'framer-motion';
import { FiArrowRight, FiClock, FiRefreshCw } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';

import EmptyState from '../components/ui/EmptyState.jsx';
import ErrorState from '../components/ui/ErrorState.jsx';
import LoadingState from '../components/ui/LoadingState.jsx';
import SectionHeader from '../components/ui/SectionHeader.jsx';
import { loadRequested } from '../store/slices/brainSlice.js';

const cardCls = 'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900';

function formatClock(value) {
  if (!value) return '--:--';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '--:--';
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function useCountdown(targetIso) {
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const targetTs = new Date(targetIso || '').getTime();
  if (!targetTs || Number.isNaN(targetTs)) return '--:--';
  const diff = Math.max(0, targetTs - now);
  const minutes = Math.floor(diff / 60000);
  const seconds = Math.floor((diff % 60000) / 1000);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function Brain() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    data: payload,
  } = useSelector((state) => state.brain || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const nextClass = payload?.next_upcoming_class || null;
  const timeline = Array.isArray(payload?.timeline) ? payload.timeline : [];
  const pending = Array.isArray(payload?.pending_inbox_actions) ? payload.pending_inbox_actions : [];
  const risk = payload?.risk_students || { high_risk: [], fee_overdue: [], repeat_absentees: [] };
  const warnings = Array.isArray(payload?.capacity_warnings) ? payload.capacity_warnings : [];
  const suggestions = Array.isArray(payload?.suggested_actions) ? payload.suggested_actions : [];
  const centerName = String(payload?.meta?.center_name || '').trim();
  const role = String(payload?.meta?.role || '').toLowerCase();
  const countdown = useCountdown(nextClass?.scheduled_start);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Operational Brain"
        subtitle="Real-time action-centric intelligence for your center."
        titleClassName="text-2xl font-bold"
        action={(
          <button
            type="button"
            onClick={() => dispatch(loadRequested({ bypassCache: true }))}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          >
            <FiRefreshCw />
            Refresh
          </button>
        )}
      />

      <ErrorState message={error} />

      {loading ? (
        <div className={cardCls}>
          <LoadingState label="Loading actionable intelligence..." />
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="h-24 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
            <div className="h-24 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
          </div>
        </div>
      ) : null}

      {!loading ? (
        <>
          <motion.section
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className={cardCls}
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-sky-600">Greeting</p>
                <h3 className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">
                  {role === 'teacher' ? 'Welcome back, Teacher' : 'Welcome back'}
                </h3>
                {centerName ? (
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{centerName}</p>
                ) : null}
              </div>
              <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-900/30 dark:text-sky-200">
                Generated {formatClock(payload?.generated_at)}
              </span>
            </div>
          </motion.section>

          <section className={`${cardCls} border-l-4 border-l-indigo-500`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Next Class</h3>
              <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-200">
                <FiClock />
                Countdown {countdown}
              </span>
            </div>
            {!nextClass ? (
              <EmptyState title="No class starts in the next 2 hours." description="Use this window to clear actions or prep content." className="mt-3" />
            ) : (
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr,auto] md:items-center">
                <div>
                  <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{nextClass.batch_name || 'Upcoming class'}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Starts at {formatClock(nextClass.scheduled_start)} for {nextClass.duration_minutes || 60} min
                  </p>
                </div>
                <Link to="/attendance" className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">
                  Open Attendance <FiArrowRight />
                </Link>
              </div>
            )}
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className={cardCls}>
              <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-100">Urgent Actions</h3>
              {pending.length === 0 ? (
                <EmptyState title="No pending inbox actions." description="You're clear for now." />
              ) : (
                <div className="max-h-[32vh] space-y-2 overflow-auto pr-1">
                  {pending.map((row) => (
                    <div key={row.id} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{row.action_type}</p>
                      <p className="text-xs text-slate-500">{row.student_name || 'General'} {row.due_at ? `• due ${formatClock(row.due_at)}` : ''}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className={cardCls}>
              <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-100">Timeline</h3>
              {timeline.length === 0 ? (
                <EmptyState title="No classes in today's timeline." description="Create or activate batches to start scheduling." />
              ) : (
                <div className="max-h-[32vh] space-y-2 overflow-auto pr-1">
                  {timeline.map((row) => (
                    <div key={`${row.batch_id}-${row.scheduled_start}`} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{row.batch_name}</p>
                      <span className="text-xs text-slate-500">{formatClock(row.scheduled_start)}</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className={cardCls}>
              <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-100">Risk Radar</h3>
              <div className="grid gap-2 sm:grid-cols-3">
                <StatChip title="High Risk" value={risk.high_risk?.length || 0} tone="rose" />
                <StatChip title="Fee Overdue" value={risk.fee_overdue?.length || 0} tone="amber" />
                <StatChip title="Absence Streak" value={risk.repeat_absentees?.length || 0} tone="orange" />
              </div>
            </section>

            <section className={cardCls}>
              <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-100">Capacity Warnings</h3>
              {warnings.length === 0 ? (
                <EmptyState title="No capacity warnings." description="Batch load looks balanced." />
              ) : (
                <div className="space-y-2">
                  {warnings.slice(0, 4).map((row) => (
                    <div key={row.batch_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-800">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{row.batch_name}</p>
                      <span className="text-xs font-semibold text-amber-600">{Math.round(row.utilization_percentage)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className={cardCls}>
            <h3 className="mb-3 text-lg font-semibold text-slate-900 dark:text-slate-100">Quick Actions</h3>
            {suggestions.length === 0 ? (
              <EmptyState title="No suggestions currently." />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {suggestions.map((item) => (
                  <Link
                    key={item.id}
                    to={item.href || '/dashboard'}
                    className="group rounded-xl border border-slate-200 p-3 transition hover:border-slate-300 hover:shadow-sm dark:border-slate-800"
                  >
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{item.label}</p>
                    <p className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-sky-600">
                      {item.cta || 'Open'} <FiArrowRight className="transition group-hover:translate-x-0.5" />
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

function StatChip({ title, value, tone }) {
  const toneClass = tone === 'rose'
    ? 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-200'
    : tone === 'amber'
      ? 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200'
      : 'bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-200';
  return (
    <div className={`rounded-xl px-3 py-2 ${toneClass}`}>
      <p className="text-[11px] font-semibold uppercase tracking-wide">{title}</p>
      <p className="mt-1 text-xl font-extrabold">{value}</p>
    </div>
  );
}

export default Brain;
