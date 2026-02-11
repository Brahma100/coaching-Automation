import React from 'react';

import ActionCard from '../components/ui/ActionCard';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import LoadingState from '../components/ui/LoadingState';
import SectionHeader from '../components/ui/SectionHeader';
import useApiData from '../hooks/useApiData';
import { fetchActions, ignoreRiskAction, notifyRiskParent, resolveAction, reviewRiskAction } from '../services/api';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function Actions() {
  const [busyId, setBusyId] = React.useState(null);
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [search, setSearch] = React.useState('');

  const { data, loading, error, setError, refetch } = useApiData('/actions/list-open', {
    fetcher: fetchActions,
    deps: [],
    transform: (payload) => normalizeList(payload?.rows ?? payload)
  });

  const rows = normalizeList(data);

  const handleRefresh = React.useCallback(() => {
    refetch().catch(() => null);
  }, [refetch]);

  const runAction = React.useCallback(
    async (id, runner) => {
      setBusyId(id);
      try {
        await runner();
        await refetch();
      } catch (err) {
        setError(err?.response?.data?.detail || err?.message || 'Action failed');
      } finally {
        setBusyId(null);
      }
    },
    [refetch, setError]
  );

  const handleResolve = React.useCallback((rowId) => runAction(`resolve-${rowId}`, () => resolveAction(rowId)), [runAction]);
  const handleReview = React.useCallback((rowId) => runAction(`review-${rowId}`, () => reviewRiskAction(rowId)), [runAction]);
  const handleNotify = React.useCallback((rowId) => runAction(`notify-${rowId}`, () => notifyRiskParent(rowId)), [runAction]);
  const handleIgnore = React.useCallback(
    (rowId) => runAction(`ignore-${rowId}`, () => {
      const note = window.prompt('Ignore note (optional):', '') || '';
      return ignoreRiskAction(rowId, note);
    }),
    [runAction]
  );

  const safeRows = normalizeList(rows);
  const filtered = safeRows.filter((row) => {
    const typeMatch = typeFilter === 'all' ? true : row.type === typeFilter;
    const text = `${row.type || ''} ${row.note || ''} ${row.student_id || ''}`.toLowerCase();
    const searchMatch = text.includes(search.toLowerCase().trim());
    return typeMatch && searchMatch;
  });

  const uniqueTypes = Array.from(new Set(safeRows.map((row) => row.type).filter(Boolean)));
  const actionCounts = uniqueTypes.map((type) => ({ type, count: safeRows.filter((row) => row.type === type).length }));

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <SectionHeader title="Actions Inbox" titleClassName="text-[30px] font-extrabold" />
          <button type="button" onClick={handleRefresh} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700">Refresh</button>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl bg-blue-50 p-3"><p className="text-xs text-blue-700">Open Actions</p><p className="text-2xl font-bold text-blue-800">{safeRows.length}</p></div>
          {actionCounts.slice(0, 3).map((item) => (
            <div key={item.type} className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs text-slate-500">{item.type}</p>
              <p className="text-2xl font-bold text-slate-800">{item.count}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1.3fr,1fr,auto]">
          <input
            placeholder="Search by type, note, student"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All Types</option>
            {uniqueTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              setTypeFilter('all');
              setSearch('');
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            Clear Filter
          </button>
        </div>

        {loading ? <LoadingState /> : null}
        <ErrorState message={error} variant="inline" />
        {!loading && !error ? (
          <ul className="space-y-2">
            {filtered.length === 0 ? <li><EmptyState title="No pending actions." /></li> : null}
            {filtered.map((row) => (
              <ActionRow
                key={row.id}
                row={row}
                busyId={busyId}
                onResolve={handleResolve}
                onReview={handleReview}
                onNotify={handleNotify}
                onIgnore={handleIgnore}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

const ActionRow = React.memo(function ActionRow({ row, busyId, onResolve, onReview, onNotify, onIgnore }) {
  const handleResolve = React.useCallback(() => onResolve(row.id), [onResolve, row.id]);
  const handleReview = React.useCallback(() => onReview(row.id), [onReview, row.id]);
  const handleNotify = React.useCallback(() => onNotify(row.id), [onNotify, row.id]);
  const handleIgnore = React.useCallback(() => onIgnore(row.id), [onIgnore, row.id]);

  return (
    <li>
      <ActionCard className="p-3">
        <p className="text-sm font-semibold">{row.type} | Student #{row.student_id || '-'}</p>
        <p className="text-xs text-slate-500">{row.note || 'No note'} | {row.created_at || '-'}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busyId === `resolve-${row.id}`}
            onClick={handleResolve}
            className="rounded bg-[#2f7bf6] px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
          >
            Resolve
          </button>
          {row.type === 'student_risk' ? (
            <>
              <button
                type="button"
                disabled={busyId === `review-${row.id}`}
                onClick={handleReview}
                className="rounded bg-emerald-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
              >
                Review
              </button>
              <button
                type="button"
                disabled={busyId === `notify-${row.id}`}
                onClick={handleNotify}
                className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
              >
                Notify Parent
              </button>
              <button
                type="button"
                disabled={busyId === `ignore-${row.id}`}
                onClick={handleIgnore}
                className="rounded bg-amber-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
              >
                Ignore
              </button>
            </>
          ) : null}
        </div>
      </ActionCard>
    </li>
  );
});

export default Actions;
