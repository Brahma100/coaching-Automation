import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useSearchParams } from 'react-router-dom';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  apiErrorToastReceived,
} from '../store/slices/appSlice.js';
import {
  consumeSessionNavigation,
  consumeTokenClear,
  hydrateFromQuery,
  loadOptionsRequested,
  loadSessionRequested,
  openSessionRequested,
  rowChanged,
  setSelectedBatchId,
  setSelectedDate,
  setSelectedScheduleId,
  submitSessionRequested,
} from '../store/slices/attendanceSlice.js';

function toToday() {
  return new Date().toISOString().slice(0, 10);
}

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeStatus(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'present') return 'Present';
  if (raw === 'absent') return 'Absent';
  if (raw === 'late') return 'Late';
  return 'Present';
}

function Attendance() {
  const dispatch = useDispatch();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryBatchId = searchParams.get('batch_id') || '';
  const queryDate = searchParams.get('date') || '';
  const queryScheduleId = searchParams.get('schedule_id') || '';
  const {
    loadingOptions,
    opening,
    loadingSheet,
    submitting,
    error,
    success,
    batches,
    schedules,
    selectedBatchId,
    selectedScheduleId,
    selectedDate,
    sheet,
    rows,
    sessionNavigationId,
    shouldClearToken,
  } = useSelector((state) => state.attendance || {});

  const sessionId = searchParams.get('session_id') || '';
  const token = searchParams.get('token') || '';
  const isFutureSelectedDate = Boolean(selectedDate && selectedDate > toToday());
  const noAvailableBatches = !loadingOptions && normalizeList(batches).length === 0;

  React.useEffect(() => {
    dispatch(
      hydrateFromQuery({
        queryBatchId,
        queryScheduleId,
        queryDate,
        today: toToday(),
      })
    );
  }, [dispatch, queryBatchId, queryScheduleId, queryDate]);

  React.useEffect(() => {
    dispatch(
      loadOptionsRequested({
        batchId: queryBatchId,
        preferredScheduleId: queryScheduleId,
        attendanceDate: queryDate || selectedDate,
      })
    );
  }, [dispatch, queryBatchId, queryScheduleId, queryDate, selectedDate]);

  React.useEffect(() => {
    if (!sessionId) return;
    dispatch(loadSessionRequested({ sessionId, token }));
  }, [dispatch, sessionId, token]);

  React.useEffect(() => {
    if (!sessionNavigationId) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set('session_id', sessionNavigationId);
    nextParams.delete('token');
    setSearchParams(nextParams);
    dispatch(consumeSessionNavigation());
  }, [dispatch, searchParams, sessionNavigationId, setSearchParams]);

  React.useEffect(() => {
    if (!shouldClearToken) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('token');
    setSearchParams(nextParams);
    dispatch(consumeTokenClear());
  }, [dispatch, searchParams, setSearchParams, shouldClearToken]);

  const clearSessionQuery = React.useCallback(() => {
    if (!searchParams.get('session_id') && !searchParams.get('token')) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete('session_id');
    nextParams.delete('token');
    setSearchParams(nextParams);
  }, [searchParams, setSearchParams]);

  const onBatchChange = async (nextBatchId) => {
    clearSessionQuery();
    dispatch(setSelectedBatchId(nextBatchId));
    dispatch(
      loadOptionsRequested({
        batchId: nextBatchId,
        preferredScheduleId: '',
        attendanceDate: selectedDate,
      })
    );
  };

  const onDateChange = async (nextDate) => {
    clearSessionQuery();
    dispatch(setSelectedDate(nextDate));
    dispatch(
      loadOptionsRequested({
        batchId: selectedBatchId,
        preferredScheduleId: selectedScheduleId,
        attendanceDate: nextDate,
      })
    );
  };

  const onScheduleChange = (nextScheduleId) => {
    clearSessionQuery();
    dispatch(setSelectedScheduleId(nextScheduleId));
  };

  const onOpenSession = async (event) => {
    event.preventDefault();
    if (isFutureSelectedDate) {
      dispatch(apiErrorToastReceived({
        tone: 'info',
        message: 'Attendance sheet can only be opened for current or past dates.',
      }));
      return;
    }
    if (!selectedBatchId) return;
    dispatch(
      openSessionRequested({
        selectedBatchId,
        selectedScheduleId,
        selectedDate,
      })
    );
  };

  const onChangeRow = (studentId, field, value) => {
    dispatch(rowChanged({ studentId, field, value }));
  };

  const onSubmit = async () => {
    if (!sessionId || !sheet?.can_edit) return;
    dispatch(
      submitSessionRequested({
        sessionId,
        token,
        records: rows.map((row) => ({
          student_id: row.student_id,
          status: normalizeStatus(row.status),
          comment: row.comment || '',
        })),
      })
    );
  };

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[30px] font-extrabold text-slate-900 dark:text-slate-100">Manage Attendance</h2>
        </div>

        {loadingOptions ? <InlineSkeletonText /> : null}
        <form onSubmit={onOpenSession} className="grid gap-3 md:grid-cols-4">
          <select
            value={selectedBatchId}
            onChange={(e) => onBatchChange(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            disabled={loadingOptions}
          >
            {normalizeList(batches).map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          />
          <select
            value={selectedScheduleId}
            onChange={(e) => onScheduleChange(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          >
            {normalizeList(schedules).map((slot) => (
              <option key={slot.id} value={slot.id}>
                Weekday {slot.weekday} | {slot.start_time} | {slot.duration_minutes} min
              </option>
            ))}
            {!normalizeList(schedules).length ? <option value="">No schedule</option> : null}
          </select>
          <button
            type="submit"
            disabled={!selectedBatchId || opening || isFutureSelectedDate}
            className="action-glow-btn rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {opening ? 'Opening...' : isFutureSelectedDate ? 'Unavailable for Future Date' : 'Open Attendance Sheet'}
          </button>
        </form>
        {noAvailableBatches ? (
          <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            No batch is scheduled on {selectedDate}. Please choose another date.
          </p>
        ) : null}
      </div>

      {error ? <p className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}
      {success ? <p className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}

      {sessionId ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          {loadingSheet ? <InlineSkeletonText /> : null}
          {sheet ? (
            <>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100">Session #{sheet.session?.id}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-300">
                    Batch {sheet.session?.batch_id} | {sheet.session?.subject} | {sheet.attendance_date}
                  </p>
                </div>
                {!sheet.can_edit ? (
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    Locked
                  </span>
                ) : null}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500 dark:border-slate-700 dark:text-slate-400">
                      <th className="px-3 py-2">Student</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Comment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {normalizeList(rows).map((row) => (
                      <tr key={row.student_id} className="border-b border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 text-slate-800 dark:text-slate-100">{row.student_name}</td>
                        <td className="px-3 py-2">
                          <select
                            value={row.status || 'Present'}
                            disabled={!sheet.can_edit}
                            onChange={(e) => onChangeRow(row.student_id, 'status', e.target.value)}
                            className="rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                          >
                            <option value="Present">Present</option>
                            <option value="Absent">Absent</option>
                            <option value="Late">Late</option>
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={row.comment || ''}
                            disabled={!sheet.can_edit}
                            onChange={(e) => onChangeRow(row.student_id, 'comment', e.target.value)}
                            className="w-full rounded-lg border border-slate-300 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                            placeholder="Optional note"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  onClick={onSubmit}
                  disabled={!sheet.can_edit || submitting}
                  className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {submitting ? 'Submitting...' : 'Submit Attendance'}
                </button>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default Attendance;
