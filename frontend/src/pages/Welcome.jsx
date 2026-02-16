import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FiArrowRight, FiCheckCircle, FiCircle, FiUsers, FiBookOpen, FiClipboard } from 'react-icons/fi';

import { fetchActivationStatus } from '../services/api';

const ACTION_META = {
  create_batch: { label: 'Create first batch', to: '/batches', icon: FiBookOpen },
  import_students: { label: 'Import students', to: '/students', icon: FiUsers },
  take_attendance: { label: 'Take attendance', to: '/attendance', icon: FiClipboard },
  dashboard_ready: { label: 'Open dashboard', to: '/dashboard', icon: FiArrowRight },
};

function Welcome() {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(true);
  const [status, setStatus] = React.useState(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await fetchActivationStatus();
        if (!active) return;
        setStatus(data || null);
      } catch {
        if (!active) return;
        setStatus(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
        <p className="text-sm text-slate-500 dark:text-slate-400">Preparing your setup checklist...</p>
      </div>
    );
  }

  const centerName = String(status?.center_name || '').trim() || 'your center';
  const checklist = Array.isArray(status?.checklist_items) ? status.checklist_items : [];
  const progress = Math.max(0, Math.min(100, Number(status?.progress_percent) || 0));
  const actionKey = String(status?.next_action || 'create_batch');
  const cta = ACTION_META[actionKey] || ACTION_META.create_batch;
  const CtaIcon = cta.icon;

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="mx-auto w-full max-w-4xl space-y-6"
    >
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">First Login Setup</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">Welcome to {centerName}</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Complete these quick tasks once, then you are ready for daily operations.</p>

        <div className="mt-5">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-500 dark:text-slate-400">
            <span>Activation Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.4 }}
              className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-sky-500"
            />
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Checklist</h2>
        <div className="mt-4 space-y-3">
          {checklist.map((item, index) => (
            <div key={String(item?.key || `check-${index}`)} className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 dark:border-slate-700">
              {item?.completed ? (
                <FiCheckCircle className="h-5 w-5 text-emerald-500" />
              ) : (
                <FiCircle className="h-5 w-5 text-slate-400" />
              )}
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{String(item?.label || '')}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => navigate(cta.to)}
            className="inline-flex items-center gap-2 rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white hover:bg-[#2a6ee0]"
          >
            <CtaIcon className="h-4 w-4" />
            {cta.label}
          </button>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
          >
            Skip for now
          </Link>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <Link to="/batches" className="rounded-full border border-slate-200 px-3 py-1.5 text-slate-600 dark:border-slate-700 dark:text-slate-300">Batches</Link>
          <Link to="/students" className="rounded-full border border-slate-200 px-3 py-1.5 text-slate-600 dark:border-slate-700 dark:text-slate-300">Students</Link>
          <Link to="/attendance" className="rounded-full border border-slate-200 px-3 py-1.5 text-slate-600 dark:border-slate-700 dark:text-slate-300">Attendance</Link>
        </div>
      </div>
    </motion.section>
  );
}

export default Welcome;
