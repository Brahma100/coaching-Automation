import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import TokenGate from '../components/TokenGate.jsx';
import { fetchAttendanceSession, submitAttendanceSession } from '../services/api';

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

function formatCountdown(expiresAt) {
  if (!expiresAt) return null;
  const now = Date.now();
  const end = new Date(expiresAt).getTime();
  if (Number.isNaN(end)) return null;
  const diffMs = end - now;
  const diffMin = Math.max(0, Math.ceil(diffMs / 60000));
  return diffMin;
}

function AttendanceToken({ expectedType, showCountdown = false }) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const sessionId = params.sessionId;

  const [loadingSheet, setLoadingSheet] = React.useState(true);
  const [sheet, setSheet] = React.useState(null);
  const [rows, setRows] = React.useState([]);
  const [error, setError] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [expiresAt, setExpiresAt] = React.useState('');
  const [tokenValid, setTokenValid] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);

  React.useEffect(() => {
    setTokenValid(false);
    if (expectedType === 'attendance_open') {
      setSubmitted(false);
      setSheet(null);
      setRows([]);
      setError('');
    }
  }, [token, sessionId, expectedType]);

  const loadSessionSheet = React.useCallback(async () => {
    if (!sessionId || !token) return;
    setLoadingSheet(true);
    try {
      const payload = await fetchAttendanceSession(sessionId, token);
      setSheet(payload || null);
      setRows(normalizeList(payload?.rows));
      setError('');
    } catch (err) {
      setSheet(null);
      setRows([]);
      setError(err?.response?.data?.detail || err?.message || 'Failed to load attendance sheet');
    } finally {
      setLoadingSheet(false);
    }
  }, [sessionId, token]);

  const onChangeRow = (studentId, field, value) => {
    setRows((prev) =>
      prev.map((row) => (row.student_id === studentId ? { ...row, [field]: value } : row))
    );
  };

  const onSubmit = async () => {
    if (!sessionId || !sheet?.can_edit) return;
    setSubmitting(true);
    try {
      await submitAttendanceSession(Number(sessionId), {
        token: token || null,
        records: rows.map((row) => ({
          student_id: row.student_id,
          status: normalizeStatus(row.status),
          comment: row.comment || ''
        }))
      });
      setSubmitted(true);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to submit attendance');
    } finally {
      setSubmitting(false);
    }
  };

  React.useEffect(() => {
    if (tokenValid) {
      loadSessionSheet();
    }
  }, [tokenValid, loadSessionSheet]);

  return (
    <TokenGate
      token={token}
      sessionId={sessionId}
      expectedType={expectedType}
      onValid={(info) => {
        setTokenValid(true);
        if (info?.expires_at) setExpiresAt(info.expires_at);
      }}
    >
      {() => {
        const countdown = showCountdown ? formatCountdown(expiresAt) : null;
        return (
          <section className="space-y-4 p-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-[28px] font-extrabold text-slate-900">Attendance</h2>
              {showCountdown && countdown !== null ? (
                <p className="mt-2 text-sm text-slate-600">
                  Editing closes in {countdown} minute{countdown === 1 ? '' : 's'}.
                </p>
              ) : null}
            </div>

            {error ? (
              <p className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
            ) : null}

            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              {loadingSheet ? <InlineSkeletonText /> : null}
              {sheet && !submitted ? (
                <>
                  <div className="mb-4">
                    <h3 className="text-xl font-bold text-slate-900">Session #{sheet.session?.id}</h3>
                    <p className="text-sm text-slate-600">
                      Batch {sheet.session?.batch_id} | {sheet.session?.subject} | {sheet.attendance_date}
                    </p>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-left text-slate-500">
                          <th className="px-3 py-2">Student</th>
                          <th className="px-3 py-2">Status</th>
                          <th className="px-3 py-2">Comment</th>
                        </tr>
                      </thead>
                      <tbody>
                        {normalizeList(rows).map((row) => (
                          <tr key={row.student_id} className="border-b border-slate-100">
                            <td className="px-3 py-2 text-slate-800">{row.student_name}</td>
                            <td className="px-3 py-2">
                              <select
                                value={row.status || 'Present'}
                                disabled={!sheet.can_edit}
                                onChange={(e) => onChangeRow(row.student_id, 'status', e.target.value)}
                                className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
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
                                className="w-full rounded-lg border border-slate-300 px-2 py-1 text-sm"
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
              {sheet && submitted ? (
                <div className="flex flex-col items-center gap-4 py-6 text-center">
                  <div className="rounded-full bg-emerald-100 p-6">
                    <svg
                      className="h-16 w-16 animate-bounce text-emerald-600"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  </div>
                  <h3 className="text-2xl font-extrabold text-slate-900">
                    Attendance for this class time slot submitted successfully.
                  </h3>
                  <p className="text-sm text-slate-600">You can review it on the Dashboard.</p>
                </div>
              ) : null}
            </div>
          </section>
        );
      }}
    </TokenGate>
  );
}

export default AttendanceToken;
