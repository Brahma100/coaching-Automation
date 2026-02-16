import { createSlice } from '@reduxjs/toolkit';

const defaultPreferences = {
  enable_daily_digest: true,
  enable_homework_reminders: true,
  enable_motivation_messages: true,
};

const studentPreferencesSlice = createSlice({
  name: 'studentPreferences',
  initialState: {
    loading: true,
    saving: false,
    error: '',
    success: '',
    values: defaultPreferences,
    initialValues: defaultPreferences,
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      const payload = action.payload || {};
      const next = {
        enable_daily_digest: payload.enable_daily_digest ?? true,
        enable_homework_reminders: payload.enable_homework_reminders ?? true,
        enable_motivation_messages: payload.enable_motivation_messages ?? true,
      };
      state.loading = false;
      state.error = '';
      state.success = '';
      state.values = next;
      state.initialValues = next;
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Could not load preferences.');
    },
    togglePreference(state, action) {
      const key = String(action.payload || '');
      if (!Object.prototype.hasOwnProperty.call(state.values, key)) return;
      state.values[key] = !state.values[key];
      state.success = '';
    },
    saveRequested(state) {
      state.saving = true;
      state.error = '';
      state.success = '';
    },
    saveSucceeded(state, action) {
      const payload = action.payload || {};
      const next = {
        enable_daily_digest: payload.enable_daily_digest ?? state.values.enable_daily_digest,
        enable_homework_reminders: payload.enable_homework_reminders ?? state.values.enable_homework_reminders,
        enable_motivation_messages: payload.enable_motivation_messages ?? state.values.enable_motivation_messages,
      };
      state.saving = false;
      state.error = '';
      state.success = 'Preferences saved';
      state.values = next;
      state.initialValues = next;
    },
    saveFailed(state, action) {
      state.saving = false;
      state.error = String(action.payload || 'Could not save preferences.');
    },
    clearSuccess(state) {
      state.success = '';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  togglePreference,
  saveRequested,
  saveSucceeded,
  saveFailed,
  clearSuccess,
} = studentPreferencesSlice.actions;

export default studentPreferencesSlice.reducer;
