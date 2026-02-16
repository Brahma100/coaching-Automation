import { createSlice } from '@reduxjs/toolkit';

const DEFAULT_PREFS = {
  snap_interval: 30,
  work_day_start: '07:00',
  work_day_end: '20:00',
  default_view: 'week',
};

function toToday() {
  const dt = new Date();
  const year = dt.getFullYear();
  const month = String(dt.getMonth() + 1).padStart(2, '0');
  const day = String(dt.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const initialState = {
  loading: false,
  error: '',
  holidaySyncDone: false,
  items: [],
  batchCatalog: [],
  holidays: [],
  preferences: DEFAULT_PREFS,
  analyticsByDay: {},
  selectedSession: null,
  isAdmin: false,
  view: 'week',
  anchorDate: toToday(),
  teacherId: '',
  filters: { search: '', subject: '', academicLevel: '', room: '' },
  heatmapEnabled: false,
};

const teacherCalendarSlice = createSlice({
  name: 'teacherCalendar',
  initialState,
  reducers: {
    setView(state, action) {
      state.view = String(action.payload || 'week');
    },
    setAnchorDate(state, action) {
      state.anchorDate = String(action.payload || toToday());
    },
    setTeacherId(state, action) {
      state.teacherId = String(action.payload || '');
    },
    setFilters(state, action) {
      state.filters = action.payload || { search: '', subject: '', academicLevel: '', room: '' };
    },
    setHeatmapEnabled(state, action) {
      state.heatmapEnabled = Boolean(action.payload);
    },

    loadCalendarRequested(state, action) {
      state.loading = Boolean(action.payload?.silent) ? state.loading : true;
      state.error = '';
      state.isAdmin = Boolean(action.payload?.isAdmin);
    },
    loadCalendarSucceeded(state, action) {
      const payload = action.payload || {};
      state.loading = false;
      state.error = '';
      state.items = Array.isArray(payload.items) ? payload.items : [];
      state.batchCatalog = Array.isArray(payload.batchCatalog) ? payload.batchCatalog : [];
      state.holidays = Array.isArray(payload.holidays) ? payload.holidays : [];
      state.preferences = payload.preferences || DEFAULT_PREFS;
    },
    loadCalendarFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Failed to load calendar.');
    },

    loadAnalyticsRequested() {},
    loadAnalyticsSucceeded(state, action) {
      state.analyticsByDay = action.payload || {};
    },
    loadAnalyticsFailed(state) {
      state.analyticsByDay = {};
    },

    loadSessionRequested(state) {
      state.selectedSession = null;
    },
    loadSessionSucceeded(state, action) {
      state.selectedSession = action.payload || null;
    },
    loadSessionFailed(state) {
      state.selectedSession = null;
    },

    markHolidaySyncDone(state) {
      state.holidaySyncDone = true;
    },
    patchEventByUid(state, action) {
      const payload = action.payload || {};
      const uid = payload.uid;
      if (!uid) return;
      state.items = (state.items || []).map((item) => (item.uid === uid ? { ...item, ...(payload.updates || {}) } : item));
    },
    setCalendarError(state, action) {
      state.error = String(action.payload || '');
    },
    clearCalendarError(state) {
      state.error = '';
    },
    openAttendanceRequested() {},
    validateConflictsRequested() {},
    createOverrideRequested() {},
    updateOverrideRequested() {},
    deleteOverrideRequested() {},
  },
});

export const {
  setView,
  setAnchorDate,
  setTeacherId,
  setFilters,
  setHeatmapEnabled,
  loadCalendarRequested,
  loadCalendarSucceeded,
  loadCalendarFailed,
  loadAnalyticsRequested,
  loadAnalyticsSucceeded,
  loadAnalyticsFailed,
  loadSessionRequested,
  loadSessionSucceeded,
  loadSessionFailed,
  markHolidaySyncDone,
  patchEventByUid,
  setCalendarError,
  clearCalendarError,
  openAttendanceRequested,
  validateConflictsRequested,
  createOverrideRequested,
  updateOverrideRequested,
  deleteOverrideRequested,
} = teacherCalendarSlice.actions;

export default teacherCalendarSlice.reducer;
