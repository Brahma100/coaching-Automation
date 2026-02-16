import { createSlice } from '@reduxjs/toolkit';

const defaultRules = {
  notify_on_attendance: true,
  class_start_reminder: true,
  fee_due_alerts: true,
  student_absence_escalation: true,
  homework_reminders: true,
};

const automationRulesSlice = createSlice({
  name: 'automationRules',
  initialState: {
    loading: true,
    saving: false,
    error: '',
    saved: '',
    rules: defaultRules,
  },
  reducers: {
    loadRequested(state) {
      state.loading = true;
      state.error = '';
    },
    loadSucceeded(state, action) {
      state.loading = false;
      state.error = '';
      state.rules = {
        ...defaultRules,
        ...(action.payload || {}),
      };
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Could not load automation rules');
    },
    toggleRule(state, action) {
      const key = String(action.payload || '');
      if (!Object.prototype.hasOwnProperty.call(state.rules, key)) return;
      state.rules[key] = !state.rules[key];
      state.saved = '';
    },
    saveRequested(state) {
      state.saving = true;
      state.error = '';
      state.saved = '';
    },
    saveSucceeded(state, action) {
      state.saving = false;
      state.error = '';
      state.saved = 'Automation rules saved';
      state.rules = {
        ...state.rules,
        ...(action.payload || {}),
      };
    },
    saveFailed(state, action) {
      state.saving = false;
      state.error = String(action.payload || 'Could not save automation rules');
    },
    clearSaved(state) {
      state.saved = '';
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  toggleRule,
  saveRequested,
  saveSucceeded,
  saveFailed,
  clearSaved,
} = automationRulesSlice.actions;

export default automationRulesSlice.reducer;
