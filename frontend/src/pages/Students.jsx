import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import Modal from '../components/Modal.jsx';
import { PageSkeleton } from '../components/Skeleton.jsx';
import { selectStudentsPageState } from '../store/selectors/studentsSelectors.js';
import {
  addReferralRequested,
  clearError,
  clearFilters,
  clearReferralNotice,
  closeDeleteModal,
  closeForm,
  deleteStudentRequested,
  loadRequested,
  openAddForm,
  openDeleteModal,
  openEditForm,
  saveStudentRequested,
  setBatchFilter,
  setFormField,
  setSearch,
} from '../store/slices/studentsSlice.js';

function Students() {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    busyId,
    search,
    batchFilter,
    batches,
    formOpen,
    formMode,
    editingStudent,
    formData,
    deleteOpen,
    deleteStudentRow,
    referralNotice,
    filteredRows,
    batchChartData,
    parentPieData,
    pieColors,
  } = useSelector(selectStudentsPageState);

  React.useEffect(() => {
    dispatch(loadRequested());
  }, [dispatch]);

  React.useEffect(() => {
    if (!referralNotice) return;
    window.alert(referralNotice);
    dispatch(clearReferralNotice());
  }, [dispatch, referralNotice]);

  const onSubmitForm = (event) => {
    event.preventDefault();
    dispatch(
      saveStudentRequested({
        mode: formMode,
        editingStudentId: editingStudent?.id,
        formData,
      })
    );
  };

  const onConfirmDelete = () => {
    if (!deleteStudentRow?.id) return;
    dispatch(deleteStudentRequested({ studentId: deleteStudentRow.id }));
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <section className="space-y-4">
      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <div className="flex items-center justify-between gap-3">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => dispatch(clearError())}
              className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white"
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : null}

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
            onClick={() => dispatch(openAddForm())}
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
            onChange={(e) => dispatch(setSearch(e.target.value))}
          />
          <select
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={batchFilter}
            onChange={(e) => dispatch(setBatchFilter(e.target.value))}
          >
            <option value="all">All Batches</option>
            {batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={() => dispatch(clearFilters())}
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
                        onClick={() => dispatch(openEditForm(row))}
                        className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => dispatch(openDeleteModal(row))}
                        disabled={busyId === `delete-${row.id}`}
                        className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                      >
                        Delete
                      </button>
                      <button
                        type="button"
                        onClick={() => dispatch(addReferralRequested({ studentId: row.id }))}
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
                  <td colSpan={5} className="px-3 py-6 text-center text-slate-500">
                    No students match your filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={formOpen}
        title={formMode === 'add' ? 'Add Student' : 'Edit Student'}
        onClose={() => dispatch(closeForm())}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dispatch(closeForm())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
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
            onChange={(e) => dispatch(setFormField({ field: 'name', value: e.target.value }))}
          />
          <input
            placeholder="Phone"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.phone}
            onChange={(e) => dispatch(setFormField({ field: 'phone', value: e.target.value }))}
          />
          <select
            required
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.batch_id}
            onChange={(e) => dispatch(setFormField({ field: 'batch_id', value: e.target.value }))}
          >
            <option value="">Select Batch</option>
            {batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Parent phone"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={formData.parent_phone}
            onChange={(e) => dispatch(setFormField({ field: 'parent_phone', value: e.target.value }))}
          />
        </form>
      </Modal>

      <Modal
        open={deleteOpen}
        title="Delete Student"
        onClose={() => dispatch(closeDeleteModal())}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dispatch(closeDeleteModal())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
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
        <p className="text-sm text-slate-700">
          You are about to permanently delete this student and linked records. This action cannot be undone.
        </p>
        {deleteStudentRow ? (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p>
              <strong>Name:</strong> {deleteStudentRow.name}
            </p>
            <p>
              <strong>Batch:</strong> {deleteStudentRow.batch || deleteStudentRow.batch_id}
            </p>
            <p>
              <strong>Phone:</strong> {deleteStudentRow.phone || '-'}
            </p>
            <p>
              <strong>Parent:</strong> {deleteStudentRow.parent_phone || '-'}
            </p>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}

export default Students;
