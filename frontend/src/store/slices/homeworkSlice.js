import { createSlice } from '@reduxjs/toolkit';

const homeworkSlice = createSlice({
  name: 'homework',
  initialState: {
    loading: true,
    error: '',
    rows: [],
    search: '',
    dueFilter: 'all',
    subjectFilter: 'all',
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
      state.error = String(action.payload || 'Failed to load homework');
    },
    setSearch(state, action) {
      state.search = String(action.payload || '');
    },
    setDueFilter(state, action) {
      state.dueFilter = String(action.payload || 'all');
    },
    setSubjectFilter(state, action) {
      state.subjectFilter = String(action.payload || 'all');
    },
    clearFilters(state) {
      state.search = '';
      state.dueFilter = 'all';
      state.subjectFilter = 'all';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setSearch,
  setDueFilter,
  setSubjectFilter,
  clearFilters,
} = homeworkSlice.actions;

export default homeworkSlice.reducer;
