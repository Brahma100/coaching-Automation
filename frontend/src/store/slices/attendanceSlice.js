import { createSlice } from '@reduxjs/toolkit';

function toToday() {
  return new Date().toISOString().slice(0, 10);
}

const initialState = {
  loadingOptions: true,
  opening: false,
  loadingSheet: false,
  submitting: false,
  error: '',
  success: '',
  batches: [],
  schedules: [],
  selectedBatchId: '',
  selectedScheduleId: '',
  selectedDate: toToday(),
  sheet: null,
  rows: [],
  sessionNavigationId: '',
  shouldClearToken: false,
};

const attendanceSlice = createSlice({
  name: 'attendance',
  initialState,
  reducers: {
    hydrateFromQuery(state, action) {
      const payload = action.payload || {};
      const today = payload.today || toToday();
      state.selectedBatchId = String(payload.queryBatchId || '');
      state.selectedScheduleId = String(payload.queryScheduleId || '');
      state.selectedDate = String(payload.queryDate || today);
    },
    setSelectedBatchId(state, action) {
      state.selectedBatchId = String(action.payload || '');
    },
    setSelectedScheduleId(state, action) {
      state.selectedScheduleId = String(action.payload || '');
    },
    setSelectedDate(state, action) {
      state.selectedDate = String(action.payload || toToday());
    },
    rowChanged(state, action) {
      const payload = action.payload || {};
      const studentId = Number(payload.studentId || 0);
      const field = String(payload.field || '');
      if (!studentId || !field) return;
      state.rows = (state.rows || []).map((row) =>
        Number(row.student_id) === studentId ? { ...row, [field]: payload.value } : row
      );
    },

    loadOptionsRequested(state) {
      state.loadingOptions = true;
      state.error = '';
    },
    loadOptionsSucceeded(state, action) {
      const payload = action.payload || {};
      state.loadingOptions = false;
      state.batches = Array.isArray(payload.batches) ? payload.batches : [];
      state.schedules = Array.isArray(payload.schedules) ? payload.schedules : [];
      state.selectedBatchId = String(payload.selectedBatchId || '');
      state.selectedScheduleId = String(payload.selectedScheduleId || '');
    },
    loadOptionsFailed(state, action) {
      state.loadingOptions = false;
      state.error = String(action.payload || 'Failed to load attendance options');
      state.batches = [];
      state.schedules = [];
    },

    loadSessionRequested(state) {
      state.loadingSheet = true;
      state.error = '';
    },
    loadSessionSucceeded(state, action) {
      const payload = action.payload || {};
      state.loadingSheet = false;
      state.sheet = payload.sheet || null;
      state.rows = Array.isArray(payload.rows) ? payload.rows : [];
      if (payload.selectedBatchId !== undefined) {
        state.selectedBatchId = String(payload.selectedBatchId || '');
      }
      if (payload.selectedDate) {
        state.selectedDate = String(payload.selectedDate);
      }
    },
    loadSessionFailed(state, action) {
      state.loadingSheet = false;
      state.sheet = null;
      state.rows = [];
      state.error = String(action.payload || 'Failed to load attendance sheet');
    },

    openSessionRequested(state) {
      state.opening = true;
      state.success = '';
      state.error = '';
      state.sheet = null;
      state.rows = [];
    },
    openSessionSucceeded(state, action) {
      const payload = action.payload || {};
      state.opening = false;
      state.success = 'Attendance sheet opened.';
      state.sessionNavigationId = String(payload.sessionId || '');
      state.shouldClearToken = true;
    },
    openSessionFailed(state, action) {
      state.opening = false;
      state.error = String(action.payload || 'Failed to open attendance sheet');
    },

    submitSessionRequested(state) {
      state.submitting = true;
      state.success = '';
      state.error = '';
    },
    submitSessionSucceeded(state) {
      state.submitting = false;
      state.success = 'Attendance submitted. Session is now locked.';
      state.shouldClearToken = true;
    },
    submitSessionFailed(state, action) {
      state.submitting = false;
      state.error = String(action.payload || 'Failed to submit attendance');
    },

    consumeSessionNavigation(state) {
      state.sessionNavigationId = '';
    },
    consumeTokenClear(state) {
      state.shouldClearToken = false;
    },
  },
});

export const {
  hydrateFromQuery,
  setSelectedBatchId,
  setSelectedScheduleId,
  setSelectedDate,
  rowChanged,
  loadOptionsRequested,
  loadOptionsSucceeded,
  loadOptionsFailed,
  loadSessionRequested,
  loadSessionSucceeded,
  loadSessionFailed,
  openSessionRequested,
  openSessionSucceeded,
  openSessionFailed,
  submitSessionRequested,
  submitSessionSucceeded,
  submitSessionFailed,
  consumeSessionNavigation,
  consumeTokenClear,
} = attendanceSlice.actions;

export default attendanceSlice.reducer;
