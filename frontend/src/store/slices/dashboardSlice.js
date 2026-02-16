import { createSlice } from '@reduxjs/toolkit';

const dashboardSlice = createSlice({
  name: 'dashboard',
  initialState: {
    loading: false,
    error: '',
    data: null,
    selectedBatchId: 'all',
    selectedMonth: 'all',
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.data = action.payload || null;
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load dashboard');
    },
    setSelectedBatchId(state, action) {
      state.selectedBatchId = String(action.payload || 'all');
    },
    setSelectedMonth(state, action) {
      state.selectedMonth = String(action.payload || 'all');
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setSelectedBatchId,
  setSelectedMonth,
} = dashboardSlice.actions;

export default dashboardSlice.reducer;
