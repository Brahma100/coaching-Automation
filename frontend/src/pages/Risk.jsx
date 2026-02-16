import React from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useDispatch, useSelector } from 'react-redux';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  clearFilters,
  loadRequested,
  setLevelFilter,
  setSearch,
} from '../store/slices/riskSlice.js';

const riskColors = {
  HIGH: '#ef4444',
  MEDIUM: '#f59e0b',
  LOW: '#10b981',
  UNKNOWN: '#94a3b8'
};

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function Risk() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    rows,
    levelFilter,
    search,
  } = useSelector((state) => state.risk || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const safeRows = normalizeList(rows);
  const riskStats = safeRows.reduce(
    (acc, row) => {
      const key = String(row.risk_level || 'UNKNOWN').toUpperCase();
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    { HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 }
  );

  const pieData = Object.entries(riskStats)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({ name, value, color: riskColors[name] || riskColors.UNKNOWN }));

  const filtered = safeRows.filter((row) => {
    const level = String(row.risk_level || '').toUpperCase();
    const levelMatch = levelFilter === 'all' ? true : level === levelFilter;
    const text = `${row.student_name || ''} ${row.student_id || ''}`.toLowerCase();
    const searchMatch = text.includes(search.toLowerCase().trim());
    return levelMatch && searchMatch;
  });

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[30px] font-extrabold text-slate-900">Risk Monitor</h2>
          <button
            type="button"
            onClick={() => dispatch(clearFilters())}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            Clear Filter
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr,260px]">
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl bg-rose-50 p-3"><p className="text-xs text-rose-700">High</p><p className="text-2xl font-bold text-rose-800">{riskStats.HIGH}</p></div>
            <div className="rounded-xl bg-amber-50 p-3"><p className="text-xs text-amber-700">Medium</p><p className="text-2xl font-bold text-amber-800">{riskStats.MEDIUM}</p></div>
            <div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Low</p><p className="text-2xl font-bold text-emerald-800">{riskStats.LOW}</p></div>
            <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Total</p><p className="text-2xl font-bold text-slate-800">{safeRows.length}</p></div>
          </div>
          <div className="h-40 rounded-xl border border-slate-200 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={34} outerRadius={58}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1.4fr,1fr,auto]">
          <input
            placeholder="Search student"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={search}
            onChange={(e) => dispatch(setSearch(e.target.value))}
          />
          <select value={levelFilter} onChange={(e) => dispatch(setLevelFilter(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All Levels</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
          <button type="button" className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700" onClick={() => dispatch(loadRequested())}>Refresh View</button>
        </div>

        {loading ? <InlineSkeletonText /> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
        {!loading && !error ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-3 py-2">Student</th>
                  <th className="px-3 py-2">Risk Level</th>
                  <th className="px-3 py-2">Score</th>
                  <th className="px-3 py-2">Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.student_id || row.id} className="border-b border-slate-100">
                    <td className="px-3 py-2">{row.student_name || row.student_id}</td>
                    <td className="px-3 py-2">{row.risk_level}</td>
                    <td className="px-3 py-2">{row.final_risk_score}</td>
                    <td className="px-3 py-2">{row.last_computed_at || '-'}</td>
                  </tr>
                ))}
                {filtered.length === 0 ? <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={4}>No students for selected filter.</td></tr> : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default Risk;
