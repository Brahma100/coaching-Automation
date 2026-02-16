import { createSlice } from '@reduxjs/toolkit';

const initialBatchForm = { name: '', subject: '', academic_level: '', active: true };
const initialScheduleForm = { weekday: 0, start_time: '07:00', duration_minutes: 60 };

const initialState = {
  loading: true,
  error: '',
  busyId: null,
  requestedBatchId: null,
  batches: [],
  students: [],
  selectedBatchId: null,
  batchStudents: [],

  batchFormOpen: false,
  batchFormMode: 'add',
  editingBatch: null,
  batchForm: initialBatchForm,

  scheduleForm: initialScheduleForm,
  scheduleEditOpen: false,
  scheduleEditTarget: null,

  deleteBatchOpen: false,
  deleteBatchTarget: null,
};

function toNullableNumber(value) {
  const parsed = Number(value || 0);
  return parsed > 0 ? parsed : null;
}

const batchesSlice = createSlice({
  name: 'batches',
  initialState,
  reducers: {
    hydrateFromQuery(state, action) {
      state.requestedBatchId = toNullableNumber(action.payload?.requestedBatchId);
    },
    setSelectedBatchId(state, action) {
      state.selectedBatchId = toNullableNumber(action.payload);
    },
    clearError(state) {
      state.error = '';
    },

    loadRequested(state) {
      state.loading = !Array.isArray(state.batches) || state.batches.length === 0;
      state.error = '';
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      state.loading = false;
      state.error = '';
      state.batches = Array.isArray(payload.batches) ? payload.batches : [];
      state.students = Array.isArray(payload.students) ? payload.students : [];
      state.selectedBatchId = toNullableNumber(payload.selectedBatchId);
      state.batchStudents = Array.isArray(payload.batchStudents) ? payload.batchStudents : [];
    },
    loadFailed(state, action) {
      state.loading = false;
      state.batches = [];
      state.students = [];
      state.batchStudents = [];
      state.error = String(action.payload || 'Failed to load batches');
    },

    loadBatchStudentsRequested() {},
    loadBatchStudentsSucceeded(state, action) {
      state.batchStudents = Array.isArray(action.payload) ? action.payload : [];
    },
    loadBatchStudentsFailed(state) {
      state.batchStudents = [];
    },

    openAddBatch(state) {
      state.batchFormMode = 'add';
      state.editingBatch = null;
      state.batchForm = { ...initialBatchForm, subject: 'General' };
      state.batchFormOpen = true;
    },
    openEditBatch(state, action) {
      const row = action.payload || {};
      state.batchFormMode = 'edit';
      state.editingBatch = row || null;
      state.batchForm = {
        name: row?.name || '',
        subject: row?.subject || 'General',
        academic_level: row?.academic_level || '',
        active: Boolean(row?.active),
      };
      state.batchFormOpen = true;
    },
    closeBatchForm(state) {
      state.batchFormOpen = false;
    },
    setBatchFormField(state, action) {
      const payload = action.payload || {};
      if (!payload.field) return;
      state.batchForm = { ...state.batchForm, [payload.field]: payload.value };
    },

    openDeleteBatchModal(state, action) {
      state.deleteBatchTarget = action.payload || null;
      state.deleteBatchOpen = true;
    },
    closeDeleteBatchModal(state) {
      state.deleteBatchOpen = false;
      state.deleteBatchTarget = null;
    },

    setScheduleFormField(state, action) {
      const payload = action.payload || {};
      if (!payload.field) return;
      state.scheduleForm = { ...state.scheduleForm, [payload.field]: payload.value };
    },
    resetScheduleForm(state) {
      state.scheduleForm = initialScheduleForm;
    },
    openScheduleEdit(state, action) {
      const row = action.payload || {};
      state.scheduleEditTarget = row || null;
      state.scheduleForm = {
        weekday: Number(row?.weekday || 0),
        start_time: row?.start_time || '07:00',
        duration_minutes: Number(row?.duration_minutes || 60),
      };
      state.scheduleEditOpen = true;
    },
    closeScheduleEdit(state) {
      state.scheduleEditOpen = false;
      state.scheduleEditTarget = null;
      state.scheduleForm = initialScheduleForm;
    },

    saveBatchRequested(state) {
      state.busyId = 'save-batch';
      state.error = '';
    },
    saveBatchSucceeded(state) {
      state.busyId = null;
      state.batchFormOpen = false;
    },
    saveBatchFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Batch save failed');
    },

    deleteBatchRequested(state, action) {
      const batchId = action.payload?.batchId;
      state.busyId = `delete-batch-${batchId}`;
      state.error = '';
    },
    deleteBatchSucceeded(state) {
      state.busyId = null;
      state.deleteBatchOpen = false;
      state.deleteBatchTarget = null;
    },
    deleteBatchFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Batch delete failed');
    },

    addScheduleRequested(state) {
      state.busyId = 'add-schedule';
      state.error = '';
    },
    addScheduleSucceeded(state) {
      state.busyId = null;
      state.scheduleForm = initialScheduleForm;
    },
    addScheduleFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Schedule add failed');
    },

    saveScheduleRequested(state, action) {
      const scheduleId = action.payload?.scheduleId;
      state.busyId = `edit-schedule-${scheduleId}`;
      state.error = '';
    },
    saveScheduleSucceeded(state) {
      state.busyId = null;
      state.scheduleEditOpen = false;
      state.scheduleEditTarget = null;
      state.scheduleForm = initialScheduleForm;
    },
    saveScheduleFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Schedule update failed');
    },

    deleteScheduleRequested(state, action) {
      const scheduleId = action.payload?.scheduleId;
      state.busyId = `delete-schedule-${scheduleId}`;
      state.error = '';
    },
    deleteScheduleSucceeded(state) {
      state.busyId = null;
    },
    deleteScheduleFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Schedule delete failed');
    },

    linkStudentRequested(state, action) {
      const studentId = action.payload?.studentId;
      state.busyId = `link-student-${studentId}`;
      state.error = '';
    },
    linkStudentSucceeded(state) {
      state.busyId = null;
    },
    linkStudentFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Student link failed');
    },

    unlinkStudentRequested(state, action) {
      const studentId = action.payload?.studentId;
      state.busyId = `unlink-student-${studentId}`;
      state.error = '';
    },
    unlinkStudentSucceeded(state) {
      state.busyId = null;
    },
    unlinkStudentFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Student unlink failed');
    },
  },
});

export const {
  hydrateFromQuery,
  setSelectedBatchId,
  clearError,
  loadRequested,
  loadSucceeded,
  loadFailed,
  loadBatchStudentsRequested,
  loadBatchStudentsSucceeded,
  loadBatchStudentsFailed,
  openAddBatch,
  openEditBatch,
  closeBatchForm,
  setBatchFormField,
  openDeleteBatchModal,
  closeDeleteBatchModal,
  setScheduleFormField,
  resetScheduleForm,
  openScheduleEdit,
  closeScheduleEdit,
  saveBatchRequested,
  saveBatchSucceeded,
  saveBatchFailed,
  deleteBatchRequested,
  deleteBatchSucceeded,
  deleteBatchFailed,
  addScheduleRequested,
  addScheduleSucceeded,
  addScheduleFailed,
  saveScheduleRequested,
  saveScheduleSucceeded,
  saveScheduleFailed,
  deleteScheduleRequested,
  deleteScheduleSucceeded,
  deleteScheduleFailed,
  linkStudentRequested,
  linkStudentSucceeded,
  linkStudentFailed,
  unlinkStudentRequested,
  unlinkStudentSucceeded,
  unlinkStudentFailed,
} = batchesSlice.actions;

export default batchesSlice.reducer;
