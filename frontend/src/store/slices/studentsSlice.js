import { createSlice } from '@reduxjs/toolkit';

const initialFormData = { name: '', phone: '', batch_id: '', parent_phone: '' };

const initialState = {
  loading: true,
  error: '',
  rows: [],
  batches: [],
  busyId: null,
  search: '',
  batchFilter: 'all',

  formOpen: false,
  formMode: 'add',
  editingStudent: null,
  formData: initialFormData,

  deleteOpen: false,
  deleteStudentRow: null,

  referralNotice: '',
};

const studentsSlice = createSlice({
  name: 'students',
  initialState,
  reducers: {
    clearError(state) {
      state.error = '';
    },
    clearReferralNotice(state) {
      state.referralNotice = '';
    },
    setSearch(state, action) {
      state.search = String(action.payload || '');
    },
    setBatchFilter(state, action) {
      state.batchFilter = String(action.payload || 'all');
    },
    clearFilters(state) {
      state.search = '';
      state.batchFilter = 'all';
    },

    loadRequested(state) {
      state.loading = !Array.isArray(state.rows) || state.rows.length === 0;
      state.error = '';
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      const nextRows = Array.isArray(payload.rows) ? payload.rows : [];
      const nextBatches = Array.isArray(payload.batches) ? payload.batches : [];
      state.loading = false;
      state.error = '';
      state.rows = nextRows;
      state.batches = nextBatches;
      if (!state.formData.batch_id && nextBatches[0]?.id) {
        state.formData = { ...state.formData, batch_id: String(nextBatches[0].id) };
      }
    },
    loadFailed(state, action) {
      state.loading = false;
      state.rows = [];
      state.error = String(action.payload || 'Failed to load students');
    },

    openAddForm(state) {
      state.formMode = 'add';
      state.editingStudent = null;
      state.formData = {
        name: '',
        phone: '',
        batch_id: String(state.batches[0]?.id || ''),
        parent_phone: '',
      };
      state.formOpen = true;
    },
    openEditForm(state, action) {
      const row = action.payload || {};
      state.formMode = 'edit';
      state.editingStudent = row || null;
      state.formData = {
        name: row.name || '',
        phone: row.phone || row.guardian_phone || '',
        batch_id: String(row.batch_id || ''),
        parent_phone: row.parent_phone || '',
      };
      state.formOpen = true;
    },
    closeForm(state) {
      state.formOpen = false;
    },
    setFormField(state, action) {
      const payload = action.payload || {};
      if (!payload.field) return;
      state.formData = { ...state.formData, [payload.field]: payload.value };
    },

    saveStudentRequested(state) {
      state.busyId = 'save-form';
      state.error = '';
    },
    saveStudentSucceeded(state) {
      state.busyId = null;
      state.formOpen = false;
    },
    saveStudentFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Save failed');
    },

    openDeleteModal(state, action) {
      state.deleteStudentRow = action.payload || null;
      state.deleteOpen = true;
    },
    closeDeleteModal(state) {
      state.deleteOpen = false;
      state.deleteStudentRow = null;
    },

    deleteStudentRequested(state, action) {
      state.busyId = `delete-${action.payload?.studentId}`;
      state.error = '';
    },
    deleteStudentSucceeded(state) {
      state.busyId = null;
      state.deleteOpen = false;
      state.deleteStudentRow = null;
    },
    deleteStudentFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Delete failed');
    },

    addReferralRequested(state, action) {
      state.busyId = `ref-${action.payload?.studentId}`;
      state.error = '';
      state.referralNotice = '';
    },
    addReferralSucceeded(state) {
      state.busyId = null;
      state.referralNotice = 'Referral created successfully.';
    },
    addReferralFailed(state, action) {
      state.busyId = null;
      state.error = String(action.payload || 'Referral failed');
    },
  },
});

export const {
  clearError,
  clearReferralNotice,
  setSearch,
  setBatchFilter,
  clearFilters,
  loadRequested,
  loadSucceeded,
  loadFailed,
  openAddForm,
  openEditForm,
  closeForm,
  setFormField,
  saveStudentRequested,
  saveStudentSucceeded,
  saveStudentFailed,
  openDeleteModal,
  closeDeleteModal,
  deleteStudentRequested,
  deleteStudentSucceeded,
  deleteStudentFailed,
  addReferralRequested,
  addReferralSucceeded,
  addReferralFailed,
} = studentsSlice.actions;

export default studentsSlice.reducer;
