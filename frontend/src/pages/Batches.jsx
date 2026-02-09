import React from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import Modal from '../components/Modal.jsx';
import { PageSkeleton } from '../components/Skeleton.jsx';
import {
  addBatchSchedule,
  createBatch,
  deleteBatch,
  deleteBatchSchedule,
  fetchAdminBatches,
  fetchBatchStudents,
  fetchStudents,
  linkStudentToBatch,
  unlinkStudentFromBatch,
  updateBatch,
  updateBatchSchedule
} from '../services/api';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function weekdayLabel(value) {
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][Number(value)] || `Day ${value}`;
}

const initialBatchForm = { name: '', subject: '', academic_level: '', active: true };
const initialScheduleForm = { weekday: 0, start_time: '07:00', duration_minutes: 60 };

function Batches() {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [batches, setBatches] = React.useState([]);
  const [students, setStudents] = React.useState([]);
  const [selectedBatchId, setSelectedBatchId] = React.useState(null);
  const [batchStudents, setBatchStudents] = React.useState([]);
  const [busyId, setBusyId] = React.useState(null);

  const [batchFormOpen, setBatchFormOpen] = React.useState(false);
  const [batchFormMode, setBatchFormMode] = React.useState('add');
  const [editingBatch, setEditingBatch] = React.useState(null);
  const [batchForm, setBatchForm] = React.useState(initialBatchForm);

  const [scheduleForm, setScheduleForm] = React.useState(initialScheduleForm);
  const [scheduleEditOpen, setScheduleEditOpen] = React.useState(false);
  const [scheduleEditTarget, setScheduleEditTarget] = React.useState(null);

  const [deleteBatchOpen, setDeleteBatchOpen] = React.useState(false);
  const [deleteBatchTarget, setDeleteBatchTarget] = React.useState(null);

  const loadData = React.useCallback(async () => {
    try {
      const [batchesPayload, studentsPayload] = await Promise.all([fetchAdminBatches(), fetchStudents()]);
      const nextBatches = normalizeList(batchesPayload?.rows ?? batchesPayload);
      const nextStudents = normalizeList(studentsPayload?.rows ?? studentsPayload);
      setBatches(nextBatches);
      setStudents(nextStudents);

      if (!selectedBatchId && nextBatches.length > 0) {
        setSelectedBatchId(nextBatches[0].id);
      }
      if (selectedBatchId && !nextBatches.some((row) => row.id === selectedBatchId)) {
        setSelectedBatchId(nextBatches[0]?.id || null);
      }
      setError('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load batches');
      setBatches([]);
      setStudents([]);
    } finally {
      setLoading(false);
    }
  }, [selectedBatchId]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  React.useEffect(() => {
    if (!selectedBatchId) {
      setBatchStudents([]);
      return;
    }
    let mounted = true;
    (async () => {
      try {
        const payload = await fetchBatchStudents(selectedBatchId);
        if (mounted) setBatchStudents(normalizeList(payload));
      } catch {
        if (mounted) setBatchStudents([]);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [selectedBatchId, batches.length]);

  const selectedBatch = batches.find((row) => row.id === selectedBatchId) || null;
  const schedules = normalizeList(selectedBatch?.schedules);
  const linkedStudentIds = new Set(batchStudents.map((row) => Number(row.student_id)));
  const availableStudents = students.filter((row) => !linkedStudentIds.has(Number(row.id)));

  const chartData = batches.map((row) => ({ name: row.name, students: Number(row.student_count || 0) }));
  const activeCount = batches.filter((row) => row.active).length;
  const inactiveCount = Math.max(batches.length - activeCount, 0);

  const openAddBatch = () => {
    setBatchFormMode('add');
    setEditingBatch(null);
    setBatchForm({ ...initialBatchForm, subject: 'General' });
    setBatchFormOpen(true);
  };

  const openEditBatch = (row) => {
    setBatchFormMode('edit');
    setEditingBatch(row);
    setBatchForm({
      name: row.name || '',
      subject: row.subject || 'General',
      academic_level: row.academic_level || '',
      active: Boolean(row.active)
    });
    setBatchFormOpen(true);
  };

  const submitBatchForm = async (event) => {
    event.preventDefault();
    setBusyId('save-batch');
    try {
      if (batchFormMode === 'add') {
        await createBatch(batchForm);
      } else if (editingBatch) {
        await updateBatch(editingBatch.id, batchForm);
      }
      setBatchFormOpen(false);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Batch save failed');
    } finally {
      setBusyId(null);
    }
  };

  const confirmSoftDeleteBatch = async () => {
    if (!deleteBatchTarget) return;
    setBusyId(`delete-batch-${deleteBatchTarget.id}`);
    try {
      await deleteBatch(deleteBatchTarget.id);
      setDeleteBatchOpen(false);
      setDeleteBatchTarget(null);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Batch delete failed');
    } finally {
      setBusyId(null);
    }
  };

  const submitScheduleAdd = async (event) => {
    event.preventDefault();
    if (!selectedBatchId) return;
    setBusyId('add-schedule');
    try {
      await addBatchSchedule(selectedBatchId, {
        weekday: Number(scheduleForm.weekday),
        start_time: scheduleForm.start_time,
        duration_minutes: Number(scheduleForm.duration_minutes)
      });
      setScheduleForm(initialScheduleForm);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Schedule add failed');
    } finally {
      setBusyId(null);
    }
  };

  const openEditSchedule = (row) => {
    setScheduleEditTarget(row);
    setScheduleForm({
      weekday: Number(row.weekday),
      start_time: row.start_time,
      duration_minutes: Number(row.duration_minutes)
    });
    setScheduleEditOpen(true);
  };

  const submitScheduleEdit = async (event) => {
    event.preventDefault();
    if (!scheduleEditTarget) return;
    setBusyId(`edit-schedule-${scheduleEditTarget.id}`);
    try {
      await updateBatchSchedule(scheduleEditTarget.id, {
        weekday: Number(scheduleForm.weekday),
        start_time: scheduleForm.start_time,
        duration_minutes: Number(scheduleForm.duration_minutes)
      });
      setScheduleEditOpen(false);
      setScheduleEditTarget(null);
      setScheduleForm(initialScheduleForm);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Schedule update failed');
    } finally {
      setBusyId(null);
    }
  };

  const removeSchedule = async (scheduleId) => {
    setBusyId(`delete-schedule-${scheduleId}`);
    try {
      await deleteBatchSchedule(scheduleId);
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Schedule delete failed');
    } finally {
      setBusyId(null);
    }
  };

  const addStudentLink = async (studentId) => {
    if (!selectedBatchId) return;
    setBusyId(`link-student-${studentId}`);
    try {
      await linkStudentToBatch(selectedBatchId, studentId);
      const payload = await fetchBatchStudents(selectedBatchId);
      setBatchStudents(normalizeList(payload));
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Student link failed');
    } finally {
      setBusyId(null);
    }
  };

  const removeStudentLink = async (studentId) => {
    if (!selectedBatchId) return;
    setBusyId(`unlink-student-${studentId}`);
    try {
      await unlinkStudentFromBatch(selectedBatchId, studentId);
      const payload = await fetchBatchStudents(selectedBatchId);
      setBatchStudents(normalizeList(payload));
      await loadData();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Student unlink failed');
    } finally {
      setBusyId(null);
    }
  };

  if (loading) {
    return <PageSkeleton />;
  }

  return (
    <section className="space-y-4">
      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}

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
            <div className="rounded-xl bg-emerald-50 p-3"><p className="text-xs text-emerald-700">Active Batches</p><p className="text-2xl font-bold text-emerald-800">{activeCount}</p></div>
            <div className="rounded-xl bg-amber-50 p-3"><p className="text-xs text-amber-700">Inactive Batches</p><p className="text-2xl font-bold text-amber-800">{inactiveCount}</p></div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-extrabold text-slate-900 sm:text-[30px]">Manage Batches</h2>
          <button type="button" onClick={openAddBatch} className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white hover:bg-[#225fca]">Add Batch</button>
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
                <tr key={row.id} className={`border-b border-slate-100 ${selectedBatchId === row.id ? 'bg-blue-50/40' : ''}`}>
                  <td className="px-3 py-2 font-semibold">{row.name}</td>
                  <td className="px-3 py-2">{row.subject || '-'}</td>
                  <td className="px-3 py-2">{row.academic_level || '-'}</td>
                  <td className="px-3 py-2">{row.student_count || 0}</td>
                  <td className="px-3 py-2">{row.active ? 'Active' : 'Inactive'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <button type="button" onClick={() => setSelectedBatchId(row.id)} className="rounded bg-slate-700 px-2 py-1 text-xs font-semibold text-white">Select</button>
                      <button type="button" onClick={() => openEditBatch(row)} className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white">Edit</button>
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteBatchTarget(row);
                          setDeleteBatchOpen(true);
                        }}
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
                <tr><td className="px-3 py-6 text-center text-slate-500" colSpan={6}>No batches available.</td></tr>
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

            <form onSubmit={submitScheduleAdd} className="mb-4 grid gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-4">
              <select className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.weekday} onChange={(e) => setScheduleForm((prev) => ({ ...prev, weekday: Number(e.target.value) }))}>
                {[0, 1, 2, 3, 4, 5, 6].map((w) => <option key={w} value={w}>{weekdayLabel(w)}</option>)}
              </select>
              <input type="time" required className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.start_time} onChange={(e) => setScheduleForm((prev) => ({ ...prev, start_time: e.target.value }))} />
              <input type="number" min={1} max={180} required className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.duration_minutes} onChange={(e) => setScheduleForm((prev) => ({ ...prev, duration_minutes: Number(e.target.value) }))} />
              <button type="submit" disabled={busyId === 'add-schedule'} className="action-glow-btn rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60">Add Slot</button>
            </form>

            <div className="space-y-2">
              {schedules.map((row) => (
                <div key={row.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <span>{weekdayLabel(row.weekday)} | {row.start_time} | {row.duration_minutes}m</span>
                  <div className="flex gap-2">
                    <button type="button" onClick={() => openEditSchedule(row)} className="rounded bg-blue-600 px-2 py-1 text-xs font-semibold text-white">Edit</button>
                    <button type="button" onClick={() => removeSchedule(row.id)} disabled={busyId === `delete-schedule-${row.id}`} className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">Delete</button>
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
              <select id="batch-student-link-select" className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">Select student to link</option>
                {availableStudents.map((row) => (
                  <option key={row.id} value={row.id}>{row.name} ({row.id})</option>
                ))}
              </select>
              <button
                type="button"
                className="action-glow-btn rounded-lg bg-[#2f7bf6] px-3 py-2 text-sm font-semibold text-white"
                onClick={() => {
                  const element = document.getElementById('batch-student-link-select');
                  const studentId = Number(element?.value || 0);
                  if (!studentId) return;
                  addStudentLink(studentId);
                  element.value = '';
                }}
              >
                Link Student
              </button>
            </div>

            <div className="space-y-2">
              {batchStudents.map((row) => (
                <div key={row.student_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <span>{row.name} ({row.student_id})</span>
                  <button type="button" onClick={() => removeStudentLink(row.student_id)} disabled={busyId === `unlink-student-${row.student_id}`} className="rounded bg-rose-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-60">Unlink</button>
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
        onClose={() => setBatchFormOpen(false)}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setBatchFormOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
            <button type="submit" form="batch-form-modal" disabled={busyId === 'save-batch'} className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{batchFormMode === 'add' ? 'Create Batch' : 'Save Changes'}</button>
          </div>
        )}
      >
        <form id="batch-form-modal" onSubmit={submitBatchForm} className="grid gap-3">
          <input required placeholder="Batch name" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={batchForm.name} onChange={(e) => setBatchForm((prev) => ({ ...prev, name: e.target.value }))} />
          <input required placeholder="Subject" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={batchForm.subject} onChange={(e) => setBatchForm((prev) => ({ ...prev, subject: e.target.value }))} />
          <input placeholder="Academic level" className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={batchForm.academic_level} onChange={(e) => setBatchForm((prev) => ({ ...prev, academic_level: e.target.value }))} />
          <label className="flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <input type="checkbox" checked={batchForm.active} onChange={(e) => setBatchForm((prev) => ({ ...prev, active: e.target.checked }))} />
            Active batch
          </label>
        </form>
      </Modal>

      <Modal
        open={scheduleEditOpen}
        title="Edit Schedule Slot"
        onClose={() => {
          setScheduleEditOpen(false);
          setScheduleEditTarget(null);
          setScheduleForm(initialScheduleForm);
        }}
        footer={(
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setScheduleEditOpen(false);
                setScheduleEditTarget(null);
                setScheduleForm(initialScheduleForm);
              }}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button type="submit" form="schedule-edit-form" disabled={!scheduleEditTarget || busyId === `edit-schedule-${scheduleEditTarget?.id}`} className="action-glow-btn rounded-lg bg-[#2f7bf6] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Save Slot</button>
          </div>
        )}
      >
        <form id="schedule-edit-form" onSubmit={submitScheduleEdit} className="grid gap-3">
          <select className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.weekday} onChange={(e) => setScheduleForm((prev) => ({ ...prev, weekday: Number(e.target.value) }))}>
            {[0, 1, 2, 3, 4, 5, 6].map((w) => <option key={w} value={w}>{weekdayLabel(w)}</option>)}
          </select>
          <input type="time" required className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.start_time} onChange={(e) => setScheduleForm((prev) => ({ ...prev, start_time: e.target.value }))} />
          <input type="number" min={1} max={180} required className="rounded-lg border border-slate-300 px-3 py-2 text-sm" value={scheduleForm.duration_minutes} onChange={(e) => setScheduleForm((prev) => ({ ...prev, duration_minutes: Number(e.target.value) }))} />
        </form>
      </Modal>

      <Modal
        open={deleteBatchOpen}
        title="Deactivate Batch"
        onClose={() => setDeleteBatchOpen(false)}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setDeleteBatchOpen(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Cancel</button>
            <button type="button" onClick={confirmSoftDeleteBatch} disabled={!deleteBatchTarget || busyId === `delete-batch-${deleteBatchTarget?.id}`} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Confirm Deactivate</button>
          </div>
        )}
      >
        <p className="text-sm text-slate-700">This will mark the batch as inactive without deleting historical attendance, fee, homework, or class session records.</p>
        {deleteBatchTarget ? (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p><strong>Name:</strong> {deleteBatchTarget.name}</p>
            <p><strong>Subject:</strong> {deleteBatchTarget.subject || '-'}</p>
            <p><strong>Level:</strong> {deleteBatchTarget.academic_level || '-'}</p>
          </div>
        ) : null}
      </Modal>
    </section>
  );
}

export default Batches;
