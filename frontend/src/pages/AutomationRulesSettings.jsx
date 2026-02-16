import React from 'react';
import { FiSave, FiToggleLeft, FiToggleRight } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';

import {
  clearSaved,
  loadRequested,
  saveRequested,
  toggleRule,
} from '../store/slices/automationRulesSlice.js';

const RULE_DEFS = [
  { key: 'notify_on_attendance', label: 'Notify on attendance' },
  { key: 'class_start_reminder', label: 'Class start reminder' },
  { key: 'fee_due_alerts', label: 'Fee due alerts' },
  { key: 'student_absence_escalation', label: 'Student absence escalation' },
  { key: 'homework_reminders', label: 'Homework reminders' },
];

function ToggleCard({ label, checked, onChange }) {
  return (
    <button
      type="button"
      onClick={onChange}
      className={`rounded-2xl border p-4 text-left transition ${
        checked
          ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20'
          : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900'
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-slate-900 dark:text-slate-100">{label}</p>
        {checked ? (
          <FiToggleRight className="h-6 w-6 text-emerald-600" />
        ) : (
          <FiToggleLeft className="h-6 w-6 text-slate-400" />
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        {checked ? 'Enabled' : 'Disabled'}
      </p>
    </button>
  );
}

function AutomationRulesSettings() {
  const dispatch = useDispatch();
  const { rules, loading, saving, error, saved } = useSelector((state) => state.automationRules || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">Settings → Automation Rules</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Control which notification automations are evaluated before dispatch.
        </p>
      </div>

      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {saved ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{saved}</div> : null}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          Loading rules...
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {RULE_DEFS.map((rule) => (
            <ToggleCard
              key={rule.key}
              label={rule.label}
              checked={Boolean(rules[rule.key])}
              onChange={() => dispatch(toggleRule(rule.key))}
            />
          ))}
        </div>
      )}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <button
          type="button"
          onClick={() => dispatch(saveRequested())}
          disabled={saving || loading}
          className="inline-flex items-center gap-2 rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          <FiSave className="h-4 w-4" />
          {saving ? 'Saving...' : 'Save Rules'}
        </button>
        {saved ? (
          <button
            type="button"
            onClick={() => dispatch(clearSaved())}
            className="ml-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </section>
  );
}

export default AutomationRulesSettings;
