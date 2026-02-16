import { createSlice } from '@reduxjs/toolkit';

const riskSlice = createSlice({
  name: 'risk',
  initialState: {
    loading: true,
    error: '',
    rows: [],
    levelFilter: 'all',
    search: '',
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.rows = Array.isArray(action.payload) ? action.payload : [];
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load risk insights');
    },
    setLevelFilter(state, action) {
      state.levelFilter = String(action.payload || 'all');
    },
    setSearch(state, action) {
      state.search = String(action.payload || '');
    },
    clearFilters(state) {
      state.levelFilter = 'all';
      state.search = '';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setLevelFilter,
  setSearch,
  clearFilters,
} = riskSlice.actions;

export default riskSlice.reducer;
