import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import TokenGate from '../components/TokenGate.jsx';
import { fetchSessionSummary } from '../services/api';

function SessionSummaryToken() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const sessionId = params.sessionId;
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [summary, setSummary] = React.useState(null);

  const loadSummary = React.useCallback(async () => {
    if (!sessionId || !token) return;
    setLoading(true);
    try {
      const payload = await fetchSessionSummary(sessionId, token);
      setSummary(payload || null);
      setError('');
    } catch (err) {
      setSummary(null);
      setError(err?.response?.data?.detail || err?.message || 'Session summary unavailable.');
    } finally {
      setLoading(false);
    }
  }, [sessionId, token]);

  return (
    <TokenGate
      token={token}
      sessionId={sessionId}
      expectedType="session_summary"
      onValid={() => loadSummary()}
    >
      {() => (
        <section className="space-y-4 p-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-2xl font-bold text-slate-900">Session Summary</h2>
            {summary ? (
              <p className="mt-1 text-sm text-slate-600">
                Batch {summary.session?.batch_id} | {summary.session?.subject} | {summary.attendance_date}
              </p>
            ) : null}
          </div>

          {loading ? <InlineSkeletonText /> : null}
          {error ? (
            <p className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
          ) : null}

          {summary ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                      <th className="px-3 py-2">Student</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Comment</th>
                      <th className="px-3 py-2">Fee Due</th>
                      <th className="px-3 py-2">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.rows?.map((row) => (
                      <tr key={row.student_id} className="border-b border-slate-100">
                        <td className="px-3 py-2 text-slate-800">{row.student_name}</td>
                        <td className="px-3 py-2">{row.status}</td>
                        <td className="px-3 py-2">{row.comment || '-'}</td>
                        <td className="px-3 py-2">{row.fee_due ?? 0}</td>
                        <td className="px-3 py-2">
                          {row.risk_level}
                          {row.risk_score !== null && row.risk_score !== undefined ? ` (${row.risk_score})` : ''}
                        </td>
                      </tr>
                    ))}
                    {!summary.rows?.length ? (
                      <tr>
                        <td className="px-3 py-4 text-center text-slate-500" colSpan={5}>
                          No summary data.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </section>
      )}
    </TokenGate>
  );
}

export default SessionSummaryToken;
