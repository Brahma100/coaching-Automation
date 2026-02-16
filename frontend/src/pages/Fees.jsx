import React from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useDispatch, useSelector } from 'react-redux';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  clearFilters,
  loadRequested,
  setMonthFilter,
  setSearch,
  setStatusFilter,
} from '../store/slices/feesSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function Fees() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    fees,
    search,
    statusFilter,
    monthFilter,
  } = useSelector((state) => state.fees || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const overdue = normalizeList(fees.overdue);
  const due = normalizeList(fees.due);
  const paid = normalizeList(fees.paid);

  const rows = [...overdue, ...due, ...paid].map((row) => {
    const today = new Date().toISOString().slice(0, 10);
    const status = row.is_paid ? 'paid' : row.due_date < today ? 'overdue' : 'due';
    const month = String(row.due_date || '').slice(0, 7) || 'unknown';
    return { ...row, computed_status: status, due_month: month };
  });

  const uniqueMonths = Array.from(new Set(rows.map((row) => row.due_month))).filter((month) => month && month !== 'unknown').sort();

  const filtered = rows.filter((row) => {
    const text = `${row.student_name || ''} ${row.student_id || ''}`.toLowerCase();
    const searchMatch = text.includes(search.toLowerCase().trim());
    const statusMatch = statusFilter === 'all' ? true : row.computed_status === statusFilter;
    const monthMatch = monthFilter === 'all' ? true : row.due_month === monthFilter;
    return searchMatch && statusMatch && monthMatch;
  });

  const totals = filtered.reduce(
    (acc, row) => {
      acc.total += Number(row.amount || 0);
      acc.paid += Number(row.paid_amount || 0);
      return acc;
    },
    { total: 0, paid: 0 }
  );
  const dueAmount = Math.max(totals.total - totals.paid, 0);

  const trendMap = filtered.reduce((acc, row) => {
    const key = row.due_month || 'Unknown';
    if (!acc[key]) {
      acc[key] = { month: key, paid: 0, due: 0, overdue: 0 };
    }
    acc[key][row.computed_status] += 1;
    return acc;
  }, {});

  const trendData = Object.values(trendMap);

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[30px] font-extrabold text-slate-900">Fees</h2>
          <button
            type="button"
            onClick={() => dispatch(clearFilters())}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            Clear Filter
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Paid Items</p><p className="text-2xl font-bold text-emerald-800">{paid.length}</p></div>
          <div className="rounded-xl bg-amber-50 p-3"><p className="text-xs text-amber-700">Due Items</p><p className="text-2xl font-bold text-amber-800">{due.length}</p></div>
          <div className="rounded-xl bg-rose-50 p-3"><p className="text-xs text-rose-700">Overdue Items</p><p className="text-2xl font-bold text-rose-800">{overdue.length}</p></div>
          <div className="rounded-xl bg-blue-50 p-3"><p className="text-xs text-blue-700">Outstanding Amount</p><p className="text-2xl font-bold text-blue-800">{dueAmount.toFixed(0)}</p></div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1.2fr,1fr,1fr]">
          <input
            placeholder="Search student"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={search}
            onChange={(e) => dispatch(setSearch(e.target.value))}
          />
          <select value={statusFilter} onChange={(e) => dispatch(setStatusFilter(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All Status</option>
            <option value="paid">Paid</option>
            <option value="due">Due</option>
            <option value="overdue">Overdue</option>
          </select>
          <select value={monthFilter} onChange={(e) => dispatch(setMonthFilter(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All Months</option>
            {uniqueMonths.map((month) => (
              <option key={month} value={month}>{month}</option>
            ))}
          </select>
        </div>

        <div className="mb-4 h-56 rounded-xl border border-slate-200 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="paid" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="due" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="overdue" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {loading ? <InlineSkeletonText /> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
        {!loading && !error ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-3 py-2">Student</th>
                  <th className="px-3 py-2">Due Date</th>
                  <th className="px-3 py-2">Amount</th>
                  <th className="px-3 py-2">Paid</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100">
                    <td className="px-3 py-2">{row.student_name || row.student_id}</td>
                    <td className="px-3 py-2">{row.due_date}</td>
                    <td className="px-3 py-2">{row.amount}</td>
                    <td className="px-3 py-2">{row.paid_amount}</td>
                    <td className="px-3 py-2 capitalize">{row.computed_status}</td>
                  </tr>
                ))}
                {filtered.length === 0 ? <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={5}>No fee rows for selected filter.</td></tr> : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default Fees;
