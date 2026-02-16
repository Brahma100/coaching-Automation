import { createSlice } from '@reduxjs/toolkit';

const feesSlice = createSlice({
  name: 'fees',
  initialState: {
    loading: true,
    error: '',
    fees: { due: [], overdue: [], paid: [] },
    search: '',
    statusFilter: 'all',
    monthFilter: 'all',
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.fees = action.payload || { due: [], overdue: [], paid: [] };
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load fees');
    },
    setSearch(state, action) {
      state.search = String(action.payload || '');
    },
    setStatusFilter(state, action) {
      state.statusFilter = String(action.payload || 'all');
    },
    setMonthFilter(state, action) {
      state.monthFilter = String(action.payload || 'all');
    },
    clearFilters(state) {
      state.search = '';
      state.statusFilter = 'all';
      state.monthFilter = 'all';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setSearch,
  setStatusFilter,
  setMonthFilter,
  clearFilters,
} = feesSlice.actions;

export default feesSlice.reducer;
