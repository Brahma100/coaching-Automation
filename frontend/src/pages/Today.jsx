import React from 'react';
import { FiCheckCircle, FiExternalLink, FiRefreshCw } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';

import ActionCard from '../components/ui/ActionCard';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import SectionHeader from '../components/ui/SectionHeader';
import StatusBadge from '../components/ui/StatusBadge';
import useApiData from '../hooks/useApiData';
import useQueryParam from '../hooks/useQueryParam';
import useRole from '../hooks/useRole';
import { fetchTodayView, resolveInboxAction } from '../services/api';

const sectionCard = 'rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900';
const dashboardSubtitle = 'Action-first dashboard answering: \"What do I need to do today?\"';
const sectionLabels = {
  overdue: '\uD83D\uDD34 Overdue Actions',
  due: '\uD83D\uDFE1 Due Today',
  classes: '\uD83D\uDCD8 Today\'s Classes',
  flags: '\u26A0 Key Flags',
  completed: '\u2705 Completed Today'
};

function Today() {
  const navigate = useNavigate();
  const { isAdmin, loading: roleLoading } = useRole();
  const teacherIdParam = useQueryParam('teacher_id');
  const [data, setData] = React.useState(null);
  const [teacherFilter, setTeacherFilter] = React.useState('');
  const [collapsedCompleted, setCollapsedCompleted] = React.useState(true);

  const fetchToday = React.useCallback((teacherId) => fetchTodayView(teacherId || undefined), []);
  const { loading, error, setError, refetch } = useApiData('/api/dashboard/today', {
    fetcher: fetchToday,
    auto: false
  });

  const lastFetchKeyRef = React.useRef('');
  React.useEffect(() => {
    if (roleLoading) return;
    const effectiveTeacherId = isAdmin && teacherIdParam ? teacherIdParam : undefined;
    const fetchKey = `${isAdmin ? 'admin' : 'user'}:${effectiveTeacherId || ''}`;
    if (lastFetchKeyRef.current === fetchKey) return;
    lastFetchKeyRef.current = fetchKey;

    if (isAdmin && teacherIdParam) {
      setTeacherFilter(teacherIdParam);
    }
    refetch(effectiveTeacherId).then(setData).catch(() => null);
  }, [isAdmin, roleLoading, teacherIdParam, refetch]);

  const onResolve = React.useCallback(
    async (actionId) => {
      try {
        await resolveInboxAction(actionId, 'Resolved from Today View');
        const payload = await refetch(isAdmin ? teacherFilter : undefined);
        setData(payload);
      } catch (err) {
        setError('Failed to resolve action.');
      }
    },
    [isAdmin, refetch, setError, teacherFilter]
  );

  const handleApplyFilter = React.useCallback(() => {
    refetch(teacherFilter)
      .then(setData)
      .catch(() => null);
  }, [refetch, teacherFilter]);

  const handleRefresh = React.useCallback(() => {
    refetch(isAdmin ? teacherFilter : undefined)
      .then(setData)
      .catch(() => null);
  }, [refetch, isAdmin, teacherFilter]);

  const handleFeesClick = React.useCallback(() => navigate('/fees'), [navigate]);
  const handleRiskClick = React.useCallback(() => navigate('/risk'), [navigate]);
  const handleAttendanceClick = React.useCallback(() => navigate('/attendance'), [navigate]);

  const overdueActions = data?.overdue_actions || [];
  const dueTodayActions = data?.due_today_actions || [];
  const todayClasses = data?.today_classes || [];
  const flags = data?.flags || { fee_due_present: [], high_risk_students: [], repeat_absentees: [] };
  const completedToday = data?.completed_today || [];

  const isLoading = roleLoading || loading;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionHeader
          title="Today View"
          subtitle={dashboardSubtitle}
          titleClassName="text-2xl font-bold"
        />
        <div className="flex items-center gap-2">
          {isAdmin ? (
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900">
              <span className="text-slate-500">Teacher ID</span>
              <input
                value={teacherFilter}
                onChange={(event) => setTeacherFilter(event.target.value)}
                className="w-24 bg-transparent text-sm text-slate-700 outline-none dark:text-slate-100"
                placeholder="All"
              />
              <button
                type="button"
                onClick={handleApplyFilter}
                className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-sky-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
              >
                Apply
              </button>
            </div>
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

      {isLoading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900">
          <LoadingState label="Loading today's actions..." />
        </div>
      ) : null}

      {!isLoading ? (
        <>
          <section className={`${sectionCard} border-l-4 border-l-rose-500`}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{sectionLabels.overdue}</h3>
              <StatusBadge variant="overdue">{overdueActions.length} overdue</StatusBadge>
            </div>
            {overdueActions.length === 0 ? (
              <EmptyState title="No overdue actions. Clear slate." />
            ) : (
              <div className="space-y-3">
                {overdueActions.map((action) => (
                  <ActionItem key={action.id} action={action} tone="overdue" onResolve={onResolve} />
                ))}
              </div>
            )}
          </section>

          <section className={`${sectionCard} border-l-4 border-l-amber-400`}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{sectionLabels.due}</h3>
              <StatusBadge variant="due">{dueTodayActions.length} due</StatusBadge>
            </div>
            {dueTodayActions.length === 0 ? (
              <EmptyState title="No actions due today." />
            ) : (
              <div className="space-y-3">
                {dueTodayActions.map((action) => (
                  <ActionItem key={action.id} action={action} tone="due" onResolve={onResolve} />
                ))}
              </div>
            )}
          </section>

          <section className={sectionCard}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{sectionLabels.classes}</h3>
              <span className="text-xs text-slate-500">{todayClasses.length} classes</span>
            </div>
            {todayClasses.length === 0 ? (
              <EmptyState title="No classes scheduled today." />
            ) : (
              <div className="space-y-3">
                {todayClasses.map((cls) => (
                  <ClassItem key={`${cls.batch_id}-${cls.schedule_id}`} item={cls} />
                ))}
              </div>
            )}
          </section>

          <section className={sectionCard}>
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{sectionLabels.flags}</h3>
              <span className="text-xs text-slate-500">Silent intelligence</span>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <FlagCard title="Fee Due (Present Today)" count={flags.fee_due_present.length} onClick={handleFeesClick} />
              <FlagCard title="High Risk Students" count={flags.high_risk_students.length} onClick={handleRiskClick} />
              <FlagCard title="Repeated Absentees" count={flags.repeat_absentees.length} onClick={handleAttendanceClick} />
            </div>
          </section>

          <section className={sectionCard}>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{sectionLabels.completed}</h3>
              <button
                type="button"
                onClick={() => setCollapsedCompleted((prev) => !prev)}
                className="text-xs font-semibold text-slate-600 dark:text-slate-300"
              >
                {collapsedCompleted ? 'Show' : 'Hide'}
              </button>
            </div>
            {!collapsedCompleted ? (
              <div className="mt-4 space-y-2">
                {completedToday.length === 0 ? (
                  <EmptyState title="Nothing resolved yet today." />
                ) : (
                  completedToday.map((action) => (
                    <CompletedItem key={action.id} action={action} />
                  ))
                )}
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500">Collapsed for focus.</p>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

const ActionItem = React.memo(function ActionItem({ action, tone, onResolve }) {
  const handleResolve = React.useCallback(() => onResolve(action.id), [onResolve, action.id]);
  const handleSummary = React.useCallback(() => {
    if (action.summary_url) {
      window.open(action.summary_url, '_blank');
    }
  }, [action.summary_url]);
  const cardTone = tone === 'overdue'
    ? 'border-rose-100 bg-rose-50 dark:border-rose-900/60 dark:bg-rose-950/40'
    : 'border-amber-100 bg-amber-50 dark:border-amber-900/60 dark:bg-amber-950/40';
  const resolveTone = tone === 'overdue' ? 'bg-rose-600' : 'bg-amber-500';

  return (
    <ActionCard className={cardTone}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900 dark:text-slate-100">{action.action_type}</p>
          {tone === 'overdue' ? (
            <p className="text-xs text-rose-600 dark:text-rose-300">
              Overdue by {action.overdue_by_hours ?? 0} hours
            </p>
          ) : null}
          {action.student_name ? (
            <p className="text-xs text-slate-500 dark:text-slate-400">Student: {action.student_name}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {action.summary_url ? (
            <button
              type="button"
              onClick={handleSummary}
              className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm dark:bg-slate-900 dark:text-slate-200"
            >
              <FiExternalLink />
              Summary
            </button>
          ) : null}
          <button
            type="button"
            onClick={handleResolve}
            className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-white ${resolveTone}`}
          >
            Resolve
          </button>
        </div>
      </div>
    </ActionCard>
  );
});

const ClassItem = React.memo(function ClassItem({ item }) {
  const handleAttendance = React.useCallback(() => {
    if (item.attendance_url) {
      window.open(item.attendance_url, '_blank');
    }
  }, [item.attendance_url]);
  const handleSummary = React.useCallback(() => {
    if (item.summary_url) {
      window.open(item.summary_url, '_blank');
    }
  }, [item.summary_url]);

  const statusText = item.attendance_status === 'submitted'
    ? '\uD83D\uDFE2 Attendance submitted'
    : item.attendance_status === 'not_started'
      ? '\u23F3 Not started'
      : '\uD83D\uDD34 Attendance pending';

  return (
    <ActionCard>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-900 dark:text-slate-100">{item.batch_name}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {new Date(item.scheduled_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} {'\u2022'} {item.duration_minutes}m
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge variant="info">{statusText}</StatusBadge>
          {item.attendance_url ? (
            <button
              type="button"
              onClick={handleAttendance}
              className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white dark:bg-slate-200 dark:text-slate-900"
            >
              Open Attendance
            </button>
          ) : null}
          {item.summary_url ? (
            <button
              type="button"
              onClick={handleSummary}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:text-slate-200"
            >
              View Summary
            </button>
          ) : null}
        </div>
      </div>
    </ActionCard>
  );
});

const FlagCard = React.memo(function FlagCard({ title, count, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-xl border border-slate-200 p-3 text-left dark:border-slate-800"
    >
      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">{title}</p>
      <p className="text-xs text-slate-500">{count} student(s)</p>
      <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-200">
        View details <FiExternalLink />
      </span>
    </button>
  );
});

const CompletedItem = React.memo(function CompletedItem({ action }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-xs dark:border-slate-800">
      <div>
        <p className="font-semibold text-slate-700 dark:text-slate-200">{action.action_type}</p>
        <p className="text-[11px] text-slate-500">{action.resolution_note || 'Resolved'}</p>
      </div>
      <FiCheckCircle className="text-emerald-500" />
    </div>
  );
});

export default Today;
