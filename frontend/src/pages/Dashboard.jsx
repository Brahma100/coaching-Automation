import React from 'react';
import { FaBookReader, FaRegStar, FaUserCheck, FaUserGraduate, FaUserTimes } from 'react-icons/fa';
import { GiAchievement } from 'react-icons/gi';
import { FiArrowRight, FiZap } from 'react-icons/fi';
import { MdWarningAmber } from 'react-icons/md';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import { PageSkeleton } from '../components/Skeleton.jsx';
import {
  loadRequested as dashboardLoadRequested,
  setSelectedBatchId,
  setSelectedMonth,
} from '../store/slices/dashboardSlice.js';
import { loadRequested as brainLoadRequested } from '../store/slices/brainSlice.js';

const skillColors = ['#10b981', '#f97316', '#06b6d4', '#f43f5e'];
const perfColors = ['#10b981', '#f97316', '#ec4899', '#0ea5e9'];
const PIE_ANIM_DURATION = 1250;

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function monthKeyFromDate(value) {
  if (!value) return '';
  const text = String(value);
  if (/^\d{4}-\d{2}/.test(text)) {
    return text.slice(0, 7);
  }
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }
  const month = String(parsed.getMonth() + 1).padStart(2, '0');
  return `${parsed.getFullYear()}-${month}`;
}

function formatMonthKey(monthKey) {
  if (!monthKey) return 'Unknown';
  const parsed = new Date(`${monthKey}-01T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return monthKey;
  return new Intl.DateTimeFormat('en-US', { month: 'long', year: 'numeric' }).format(parsed);
}

function Dashboard() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    data,
    selectedBatchId,
    selectedMonth,
  } = useSelector((state) => state.dashboard || {});
  const { data: brainData, loading: brainLoading } = useSelector((state) => state.brain || {});

  React.useEffect(() => {
    dispatch(dashboardLoadRequested());
    dispatch(brainLoadRequested());
  }, [dispatch]);

  if (loading) {
    return <PageSkeleton />;
  }

  if (error) {
    return <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700">{error}</div>;
  }

  const students = normalizeList(data?.students);
  const batches = normalizeList(data?.batches);
  const feesRaw = data?.fees && typeof data.fees === 'object' ? data.fees : {};
  const dueBase = normalizeList(feesRaw.due);
  const overdueBase = normalizeList(feesRaw.overdue);
  const paidBase = normalizeList(feesRaw.paid);
  const riskBase = normalizeList(data?.risk);
  const actionsBase = normalizeList(data?.actions);
  const briefMonthKey = monthKeyFromDate(data?.brief?.date || data?.brief?.generated_at);

  const availableMonths = (() => {
    const bucket = new Set();
    [briefMonthKey].filter(Boolean).forEach((item) => bucket.add(item));
    dueBase.forEach((row) => {
      const key = monthKeyFromDate(row.due_date);
      if (key) bucket.add(key);
    });
    overdueBase.forEach((row) => {
      const key = monthKeyFromDate(row.due_date);
      if (key) bucket.add(key);
    });
    paidBase.forEach((row) => {
      const key = monthKeyFromDate(row.due_date);
      if (key) bucket.add(key);
    });
    actionsBase.forEach((row) => {
      const key = monthKeyFromDate(row.created_at || row.date);
      if (key) bucket.add(key);
    });
    riskBase.forEach((row) => {
      const key = monthKeyFromDate(row.last_computed_at);
      if (key) bucket.add(key);
    });
    return Array.from(bucket).sort((a, b) => b.localeCompare(a));
  })();

  const matchesMonth = (value) => selectedMonth === 'all' || monthKeyFromDate(value) === selectedMonth;
  const filteredStudents = selectedBatchId === 'all'
    ? students
    : students.filter((row) => String(row.batch_id) === selectedBatchId);
  const selectedStudentIds = new Set(filteredStudents.map((row) => String(row.id)));

  const filterByClass = (rows, idField = 'student_id') => {
    if (selectedBatchId === 'all') return rows;
    return rows.filter((row) => selectedStudentIds.has(String(row[idField])));
  };

  const due = filterByClass(dueBase.filter((row) => matchesMonth(row.due_date)));
  const overdue = filterByClass(overdueBase.filter((row) => matchesMonth(row.due_date)));
  const paid = filterByClass(paidBase.filter((row) => matchesMonth(row.due_date)));
  const riskRows = filterByClass(riskBase.filter((row) => matchesMonth(row.last_computed_at)));
  const actions = filterByClass(actionsBase.filter((row) => matchesMonth(row.created_at || row.date)));

  const totalStudents = filteredStudents.length;
  const struggling = Math.max(riskRows.filter((r) => (r.risk_level || '').toUpperCase() === 'HIGH').length, 0);
  const excelling = Math.max(riskRows.filter((r) => (r.risk_level || '').toUpperCase() === 'LOW').length, 0);
  const attendancePercent = Math.max(
    Math.min(
      Math.round(((totalStudents - (data?.brief?.absent_students?.count || 0)) / Math.max(totalStudents, 1)) * 100),
      100
    ),
    0
  );

  const skillData = [
    { name: 'Advanced', value: Math.max(excelling, 1) },
    { name: 'Basic', value: Math.max(overdue.length, 1) },
    { name: 'Proficient', value: Math.max(paid.length, 1) },
    { name: 'Intermediate', value: Math.max(totalStudents - excelling - struggling, 1) }
  ];

  const summaryData = [
    { name: 'Completed', value: Math.max(paid.length, 1) },
    { name: 'Lagging', value: Math.max(struggling, 1) },
    { name: 'On Track', value: Math.max(due.length, 1) },
    { name: 'Ahead', value: Math.max(excelling, 1) }
  ];

  const topStudents = filteredStudents.slice(0, 4).map((s, idx) => ({
    id: s.id,
    name: s.name,
    status: ['Lagging', 'On Track', 'Ahead', 'Completed'][idx % 4],
    tone: ['bg-orange-100 text-orange-600', 'bg-pink-100 text-pink-600', 'bg-sky-100 text-sky-600', 'bg-emerald-100 text-emerald-600'][idx % 4]
  }));

  const strugglingList = filteredStudents.slice(0, 3);
  const excellingList = filteredStudents.slice(3, 6);
  const activePeriodLabel = selectedMonth === 'all'
    ? 'All Months'
    : formatMonthKey(selectedMonth);
  const brainNextClass = brainData?.next_upcoming_class || null;
  const brainPendingCount = Array.isArray(brainData?.pending_inbox_actions) ? brainData.pending_inbox_actions.length : 0;
  const brainRiskCount = (() => {
    const risk = brainData?.risk_students || {};
    return (risk.high_risk?.length || 0) + (risk.fee_overdue?.length || 0) + (risk.repeat_absentees?.length || 0);
  })();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-3xl font-extrabold text-slate-900 sm:text-[34px]">Dashboard</h2>
        <select
          value={selectedBatchId}
          onChange={(e) => dispatch(setSelectedBatchId(e.target.value))}
          className="w-full rounded-lg bg-white px-4 py-2 text-sm font-semibold text-[#2f7bf6] shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:text-[#66a3ff] sm:w-auto"
        >
          <option value="all">All Classes</option>
          {batches.map((batch) => (
            <option key={batch.id} value={batch.id}>{batch.name}</option>
          ))}
        </select>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr,.85fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-2xl font-bold text-slate-900 sm:text-[26px]">Class Statistics</h3>
            <select
              value={selectedMonth}
              onChange={(e) => dispatch(setSelectedMonth(e.target.value))}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 dark:bg-slate-900 dark:text-slate-300 sm:w-auto"
            >
              <option value="all">All Months</option>
              {availableMonths.map((monthKey) => (
                <option key={monthKey} value={monthKey}>{formatMonthKey(monthKey)}</option>
              ))}
            </select>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-[#f8fbff] p-3 text-center">
              <div className="mx-auto mb-2 grid h-14 w-14 place-items-center rounded-full bg-[#e7f0ff] text-[#2f7bf6]">
                <FaUserGraduate className="h-7 w-7" />
              </div>
              <p className="text-4xl font-extrabold">{totalStudents}</p>
              <p className="text-xs text-slate-500">Total Students</p>
            </div>
            <div className="rounded-xl bg-[#fff8f2] p-3 text-center">
              <div className="mx-auto mb-2 grid h-14 w-14 place-items-center rounded-full bg-[#ffe9d7] text-[#b45309]">
                <FaUserTimes className="h-7 w-7" />
              </div>
              <p className="text-4xl font-extrabold">{struggling}</p>
              <p className="text-xs text-slate-500">Struggling</p>
            </div>
            <div className="rounded-xl bg-[#f2fff7] p-3 text-center">
              <div className="mx-auto mb-2 grid h-14 w-14 place-items-center rounded-full bg-[#dff7ea] text-[#047857]">
                <FaUserCheck className="h-7 w-7" />
              </div>
              <p className="text-4xl font-extrabold">{excelling}</p>
              <p className="text-xs text-slate-500">Excelling</p>
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-[#f8fafc] p-4">
            <div className="mb-2 flex items-center justify-between text-sm font-semibold text-slate-600">
              <span>Class Progress</span>
              <span>{attendancePercent}% of the progress</span>
            </div>
            <div className="mb-2 flex items-center gap-2 text-slate-500">
              <FaBookReader className="h-5 w-5" />
              <span className="text-xs">A-Z Learning Progress</span>
            </div>
            <div className="h-2 rounded-full bg-slate-200">
              <div className="h-2 rounded-full bg-[#20a8f4]" style={{ width: `${attendancePercent}%` }} />
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-2xl font-bold text-slate-900 sm:text-[26px]">Overall Class Performance</h3>
            <button className="rounded-lg px-2 py-1 text-sm font-semibold text-slate-500">View Details &gt;</button>
          </div>

          <div className="grid gap-2 md:grid-cols-[220px,1fr]">
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={skillData}
                    dataKey="value"
                    innerRadius={42}
                    outerRadius={74}
                    paddingAngle={2}
                    isAnimationActive
                    animationBegin={80}
                    animationDuration={PIE_ANIM_DURATION}
                    animationEasing="ease-out"
                  >
                    {skillData.map((entry, index) => (
                      <Cell key={`${entry.name}-${index}`} fill={skillColors[index % skillColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="grid content-center gap-2 text-sm">
              {skillData.map((item, index) => (
                <div key={item.name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: skillColors[index % skillColors.length] }} />
                    <span>{item.name}</span>
                  </div>
                  <span className="font-bold">{Math.round((item.value / Math.max(totalStudents, 1)) * 100)}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 space-y-2">
            <p className="text-sm font-semibold text-slate-700">Top Students</p>
            {topStudents.map((student, idx) => (
              <div key={student.id || student.name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-3">
                  <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-slate-700 to-slate-500 text-xs font-bold text-white">{(student.name || 'S').charAt(0)}</div>
                  <p className="font-semibold text-slate-700">{student.name || `Student ${idx + 1}`}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${student.tone}`}>{student.status}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-sky-100 bg-gradient-to-r from-sky-50 to-indigo-50 p-4 shadow-sm dark:border-slate-700 dark:from-slate-900 dark:to-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">
              <FiZap className="h-3.5 w-3.5" />
              Operational Brain Preview
            </p>
            <h3 className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">
              {brainLoading ? 'Loading live intelligence...' : (brainNextClass ? `${brainNextClass.batch_name} is coming up` : 'No class in next 2 hours')}
            </h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Pending actions: {brainPendingCount} | Risk signals: {brainRiskCount}
            </p>
          </div>
          <Link to="/brain" className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white">
            Open /brain <FiArrowRight />
          </Link>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.15fr,.85fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-2xl font-bold text-slate-900 sm:text-[26px]">Struggling & Excelling</h3>
            <button className="rounded-lg px-2 py-1 text-sm font-semibold text-slate-500">View Details &gt;</button>
          </div>

          <div className="space-y-4">
            <div>
              <p className="mb-2 flex items-center gap-2 text-sm font-bold text-rose-500">
                <MdWarningAmber /> Bottom 3 Struggling
              </p>
              <div className="space-y-2">
                {strugglingList.map((student, idx) => (
                  <div key={`s-${student.id || idx}`} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
                    <div>
                      <p className="font-semibold text-slate-700">{student.name}</p>
                      <p className="text-xs text-slate-500">Science, Biology</p>
                    </div>
                    <button className="rounded-full border border-[#2f7bf6] px-4 py-1 text-xs font-semibold text-[#2f7bf6]">View</button>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 flex items-center gap-2 text-sm font-bold text-amber-500">
                <FaRegStar /> Top 3 Excelling
              </p>
              <div className="space-y-2">
                {excellingList.map((student, idx) => (
                  <div key={`e-${student.id || idx}`} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
                    <div>
                      <p className="font-semibold text-slate-700">{student.name}</p>
                      <p className="text-xs text-slate-500">History, English</p>
                    </div>
                    <button className="rounded-full border border-[#2f7bf6] px-4 py-1 text-xs font-semibold text-[#2f7bf6]">View</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-2xl font-bold text-slate-900 sm:text-[26px]">Performance Summary</h3>
            <button className="rounded-lg px-2 py-1 text-sm font-semibold text-slate-500">View Details &gt;</button>
          </div>

          <div className="grid gap-2 md:grid-cols-[220px,1fr]">
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={summaryData}
                    dataKey="value"
                    innerRadius={42}
                    outerRadius={74}
                    startAngle={180}
                    endAngle={0}
                    isAnimationActive
                    animationBegin={180}
                    animationDuration={PIE_ANIM_DURATION}
                    animationEasing="ease-out"
                  >
                    {summaryData.map((entry, index) => (
                      <Cell key={`${entry.name}-${index}`} fill={perfColors[index % perfColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <p className="-mt-6 text-center text-xl font-extrabold text-emerald-500">{attendancePercent}%</p>
            </div>

            <div className="grid content-center gap-3">
              <div className="rounded-xl bg-slate-50 px-3 py-3">
                <p className="text-sm text-slate-500">Proficient</p>
                <div className="flex items-center justify-between">
                  <p className="text-lg font-bold">Average Proficiency</p>
                  <GiAchievement className="h-8 w-8 text-amber-500" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {summaryData.map((item, idx) => (
                  <div key={item.name} className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="font-bold" style={{ color: perfColors[idx % perfColors.length] }}>{item.name}</p>
                    <p className="text-slate-500">{item.value} students</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        <strong>Notifications ({activePeriodLabel}):</strong> {actions.length} action item(s) pending. {due.length + overdue.length} fee item(s) need follow-up.
      </div>
    </div>
  );
}

export default Dashboard;
