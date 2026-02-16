import React from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useDispatch, useSelector } from 'react-redux';

import { InlineSkeletonText } from '../components/Skeleton.jsx';
import {
  clearFilters,
  loadRequested,
  setDueFilter,
  setSearch,
  setSubjectFilter,
} from '../store/slices/homeworkSlice.js';

const dueColors = ['#2f7bf6', '#ef4444', '#f59e0b'];

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function Homework() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    rows,
    search,
    dueFilter,
    subjectFilter,
  } = useSelector((state) => state.homework || {});

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  const safeRows = normalizeList(rows);
  const today = new Date().toISOString().slice(0, 10);

  const subjects = Array.from(new Set(safeRows.map((row) => row.subject).filter(Boolean))).sort();

  const filtered = safeRows.filter((row) => {
    const text = `${row.title || ''} ${row.description || ''}`.toLowerCase();
    const searchMatch = text.includes(search.toLowerCase().trim());
    let dueMatch = true;
    if (dueFilter === 'today') dueMatch = row.due_date === today;
    if (dueFilter === 'overdue') dueMatch = row.due_date < today;
    if (dueFilter === 'upcoming') dueMatch = row.due_date > today;
    const subjectMatch = subjectFilter === 'all' ? true : row.subject === subjectFilter;
    return searchMatch && dueMatch && subjectMatch;
  });

  const dueStats = {
    today: safeRows.filter((row) => row.due_date === today).length,
    overdue: safeRows.filter((row) => row.due_date < today).length,
    upcoming: safeRows.filter((row) => row.due_date > today).length
  };

  const pieData = [
    { name: 'Due Today', value: dueStats.today },
    { name: 'Overdue', value: dueStats.overdue },
    { name: 'Upcoming', value: dueStats.upcoming }
  ].filter((item) => item.value > 0);

  return (
    <section className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-[30px] font-extrabold text-slate-900">Homework</h2>
          <button
            type="button"
            onClick={() => dispatch(clearFilters())}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
          >
            Clear Filter
          </button>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr,260px]">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl bg-blue-50 p-3"><p className="text-xs text-blue-700">Due Today</p><p className="text-2xl font-bold text-blue-800">{dueStats.today}</p></div>
            <div className="rounded-xl bg-rose-50 p-3"><p className="text-xs text-rose-700">Overdue</p><p className="text-2xl font-bold text-rose-800">{dueStats.overdue}</p></div>
            <div className="rounded-xl bg-amber-50 p-3"><p className="text-xs text-amber-700">Upcoming</p><p className="text-2xl font-bold text-amber-800">{dueStats.upcoming}</p></div>
          </div>
          <div className="h-40 rounded-xl border border-slate-200 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={34} outerRadius={58}>
                  {pieData.map((entry, idx) => (
                    <Cell key={entry.name} fill={dueColors[idx % dueColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1.3fr,1fr,1fr]">
          <input
            placeholder="Search title"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={search}
            onChange={(e) => dispatch(setSearch(e.target.value))}
          />
          <select value={dueFilter} onChange={(e) => dispatch(setDueFilter(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All</option>
            <option value="today">Due Today</option>
            <option value="overdue">Overdue</option>
            <option value="upcoming">Upcoming</option>
          </select>
          <select value={subjectFilter} onChange={(e) => dispatch(setSubjectFilter(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All Subjects</option>
            {subjects.map((subject) => (
              <option key={subject} value={subject}>{subject}</option>
            ))}
          </select>
        </div>

        {loading ? <InlineSkeletonText /> : null}
        {error ? <p className="text-rose-600">{error}</p> : null}
        {!loading && !error ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="px-3 py-2">Subject</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2">Due Date</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100">
                    <td className="px-3 py-2">{row.subject || '-'}</td>
                    <td className="px-3 py-2">{row.title}</td>
                    <td className="px-3 py-2">{row.description || '-'}</td>
                    <td className="px-3 py-2">{row.due_date}</td>
                  </tr>
                ))}
                {filtered.length === 0 ? <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={4}>No homework for this filter.</td></tr> : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default Homework;
