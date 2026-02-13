import React from 'react';
import { useSearchParams } from 'react-router-dom';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  fetchAttendanceManageOptions,
  fetchAttendanceSession,
  notifyGlobalToast,
  openAttendanceSession,
  submitAttendanceSession
} from '../services/api';

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
  const [searchParams, setSearchParams] = useSearchParams();
  const queryBatchId = searchParams.get('batch_id') || '';
  const queryDate = searchParams.get('date') || '';
  const queryScheduleId = searchParams.get('schedule_id') || '';
  const [loadingOptions, setLoadingOptions] = React.useState(true);
  const [opening, setOpening] = React.useState(false);
  const [loadingSheet, setLoadingSheet] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState('');

  const [batches, setBatches] = React.useState([]);
  const [schedules, setSchedules] = React.useState([]);
  const [selectedBatchId, setSelectedBatchId] = React.useState(queryBatchId || '');
  const [selectedScheduleId, setSelectedScheduleId] = React.useState(queryScheduleId || '');
  const [selectedDate, setSelectedDate] = React.useState(queryDate || toToday());

  const [sheet, setSheet] = React.useState(null);
  const [rows, setRows] = React.useState([]);

  const sessionId = searchParams.get('session_id') || '';
  const token = searchParams.get('token') || '';
  const isFutureSelectedDate = Boolean(selectedDate && selectedDate > toToday());

  const loadOptions = React.useCallback(async (batchId = '', preferredScheduleId = '') => {
    setLoadingOptions(true);
    try {
      const payload = await fetchAttendanceManageOptions(batchId);
      const batchRows = normalizeList(payload?.batches);
      const scheduleRows = normalizeList(payload?.schedules);
      setBatches(batchRows);
      const resolvedBatchId = String(payload?.selected_batch_id || batchRows[0]?.id || '');
      setSelectedBatchId(resolvedBatchId);
      setSchedules(scheduleRows);
      const matchSchedule = String(preferredScheduleId || '');
      const hasPreferredSchedule = Boolean(matchSchedule && scheduleRows.some((slot) => String(slot.id) === matchSchedule));
      setSelectedScheduleId(hasPreferredSchedule ? matchSchedule : String(scheduleRows[0]?.id || ''));
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load attendance options');
    } finally {
      setLoadingOptions(false);
    }
  }, []);

  const loadSessionSheet = React.useCallback(async (id, tkn = '') => {
    if (!id) return;
    setLoadingSheet(true);
    try {
      const payload = await fetchAttendanceSession(id, tkn);
      setSheet(payload || null);
      setRows(normalizeList(payload?.rows));
      const sessionBatchId = String(payload?.session?.batch_id || '');
      if (sessionBatchId) setSelectedBatchId(sessionBatchId);
      if (payload?.attendance_date) setSelectedDate(String(payload.attendance_date));
      setError('');
    } catch (err) {
      setSheet(null);
      setRows([]);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load attendance sheet');
    } finally {
      setLoadingSheet(false);
    }
  }, []);

  React.useEffect(() => {
    loadOptions(queryBatchId, queryScheduleId);
  }, [loadOptions, queryBatchId, queryScheduleId]);

  React.useEffect(() => {
    if (!sessionId) return;
    loadSessionSheet(sessionId, token);
  }, [sessionId, token, loadSessionSheet]);

  const onBatchChange = async (nextBatchId) => {
    setSelectedBatchId(nextBatchId);
    await loadOptions(nextBatchId);
  };

  const onOpenSession = async (event) => {
    event.preventDefault();
    if (isFutureSelectedDate) {
      notifyGlobalToast({
        tone: 'info',
        message: 'Attendance sheet can only be opened for current or past dates.',
      });
      return;
    }
    if (!selectedBatchId) return;
    setOpening(true);
    setSuccess('');
    try {
      const payload = await openAttendanceSession({
        batch_id: Number(selectedBatchId),
        schedule_id: selectedScheduleId ? Number(selectedScheduleId) : null,
        attendance_date: selectedDate
      });
      const nextId = String(payload?.session_id || '');
      if (!nextId) throw new Error('Session id missing in response');
      const nextParams = new URLSearchParams(searchParams);
      nextParams.set('session_id', nextId);
      nextParams.delete('token');
      setSearchParams(nextParams);
      await loadSessionSheet(nextId, '');
      setSuccess('Attendance sheet opened.');
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to open attendance sheet');
    } finally {
      setOpening(false);
    }
  };

  const onChangeRow = (studentId, field, value) => {
    setRows((prev) =>
      prev.map((row) => (row.student_id === studentId ? { ...row, [field]: value } : row))
    );
  };

  const onSubmit = async () => {
    if (!sessionId || !sheet?.can_edit) return;
    setSubmitting(true);
    setSuccess('');
    try {
      await submitAttendanceSession(Number(sessionId), {
        token: token || null,
        records: rows.map((row) => ({
          student_id: row.student_id,
          status: normalizeStatus(row.status),
          comment: row.comment || ''
        }))
      });
      await loadSessionSheet(sessionId, '');
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete('token');
      setSearchParams(nextParams);
      setSuccess('Attendance submitted. Session is now locked.');
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to submit attendance');
    } finally {
      setSubmitting(false);
    }
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
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          />
          <select
            value={selectedScheduleId}
            onChange={(e) => setSelectedScheduleId(e.target.value)}
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
