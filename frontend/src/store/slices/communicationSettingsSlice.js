import { createSlice } from '@reduxjs/toolkit';

export const EVENT_OPTIONS = [
  'CLASS_STARTED',
  'ATTENDANCE_SUBMITTED',
  'FEE_DUE',
  'HOMEWORK_ASSIGNED',
  'STUDENT_ADDED',
  'BATCH_RESCHEDULED',
  'DAILY_BRIEF',
];

const defaultConnection = { healthy: false, status: 'unknown', message: 'Checking...' };

const communicationSettingsSlice = createSlice({
  name: 'communicationSettings',
  initialState: {
    loading: true,
    saving: false,
    testing: false,
    healthLoading: false,
    provider: 'telegram',
    providerConfig: {},
    enabledEvents: EVENT_OPTIONS,
    quietStart: '22:00',
    quietEnd: '06:00',
    deleteTimer: 15,
    connection: defaultConnection,
    testMessage: 'Test message from Communication settings',
    feedback: '',
    error: '',
    communicationMode: 'embedded',
    externalDashboardUrl: '',
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
      state.provider = payload.provider || 'telegram';
      state.providerConfig = payload.providerConfig || {};
      state.enabledEvents = Array.isArray(payload.enabledEvents) ? payload.enabledEvents : EVENT_OPTIONS;
      state.quietStart = payload.quietStart || '22:00';
      state.quietEnd = payload.quietEnd || '06:00';
      state.deleteTimer = Number(payload.deleteTimer || 15);
      state.connection = payload.connection || defaultConnection;
      state.communicationMode = payload.communicationMode || 'embedded';
      state.externalDashboardUrl = payload.externalDashboardUrl || '';
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Could not load communication settings');
    },
    setProvider(state, action) {
      state.provider = String(action.payload || 'telegram');
      state.feedback = '';
    },
    setProviderConfigField(state, action) {
      const key = String(action.payload?.key || '');
      if (!key) return;
      state.providerConfig = {
        ...(state.providerConfig || {}),
        [key]: action.payload?.value || '',
      };
      state.feedback = '';
    },
    toggleEvent(state, action) {
      const eventType = String(action.payload || '');
      if (!eventType) return;
      const current = Array.isArray(state.enabledEvents) ? state.enabledEvents : [];
      state.enabledEvents = current.includes(eventType)
        ? current.filter((item) => item !== eventType)
        : [...current, eventType];
      state.feedback = '';
    },
    setQuietStart(state, action) {
      state.quietStart = String(action.payload || '22:00');
      state.feedback = '';
    },
    setQuietEnd(state, action) {
      state.quietEnd = String(action.payload || '06:00');
      state.feedback = '';
    },
    setDeleteTimer(state, action) {
      state.deleteTimer = action.payload;
      state.feedback = '';
    },
    setTestMessage(state, action) {
      state.testMessage = String(action.payload || '');
    },
    saveRequested(state) {
      state.saving = true;
      state.error = '';
      state.feedback = '';
    },
    saveSucceeded(state, action) {
      state.saving = false;
      state.error = '';
      state.feedback = 'Communication settings saved';
      if (action.payload?.connection) {
        state.connection = action.payload.connection;
      }
    },
    saveFailed(state, action) {
      state.saving = false;
      state.error = String(action.payload || 'Could not save communication settings');
    },
    healthCheckRequested(state) {
      state.healthLoading = true;
    },
    healthCheckSucceeded(state, action) {
      state.healthLoading = false;
      state.connection = action.payload || defaultConnection;
    },
    healthCheckFailed(state, action) {
      state.healthLoading = false;
      state.connection = {
        healthy: false,
        status: 'error',
        message: String(action.payload || 'Health check failed'),
      };
    },
    testRequested(state) {
      state.testing = true;
      state.error = '';
      state.feedback = '';
    },
    testSucceeded(state, action) {
      state.testing = false;
      state.error = '';
      state.connection = action.payload?.connection || state.connection;
      state.feedback = action.payload?.feedback || 'Test message sent';
    },
    testFailed(state, action) {
      state.testing = false;
      state.error = String(action.payload || 'Could not send test message');
    },
    clearFeedback(state) {
      state.feedback = '';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setProvider,
  setProviderConfigField,
  toggleEvent,
  setQuietStart,
  setQuietEnd,
  setDeleteTimer,
  setTestMessage,
  saveRequested,
  saveSucceeded,
  saveFailed,
  healthCheckRequested,
  healthCheckSucceeded,
  healthCheckFailed,
  testRequested,
  testSucceeded,
  testFailed,
  clearFeedback,
} = communicationSettingsSlice.actions;

export default communicationSettingsSlice.reducer;
