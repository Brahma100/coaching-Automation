import React from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import Modal from '../components/Modal.jsx';
import { PageSkeleton } from '../components/Skeleton.jsx';
import { createReferral, createStudent, deleteStudent, fetchBatches, fetchStudents, updateStudent } from '../services/api';

const pieColors = ['#2f7bf6', '#10b981'];

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function Students() {
  const [state, setState] = React.useState({ loading: true, error: '', rows: [] });
  const [batches, setBatches] = React.useState([]);
  const [busyId, setBusyId] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [batchFilter, setBatchFilter] = React.useState('all');

  const [formOpen, setFormOpen] = React.useState(false);
  const [formMode, setFormMode] = React.useState('add');
  const [editingStudent, setEditingStudent] = React.useState(null);
  const [formData, setFormData] = React.useState({ name: '', phone: '', batch_id: '', parent_phone: '' });

  const [deleteOpen, setDeleteOpen] = React.useState(false);
  const [deleteStudentRow, setDeleteStudentRow] = React.useState(null);

  const loadAll = React.useCallback(async () => {
    try {
      const [studentsPayload, batchesPayload] = await Promise.all([fetchStudents(), fetchBatches().catch(() => [])]);
      const rows = normalizeList(studentsPayload?.rows ?? studentsPayload);
      const nextBatches = normalizeList(batchesPayload?.rows ?? batchesPayload);
      setState({ loading: false, error: '', rows });
      setBatches(nextBatches);
      if (!formData.batch_id && nextBatches[0]?.id) {
        setFormData((prev) => ({ ...prev, batch_id: String(nextBatches[0].id) }));
      }
    } catch (err) {
      setState({ loading: false, error: err?.response?.data?.detail || err?.message || 'Failed to load students', rows: [] });
    }
  }, [formData.batch_id]);

  React.useEffect(() => {
    loadAll();
  }, [loadAll]);

  const rows = normalizeList(state.rows);
  const safeBatches = normalizeList(batches);

  const filteredRows = rows.filter((row) => {
    const text = `${row.name || ''} ${row.phone || ''} ${row.parent_phone || ''}`.toLowerCase();
    const searchMatch = text.includes(search.toLowerCase().trim());
    const batchMatch = batchFilter === 'all' ? true : String(row.batch_id) === batchFilter;
    return searchMatch && batchMatch;
  });

  const batchStatsMap = filteredRows.reduce((acc, row) => {
    const key = row.batch || `Batch ${row.batch_id}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  const batchChartData = Object.entries(batchStatsMap).map(([name, count]) => ({ name, count }));
  const withParent = filteredRows.filter((row) => (row.parent_phone || '').trim()).length;
  const withoutParent = Math.max(filteredRows.length - withParent, 0);
  const parentPieData = [
    { name: 'Parent Linked', value: withParent },
    { name: 'Missing Parent', value: withoutParent }
  ];

  const openAddForm = () => {
    setFormMode('add');
    setEditingStudent(null);
    setFormData({
      name: '',
      phone: '',
      batch_id: String(safeBatches[0]?.id || ''),
      parent_phone: ''
    });
    setFormOpen(true);
  };

  const openEditForm = (row) => {
    setFormMode('edit');
    setEditingStudent(row);
    setFormData({
      name: row.name || '',
      phone: row.phone || row.guardian_phone || '',
      batch_id: String(row.batch_id || ''),
      parent_phone: row.parent_phone || ''
    });
    setFormOpen(true);
  };

  const onSubmitForm = async (event) => {
    event.preventDefault();
    if (!formData.name.trim() || !formData.batch_id) {
      return;
    }

    setBusyId('save-form');
    try {
      if (formMode === 'add') {
        await createStudent(formData);
      } else if (editingStudent) {
        await updateStudent(editingStudent.id, {
          name: formData.name,
          phone: formData.phone,
          batch_id: Number(formData.batch_id),
          parent_phone: formData.parent_phone
        });
      }
      setFormOpen(false);
      await loadAll();
    } catch (err) {
      setState((prev) => ({ ...prev, error: err?.response?.data?.detail || err?.message || 'Save failed' }));
    } finally {
      setBusyId(null);
    }
  };

  const openDeleteModal = (row) => {
    setDeleteStudentRow(row);
    setDeleteOpen(true);
  };

  const onConfirmDelete = async () => {
    if (!deleteStudentRow) return;
    setBusyId(`delete-${deleteStudentRow.id}`);
    try {
      await deleteStudent(deleteStudentRow.id);
      setDeleteOpen(false);
      setDeleteStudentRow(null);
      await loadAll();
    } catch (err) {
      setState((prev) => ({ ...prev, error: err?.response?.data?.detail || err?.message || 'Delete failed' }));
    } finally {
      setBusyId(null);
    }
  };

  const onAddReferral = async (studentId) => {
    setBusyId(`ref-${studentId}`);
    try {
      await createReferral(studentId);
      window.alert('Referral created successfully.');
    } catch (err) {
      setState((prev) => ({ ...prev, error: err?.response?.data?.detail || err?.message || 'Referral failed' }));
    } finally {
      setBusyId(null);
    }
  };

  if (state.loading) {
    return <PageSkeleton />;
  }

  return (
    <section className="space-y-4">
      {state.error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{state.error}</div> : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-700">Students by Batch</h3>
            <span className="text-xs text-slate-500">Top Overview</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={batchChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2f7bf6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-700">Parent Link Coverage</h3>
            <span className="text-xs text-slate-500">Quality Check</span>
          </div>
          <div className="grid h-auto gap-2 sm:h-48 sm:grid-cols-[180px,1fr]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={parentPieData} dataKey="value" innerRadius={40} outerRadius={70}>
                  {parentPieData.map((entry, index) => (
                    <Cell key={entry.name} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {parentPieData.map((item, idx) => (
                <div key={item.name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: pieColors[idx] }} />
                    {item.name}
                  </span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-extrabold text-slate-900 sm:text-[30px]">Students</h2>
          <button
            type="button"
            onClick={openAddForm}
            className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white hover:bg-[#225fca]"
          >
            Add Student
          </button>
        </div>

        <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1.2fr,1fr,auto]">
          <input
            placeholder="Search by student/phone/parent"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={batchFilter}
            onChange={(e) => setBatchFilter(e.target.value)}
          >
            <option value="all">All Batches</option>
            {safeBatches.map((batch) => (
              <option key={batch.id} value={batch.id}>{batch.name}</option>
            ))}
          </select>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={() => {
              setSearch('');
              setBatchFilter('all');
            }}
          >
            Clear Filter
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Batch</th>
                <th className="px-3 py-2">Phone</th>
                <th className="px-3 py-2">Parent</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.id} className="border-b border-slate-100">
                  <td className="px-3 py-2">{row.name}</td>
                  <td className="px-3 py-2">{row.batch || row.batch_id}</td>
                  <td className="px-3 py-2">{row.phone || '-'}</td>
                  <td className="px-3 py-2">{row.parent_phone || '-'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => openEditForm(row)}
                        className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => openDeleteModal(row)}
                        disabled={busyId === `delete-${row.id}`}
                        className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                      >
                        Delete
                      </button>
                      <button
                        type="button"
                        onClick={() => onAddReferral(row.id)}
                        disabled={busyId === `ref-${row.id}`}
                        className="rounded bg-amber-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                      >
                        Add Referral
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-6 text-center text-slate-500">No students match your filter.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={formOpen}
        title={formMode === 'add' ? 'Add Student' : 'Edit Student'}
        onClose={() => setFormOpen(false)}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
            <button
              type="submit"
              form="student-form-modal"
              disabled={busyId === 'save-form'}
              className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {formMode === 'add' ? 'Create Student' : 'Save Changes'}
            </button>
          </div>
        )}
      >
        <form id="student-form-modal" onSubmit={onSubmitForm} className="grid gap-3">
          <input
            required
            placeholder="Student name"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
          />
          <input
            placeholder="Phone"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.phone}
            onChange={(e) => setFormData((prev) => ({ ...prev, phone: e.target.value }))}
          />
          <select
            required
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.batch_id}
            onChange={(e) => setFormData((prev) => ({ ...prev, batch_id: e.target.value }))}
          >
            <option value="">Select Batch</option>
            {safeBatches.map((batch) => (
              <option key={batch.id} value={batch.id}>{batch.name}</option>
            ))}
          </select>
          <input
            placeholder="Parent phone"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.parent_phone}
            onChange={(e) => setFormData((prev) => ({ ...prev, parent_phone: e.target.value }))}
          />
        </form>
      </Modal>

      <Modal
        open={deleteOpen}
        title="Delete Student"
        onClose={() => setDeleteOpen(false)}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setDeleteOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
            <button
              type="button"
              onClick={onConfirmDelete}
              disabled={!deleteStudentRow || busyId === `delete-${deleteStudentRow?.id}`}
              className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Confirm Delete
            </button>
          </div>
        )}
      >
        <p className="text-sm text-slate-700">You are about to permanently delete this student and linked records. This action cannot be undone.</p>
        {deleteStudentRow ? (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p><strong>Name:</strong> {deleteStudentRow.name}</p>
            <p><strong>Batch:</strong> {deleteStudentRow.batch || deleteStudentRow.batch_id}</p>
            <p><strong>Phone:</strong> {deleteStudentRow.phone || '-'}</p>
            <p><strong>Parent:</strong> {deleteStudentRow.parent_phone || '-'}</p>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}

export default Students;
