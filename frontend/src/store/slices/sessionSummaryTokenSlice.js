import { createSlice } from '@reduxjs/toolkit';

const sessionSummaryTokenSlice = createSlice({
  name: 'sessionSummaryToken',
  initialState: {
    loading: false,
    error: '',
    summary: null,
  },
  reducers: {
    resetState(state) {
      state.loading = false;
      state.error = '';
      state.summary = null;
    },
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.summary = action.payload || null;
    },
    loadFailed(state, action) {
      state.loading = false;
      state.summary = null;
      state.error = String(action.payload || 'Session summary unavailable.');
    },
  },
});

export const {
  resetState,
  loadRequested,
  loadSucceeded,
  loadFailed,
} = sessionSummaryTokenSlice.actions;

export default sessionSummaryTokenSlice.reducer;
