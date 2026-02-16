import { createSlice } from '@reduxjs/toolkit';

const attendanceTokenSlice = createSlice({
  name: 'attendanceToken',
  initialState: {
    loadingSheet: true,
    sheet: null,
    rows: [],
    error: '',
    submitting: false,
    expiresAt: '',
    tokenValid: false,
    submitted: false,
  },
  reducers: {
    resetForTokenChange(state) {
      state.loadingSheet = true;
      state.sheet = null;
      state.rows = [];
      state.error = '';
      state.submitting = false;
      state.expiresAt = '';
      state.tokenValid = false;
      state.submitted = false;
    },
    tokenValidated(state, action) {
      state.tokenValid = true;
      state.expiresAt = String(action.payload?.expiresAt || '');
    },
    loadRequested(state) {
      state.loadingSheet = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      state.loadingSheet = false;
      state.error = '';
      state.sheet = payload.sheet || null;
      state.rows = Array.isArray(payload.rows) ? payload.rows : [];
    },
    loadFailed(state, action) {
      state.loadingSheet = false;
      state.sheet = null;
      state.rows = [];
      state.error = String(action.payload || 'Failed to load attendance sheet');
    },
    rowChanged(state, action) {
      const studentId = action.payload?.studentId;
      const field = String(action.payload?.field || '');
      const value = action.payload?.value;
      state.rows = (state.rows || []).map((row) => (
        row.student_id === studentId ? { ...row, [field]: value } : row
      ));
    },
    submitRequested(state) {
      state.submitting = true;
      state.error = '';
    },
    submitSucceeded(state) {
      state.submitting = false;
      state.submitted = true;
    },
    submitFailed(state, action) {
      state.submitting = false;
      state.error = String(action.payload || 'Failed to submit attendance');
    },
  },
});

export const {
  resetForTokenChange,
  tokenValidated,
  loadRequested,
  loadSucceeded,
  loadFailed,
  rowChanged,
  submitRequested,
  submitSucceeded,
  submitFailed,
} = attendanceTokenSlice.actions;

export default attendanceTokenSlice.reducer;
