import { createSlice } from '@reduxjs/toolkit';

const defaultFilters = {
  search: '',
  batch_id: '',
  subject_id: '',
  topic_id: '',
  tag: '',
  page: 1,
  page_size: 12,
};

const notesSlice = createSlice({
  name: 'notes',
  initialState: {
    loading: false,
    error: '',
    notes: [],
    metadata: { subjects: [], chapters: [], topics: [], tags: [], batches: [] },
    analytics: { total_notes: 0, total_subjects: 0, total_tags: 0, total_downloads: 0 },
    pagination: { page: 1, page_size: 12, total: 0, total_pages: 1 },
    filters: defaultFilters,
    viewMode: 'grid',
    autoDeleteOnExpiryEnabled: false,
    driveConnected: false,
    driveStatusLoading: false,
    driveDisconnecting: false,
    deletingId: null,
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      state.loading = false;
      state.error = '';
      state.notes = Array.isArray(payload.notes) ? payload.notes : [];
      state.metadata = payload.metadata || { subjects: [], chapters: [], topics: [], tags: [], batches: [] };
      state.analytics = payload.analytics || { total_notes: 0, total_subjects: 0, total_tags: 0, total_downloads: 0 };
      state.pagination = payload.pagination || { page: 1, page_size: 12, total: 0, total_pages: 1 };
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load notes');
    },
    setError(state, action) {
      state.error = String(action.payload || '');
    },
    clearError(state) {
      state.error = '';
    },
    setViewMode(state, action) {
      state.viewMode = String(action.payload || 'grid');
    },
    updateFilter(state, action) {
      const payload = action.payload || {};
      const key = String(payload.key || '');
      const value = payload.value;
      if (!key || !(key in state.filters)) return;
      state.filters[key] = value;
      state.filters.page = key === 'page' ? Number(value || 1) : 1;
    },
    setFilters(state, action) {
      state.filters = { ...defaultFilters, ...(action.payload || {}) };
    },
    loadAutoDeletePrefRequested() {},
    loadAutoDeletePrefSucceeded(state, action) {
      state.autoDeleteOnExpiryEnabled = Boolean(action.payload);
    },
    loadAutoDeletePrefFailed(state) {
      state.autoDeleteOnExpiryEnabled = false;
    },
    loadDriveStatusRequested(state) {
      state.driveStatusLoading = true;
    },
    loadDriveStatusSucceeded(state, action) {
      state.driveStatusLoading = false;
      state.driveConnected = Boolean(action.payload);
    },
    loadDriveStatusFailed(state) {
      state.driveStatusLoading = false;
      state.driveConnected = false;
    },
    disconnectDriveRequested(state) {
      state.driveDisconnecting = true;
    },
    disconnectDriveSucceeded(state) {
      state.driveDisconnecting = false;
      state.driveConnected = false;
    },
    disconnectDriveFailed(state) {
      state.driveDisconnecting = false;
    },
    deleteRequested(state, action) {
      state.deletingId = Number(action.payload?.noteId || 0) || null;
      state.error = '';
    },
    deleteSucceeded(state) {
      state.deletingId = null;
    },
    deleteFailed(state, action) {
      state.deletingId = null;
      state.error = String(action.payload || 'Delete failed');
    },
    uploadRequested() {},
    downloadRequested() {},
    autoDeleteRequested() {},
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setError,
  clearError,
  setViewMode,
  updateFilter,
  setFilters,
  loadAutoDeletePrefRequested,
  loadAutoDeletePrefSucceeded,
  loadAutoDeletePrefFailed,
  loadDriveStatusRequested,
  loadDriveStatusSucceeded,
  loadDriveStatusFailed,
  disconnectDriveRequested,
  disconnectDriveSucceeded,
  disconnectDriveFailed,
  deleteRequested,
  deleteSucceeded,
  deleteFailed,
  uploadRequested,
  downloadRequested,
  autoDeleteRequested,
} = notesSlice.actions;

export default notesSlice.reducer;
