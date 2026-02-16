import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  rows: [],
  loading: false,
  error: '',
  integrationRequired: false,
  integrationProvider: '',
  integrationMessage: '',
  busyId: null,
  typeFilter: 'all',
  search: '',
};

const actionsSlice = createSlice({
  name: 'actions',
  initialState,
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
      state.integrationRequired = false;
      state.integrationProvider = '';
      state.integrationMessage = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.rows = Array.isArray(action.payload) ? action.payload : [];
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load actions');
    },
    runActionRequested(state, action) {
      state.busyId = String(action.payload?.busyId || '');
      state.error = '';
      state.integrationRequired = false;
      state.integrationProvider = '';
      state.integrationMessage = '';
    },
    runActionSucceeded(state, action) {
      state.busyId = null;
      state.error = '';
      state.rows = Array.isArray(action.payload) ? action.payload : [];
    },
    runActionFailed(state, action) {
      state.busyId = null;
      const payload = action.payload;
      if (payload && typeof payload === 'object') {
        state.error = String(payload.message || 'Action failed');
        state.integrationRequired = Boolean(payload.integrationRequired);
        state.integrationProvider = String(payload.provider || '');
        state.integrationMessage = String(payload.integrationMessage || '');
        return;
      }
      state.error = String(action.payload || 'Action failed');
      state.integrationRequired = false;
      state.integrationProvider = '';
      state.integrationMessage = '';
    },
    setTypeFilter(state, action) {
      state.typeFilter = String(action.payload || 'all');
    },
    setSearch(state, action) {
      state.search = String(action.payload || '');
    },
    clearFilters(state) {
      state.typeFilter = 'all';
      state.search = '';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  runActionRequested,
  runActionSucceeded,
  runActionFailed,
  setTypeFilter,
  setSearch,
  clearFilters,
} = actionsSlice.actions;

export default actionsSlice.reducer;
