import React from 'react';
import { FiAlertTriangle, FiChevronDown, FiChevronUp, FiRefreshCw } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';

import ActionCard from '../components/ui/ActionCard';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { loadRequested, toggleSection } from '../store/slices/adminOpsSlice.js';

const sectionCard =
  'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900';

function AdminOpsDashboard() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const {
    updatedAt,
    collapsed,
    data,
    loading,
    error,
    errorStatus,
  } = useSelector((state) => state.adminOps || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  React.useEffect(() => {
    if (errorStatus === 401 || errorStatus === 403) {
      navigate(`/login?next=${encodeURIComponent('/admin/ops')}`);
    }
  }, [errorStatus, navigate]);

  const systemAlerts = data?.system_alerts || [];
  const teacherRows = data?.teacher_bottlenecks || [];
  const batchRows = data?.batch_health || [];
  const risk = data?.student_risk_summary || {};
  const automation = data?.automation_health?.items || [];

  const handleRefresh = React.useCallback(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const handleAlertClick = React.useCallback(
    (alert) => {
      if (alert.action_url) {
        navigate(alert.action_url);
      }
    },
    [navigate]
  );

  const handleTeacherClick = React.useCallback(
    (teacherId) => {
      navigate(`/today?teacher_id=${teacherId}`);
    },
    [navigate]
  );

  const handleBatchClick = React.useCallback(
    (batchId) => {
      navigate(`/batches?batch_id=${batchId}`);
    },
    [navigate]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionHeader
          title="Admin Ops Dashboard"
          subtitle="Real-time operations view across teachers, batches, and automations."
          titleClassName="text-2xl font-extrabold"
        />
        <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
          {updatedAt ? (
            <span>Updated {new Date(updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          ) : null}
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          >
            <FiRefreshCw />
            Refresh
          </button>
        </div>
      </div>

      <ErrorState message={error} />

      {loading ? (
        <div className={sectionCard}>
          <LoadingState label="Loading operational overview..." />
        </div>
      ) : (
        <>
          <section className={`${sectionCard} border-l-4 border-l-rose-500`}>
            <HeaderToggle
              title="System Alerts"
              count={systemAlerts.length}
              color="text-rose-600"
              collapsed={collapsed.alerts}
              onToggle={() => dispatch(toggleSection('alerts'))}
            />
            {!collapsed.alerts ? (
              systemAlerts.length ? (
                <div className="space-y-3">
                  {systemAlerts.map((alert) => (
                    <AlertItem
                      key={alert.id}
                      alert={alert}
                      onClick={handleAlertClick}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState title="No critical alerts right now." />
              )
            ) : null}
          </section>

          <section className={`${sectionCard} border-l-4 border-l-amber-400`}>
            <HeaderToggle
              title="Teacher Bottlenecks"
              count={teacherRows.length}
              color="text-amber-600"
              collapsed={collapsed.teachers}
              onToggle={() => dispatch(toggleSection('teachers'))}
            />
            {!collapsed.teachers ? (
              teacherRows.length ? (
                <div className="overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase text-slate-400">
                      <tr>
                        <th className="py-2">Teacher</th>
                        <th className="py-2">Open</th>
                        <th className="py-2">Overdue</th>
                        <th className="py-2">Oldest Overdue</th>
                        <th className="py-2">Classes Missed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {teacherRows.map((row) => (
                        <TeacherRow
                          key={row.teacher_id}
                          row={row}
                          onClick={handleTeacherClick}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No teacher bottlenecks detected." />
              )
            ) : null}
          </section>

          <section className={sectionCard}>
            <HeaderToggle
              title="Batch Health Overview"
              count={batchRows.length}
              color="text-slate-600"
              collapsed={collapsed.batches}
              onToggle={() => dispatch(toggleSection('batches'))}
            />
            {!collapsed.batches ? (
              batchRows.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {batchRows.map((batch) => (
                    <BatchCard key={batch.batch_id} batch={batch} onClick={handleBatchClick} />
                  ))}
                </div>
              ) : (
                <EmptyState title="No active batch data available." />
              )
            ) : null}
          </section>

          <section className={sectionCard}>
            <HeaderToggle
              title="Student Risk Snapshot"
              count={risk.high_risk_students || 0}
              color="text-slate-600"
              collapsed={collapsed.risk}
              onToggle={() => dispatch(toggleSection('risk'))}
            />
            {!collapsed.risk ? (
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard label="High-risk students" value={risk.high_risk_students ?? 0} />
                <MetricCard label="New risks this week" value={risk.new_risk_entries_week ?? 0} />
                <MetricCard
                  label={`Attendance < ${risk.attendance_threshold_percent ?? 0}%`}
                  value={risk.low_attendance_students ?? 0}
                  helper={`Last ${risk.attendance_window_days ?? 0} days`}
                />
              </div>
            ) : null}
          </section>

          <section className={sectionCard}>
            <HeaderToggle
              title="Automation Health"
              count={automation.length}
              color="text-slate-600"
              collapsed={collapsed.automation}
              onToggle={() => dispatch(toggleSection('automation'))}
            />
            {!collapsed.automation ? (
              automation.length ? (
                <div className="grid gap-3 md:grid-cols-2">
                  {automation.map((job) => (
                    <AutomationCard key={job.key} job={job} />
                  ))}
                </div>
              ) : (
                <EmptyState title="Automation activity unavailable." />
              )
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}

function HeaderToggle({ title, count, color, collapsed, onToggle }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
        <p className={`text-xs font-semibold ${color}`}>{count} items</p>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500"
      >
        {collapsed ? 'Expand' : 'Collapse'}
        {collapsed ? <FiChevronDown /> : <FiChevronUp />}
      </button>
    </div>
  );
}

const MetricCard = React.memo(function MetricCard({ label, value, helper }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-800/40">
      <p className="text-xs font-semibold text-slate-500 dark:text-slate-300">{label}</p>
      <p className="mt-2 text-2xl font-extrabold text-slate-800 dark:text-slate-100">{value}</p>
      {helper ? <p className="text-xs text-slate-400 dark:text-slate-400">{helper}</p> : null}
    </div>
  );
});

const AlertItem = React.memo(function AlertItem({ alert, onClick }) {
  const handleClick = React.useCallback(() => onClick(alert), [onClick, alert]);
  return (
    <button
      type="button"
      onClick={handleClick}
      className="w-full rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-left text-sm text-slate-700 transition hover:border-rose-200 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-slate-100"
    >
      <div className="flex items-center gap-2 font-semibold text-rose-700 dark:text-rose-200">
        <FiAlertTriangle />
        {alert.message}
      </div>
      {alert.oldest_overdue_hours ? (
        <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">
          Oldest overdue: {alert.oldest_overdue_hours}h
        </p>
      ) : null}
    </button>
  );
});

const TeacherRow = React.memo(function TeacherRow({ row, onClick }) {
  const handleClick = React.useCallback(() => onClick(row.teacher_id), [onClick, row.teacher_id]);
  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/40">
      <td className="py-3">
        <button
          type="button"
          onClick={handleClick}
          className="text-left font-semibold text-slate-800 dark:text-slate-100"
        >
          {row.teacher_label}
        </button>
        {row.teacher_phone ? <div className="text-xs text-slate-500">{row.teacher_phone}</div> : null}
      </td>
      <td className="py-3 font-semibold text-slate-700 dark:text-slate-200">{row.open_actions}</td>
      <td className="py-3 font-semibold text-amber-600 dark:text-amber-300">{row.overdue_actions}</td>
      <td className="py-3 text-slate-500">{row.oldest_overdue_hours ?? '--'}h</td>
      <td className="py-3 text-slate-500">{row.classes_missed}</td>
    </tr>
  );
});

const BatchCard = React.memo(function BatchCard({ batch, onClick }) {
  const attention = batch.attention_flags?.length;
  const handleClick = React.useCallback(() => onClick(batch.batch_id), [onClick, batch.batch_id]);
  return (
    <button
      type="button"
      onClick={handleClick}
      className={`rounded-xl border px-4 py-3 text-left transition ${
        attention
          ? 'border-amber-200 bg-amber-50 dark:border-amber-900/60 dark:bg-amber-950/40'
          : 'border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/40'
      }`}
    >
      <div className="flex items-center justify-between">
        <p className="font-semibold text-slate-800 dark:text-slate-100">{batch.batch_name}</p>
        {attention ? (
          <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
            Needs attention
          </span>
        ) : null}
      </div>
      <div className="mt-2 grid gap-2 text-xs text-slate-500 dark:text-slate-300 sm:grid-cols-2">
        <div>Attendance completion: {batch.attendance_completion_rate ?? '--'}%</div>
        <div>Absentee trend: {batch.absentee_trend}</div>
        <div>Fee-due students: {batch.fee_due_students}</div>
        <div>Last class: {batch.last_class_date ? new Date(batch.last_class_date).toLocaleDateString() : '--'}</div>
      </div>
    </button>
  );
});

const AutomationCard = React.memo(function AutomationCard({ job }) {
  const statusVariant = job.status === 'ok' ? 'completed' : job.status === 'stale' ? 'due' : 'overdue';
  return (
    <ActionCard className="border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/40">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-slate-800 dark:text-slate-100">{job.label}</p>
        <StatusBadge variant={statusVariant}>{job.status}</StatusBadge>
      </div>
      <div className="mt-2 text-xs text-slate-500 dark:text-slate-300">
        Last run: {job.last_run_at ? new Date(job.last_run_at).toLocaleString() : 'No recent run'}
      </div>
      <div className="text-xs text-slate-500 dark:text-slate-300">
        Age: {job.age_hours ?? '--'}h (expected &lt; {job.expected_window_hours}h)
      </div>
    </ActionCard>
  );
});

export default AdminOpsDashboard;
