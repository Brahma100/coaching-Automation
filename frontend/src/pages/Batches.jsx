import React from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useSearchParams } from 'react-router-dom';

import Modal from '../components/Modal.jsx';
import { PageSkeleton } from '../components/Skeleton.jsx';
import { selectBatchesPageState } from '../store/selectors/batchesSelectors.js';
import {
  addScheduleRequested,
  clearError,
  closeBatchForm,
  closeDeleteBatchModal,
  closeScheduleEdit,
  deleteBatchRequested,
  deleteScheduleRequested,
  hydrateFromQuery,
  linkStudentRequested,
  loadBatchStudentsRequested,
  loadRequested,
  openAddBatch,
  openDeleteBatchModal,
  openEditBatch,
  openScheduleEdit,
  saveBatchRequested,
  saveScheduleRequested,
  setBatchFormField,
  setScheduleFormField,
  setSelectedBatchId,
  unlinkStudentRequested,
} from '../store/slices/batchesSlice.js';

function weekdayLabel(value) {
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][Number(value)] || `Day ${value}`;
}

function dateToInput(value) {
  return value.toISOString().slice(0, 10);
}

function Batches() {
  const dispatch = useDispatch();
  const [searchParams, setSearchParams] = useSearchParams();
  const todayIso = React.useMemo(() => dateToInput(new Date()), []);
  const requestedBatchId = Number(searchParams.get('batch_id') || 0) || null;
  const [linkStudentId, setLinkStudentId] = React.useState('');

  const {
    loading,
    error,
    busyId,
    batches,
    batchStudents,
    selectedBatchId,
    selectedBatch,
    schedules,
    availableStudents,
    chartData,
    activeCount,
    inactiveCount,
    batchFormOpen,
    batchFormMode,
    editingBatch,
    batchForm,
    scheduleForm,
    scheduleEditOpen,
    scheduleEditTarget,
    deleteBatchOpen,
    deleteBatchTarget,
  } = useSelector(selectBatchesPageState);

  const effectiveToday = selectedBatch?.effective_schedule_for_date || null;

  React.useEffect(() => {
    dispatch(hydrateFromQuery({ requestedBatchId }));
    dispatch(loadRequested({ requestedBatchId, forDate: todayIso }));
  }, [dispatch, requestedBatchId, todayIso]);

  React.useEffect(() => {
    if (!selectedBatchId) return;
    if (requestedBatchId === Number(selectedBatchId)) return;
    const next = new URLSearchParams(searchParams);
    next.set('batch_id', String(selectedBatchId));
    setSearchParams(next, { replace: true });
  }, [requestedBatchId, searchParams, selectedBatchId, setSearchParams]);

  const onSelectBatch = (batchId) => {
    dispatch(setSelectedBatchId(batchId));
    dispatch(loadBatchStudentsRequested({ batchId }));
    setLinkStudentId('');
  };

  const onSubmitBatchForm = (event) => {
    event.preventDefault();
    dispatch(
      saveBatchRequested({
        mode: batchFormMode,
        batchId: editingBatch?.id,
        form: batchForm,
        requestedBatchId,
        forDate: todayIso,
      })
    );
  };

  const onConfirmDeleteBatch = () => {
    if (!deleteBatchTarget?.id) return;
    dispatch(
      deleteBatchRequested({
        batchId: deleteBatchTarget.id,
        requestedBatchId,
        forDate: todayIso,
      })
    );
  };

  const onSubmitScheduleAdd = (event) => {
    event.preventDefault();
    if (!selectedBatchId) return;
    dispatch(
      addScheduleRequested({
        batchId: selectedBatchId,
        form: scheduleForm,
        requestedBatchId,
        forDate: todayIso,
      })
    );
  };

  const onSubmitScheduleEdit = (event) => {
    event.preventDefault();
    if (!scheduleEditTarget?.id) return;
    dispatch(
      saveScheduleRequested({
        scheduleId: scheduleEditTarget.id,
        form: scheduleForm,
        requestedBatchId,
        forDate: todayIso,
      })
    );
  };

  const onDeleteSchedule = (scheduleId) => {
    dispatch(deleteScheduleRequested({ scheduleId, requestedBatchId, forDate: todayIso }));
  };

  const onLinkStudent = () => {
    const studentId = Number(linkStudentId || 0);
    if (!selectedBatchId || !studentId) return;
    dispatch(
      linkStudentRequested({
        batchId: selectedBatchId,
        studentId,
        requestedBatchId,
        forDate: todayIso,
      })
    );
    setLinkStudentId('');
  };

  const onUnlinkStudent = (studentId) => {
    if (!selectedBatchId) return;
    dispatch(
      unlinkStudentRequested({
        batchId: selectedBatchId,
        studentId,
        requestedBatchId,
        forDate: todayIso,
      })
    );
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
            <h3 className="text-sm font-bold text-slate-700">Students per Batch</h3>
            <span className="text-xs text-slate-500">Batch Load</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="students" fill="#2f7bf6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-700">Batch Status</h3>
            <span className="text-xs text-slate-500">Active vs Inactive</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-emerald-50 p-3">
              <p className="text-xs text-emerald-700">Active Batches</p>
              <p className="text-2xl font-bold text-emerald-800">{activeCount}</p>
            </div>
            <div className="rounded-xl bg-amber-50 p-3">
              <p className="text-xs text-amber-700">Inactive Batches</p>
              <p className="text-2xl font-bold text-amber-800">{inactiveCount}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-extrabold text-slate-900 sm:text-[30px]">Manage Batches</h2>
          <button
            type="button"
            onClick={() => dispatch(openAddBatch())}
            className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white hover:bg-[#225fca]"
          >
            Add Batch
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Subject</th>
                <th className="px-3 py-2">Level</th>
                <th className="px-3 py-2">Students</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((row) => (
                <tr
                  key={row.id}
                  className={`border-b border-slate-100 ${Number(selectedBatchId) === Number(row.id) ? 'bg-blue-50/40' : ''}`}
                >
                  <td className="px-3 py-2 font-semibold">{row.name}</td>
                  <td className="px-3 py-2">{row.subject || '-'}</td>
                  <td className="px-3 py-2">{row.academic_level || '-'}</td>
                  <td className="px-3 py-2">{row.student_count || 0}</td>
                  <td className="px-3 py-2">{row.active ? 'Active' : 'Inactive'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => onSelectBatch(row.id)}
                        className="rounded bg-slate-700 px-2 py-1 text-xs font-semibold text-white"
                      >
                        Select
                      </button>
                      <button
                        type="button"
                        onClick={() => dispatch(openEditBatch(row))}
                        className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => dispatch(openDeleteBatchModal(row))}
                        disabled={busyId === `delete-batch-${row.id}`}
                        className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                      >
                        Deactivate
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {batches.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-slate-500" colSpan={6}>
                    No batches available.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {selectedBatch ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">Schedule Slots - {selectedBatch.name}</h3>
            </div>
            {effectiveToday ? (
              <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
                Effective Today: {effectiveToday.start_time ? `${effectiveToday.start_time} (${effectiveToday.duration_minutes || 60}m)` : 'No class'}
                {effectiveToday.source === 'override' ? ' [override]' : ''}
                {effectiveToday.cancelled ? ' [cancelled]' : ''}
              </div>
            ) : null}

            <form onSubmit={onSubmitScheduleAdd} className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-4">
              <select
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={scheduleForm.weekday}
                onChange={(e) => dispatch(setScheduleFormField({ field: 'weekday', value: Number(e.target.value) }))}
              >
                {[0, 1, 2, 3, 4, 5, 6].map((w) => (
                  <option key={w} value={w}>
                    {weekdayLabel(w)}
                  </option>
                ))}
              </select>
              <input
                type="time"
                required
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={scheduleForm.start_time}
                onChange={(e) => dispatch(setScheduleFormField({ field: 'start_time', value: e.target.value }))}
              />
              <input
                type="number"
                min={1}
                max={180}
                required
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={scheduleForm.duration_minutes}
                onChange={(e) => dispatch(setScheduleFormField({ field: 'duration_minutes', value: Number(e.target.value) }))}
              />
              <button
                type="submit"
                disabled={busyId === 'add-schedule'}
                className="action-glow-btn rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                Add Slot
              </button>
            </form>

            <div className="space-y-2">
              {schedules.map((row) => (
                <div key={row.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <span>
                    {weekdayLabel(row.weekday)} | {row.start_time} | {row.duration_minutes}m
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => dispatch(openScheduleEdit(row))}
                      className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onDeleteSchedule(row.id)}
                      disabled={busyId === `delete-schedule-${row.id}`}
                      className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
              {schedules.length === 0 ? <p className="text-sm text-slate-500">No schedule slots yet.</p> : null}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-700">Student Links - {selectedBatch.name}</h3>
            </div>

            <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1fr,auto]">
              <select
                id="batch-student-link-select"
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={linkStudentId}
                onChange={(e) => setLinkStudentId(e.target.value)}
              >
                <option value="">Select student to link</option>
                {availableStudents.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name} ({row.id})
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="action-glow-btn rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white"
                onClick={onLinkStudent}
              >
                Link Student
              </button>
            </div>

            <div className="space-y-2">
              {batchStudents.map((row) => (
                <div key={row.student_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <span>
                    {row.name} ({row.student_id})
                  </span>
                  <button
                    type="button"
                    onClick={() => onUnlinkStudent(row.student_id)}
                    disabled={busyId === `unlink-student-${row.student_id}`}
                    className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60"
                  >
                    Unlink
                  </button>
                </div>
              ))}
              {batchStudents.length === 0 ? <p className="text-sm text-slate-500">No linked students.</p> : null}
            </div>
          </div>
        </div>
      ) : null}

      <Modal
        open={batchFormOpen}
        title={batchFormMode === 'add' ? 'Add Batch' : 'Edit Batch'}
        onClose={() => dispatch(closeBatchForm())}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dispatch(closeBatchForm())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="batch-form-modal"
              disabled={busyId === 'save-batch'}
              className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {batchFormMode === 'add' ? 'Create Batch' : 'Save Changes'}
            </button>
          </div>
        )}
      >
        <form id="batch-form-modal" onSubmit={onSubmitBatchForm} className="grid gap-3">
          <input
            required
            placeholder="Batch name"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={batchForm.name}
            onChange={(e) => dispatch(setBatchFormField({ field: 'name', value: e.target.value }))}
          />
          <input
            required
            placeholder="Subject"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={batchForm.subject}
            onChange={(e) => dispatch(setBatchFormField({ field: 'subject', value: e.target.value }))}
          />
          <input
            placeholder="Academic level"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={batchForm.academic_level}
            onChange={(e) => dispatch(setBatchFormField({ field: 'academic_level', value: e.target.value }))}
          />
          <label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={batchForm.active}
              onChange={(e) => dispatch(setBatchFormField({ field: 'active', value: e.target.checked }))}
            />
            Active batch
          </label>
        </form>
      </Modal>

      <Modal
        open={scheduleEditOpen}
        title="Edit Schedule Slot"
        onClose={() => dispatch(closeScheduleEdit())}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dispatch(closeScheduleEdit())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="schedule-edit-form"
              disabled={!scheduleEditTarget || busyId === `edit-schedule-${scheduleEditTarget?.id}`}
              className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Save Slot
            </button>
          </div>
        )}
      >
        <form id="schedule-edit-form" onSubmit={onSubmitScheduleEdit} className="grid gap-3">
          <select
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={scheduleForm.weekday}
            onChange={(e) => dispatch(setScheduleFormField({ field: 'weekday', value: Number(e.target.value) }))}
          >
            {[0, 1, 2, 3, 4, 5, 6].map((w) => (
              <option key={w} value={w}>
                {weekdayLabel(w)}
              </option>
            ))}
          </select>
          <input
            type="time"
            required
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={scheduleForm.start_time}
            onChange={(e) => dispatch(setScheduleFormField({ field: 'start_time', value: e.target.value }))}
          />
          <input
            type="number"
            min={1}
            max={180}
            required
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={scheduleForm.duration_minutes}
            onChange={(e) => dispatch(setScheduleFormField({ field: 'duration_minutes', value: Number(e.target.value) }))}
          />
        </form>
      </Modal>

      <Modal
        open={deleteBatchOpen}
        title="Deactivate Batch"
        onClose={() => dispatch(closeDeleteBatchModal())}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => dispatch(closeDeleteBatchModal())}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirmDeleteBatch}
              disabled={!deleteBatchTarget || busyId === `delete-batch-${deleteBatchTarget?.id}`}
              className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              Confirm Deactivate
            </button>
          </div>
        )}
      >
        <p className="text-sm text-slate-700">
          This will mark the batch as inactive without deleting historical attendance, fee, homework, or class session records.
        </p>
        {deleteBatchTarget ? (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p>
              <strong>Name:</strong> {deleteBatchTarget.name}
            </p>
            <p>
              <strong>Subject:</strong> {deleteBatchTarget.subject || '-'}
            </p>
            <p>
              <strong>Level:</strong> {deleteBatchTarget.academic_level || '-'}
            </p>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}

export default Batches;
