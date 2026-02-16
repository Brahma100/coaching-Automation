import { createSlice } from '@reduxjs/toolkit';

const settingsSlice = createSlice({
  name: 'settings',
  initialState: {
    loading: false,
    error: '',
    brief: null,
    profile: null,
    notificationsOn: true,
    deleteMinutes: 15,
    enableAutoDeleteNotesOnExpiry: false,
    toastDurationSeconds: 5,
    savingProfile: false,
    lifecycleNotificationsEnabled: true,
    savingLifecycleRules: false,
    lifecycleRuleConfig: null,
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
      state.brief = payload.brief || null;
      state.profile = payload.profile || null;
      state.deleteMinutes = Number(payload.deleteMinutes ?? 15);
      state.enableAutoDeleteNotesOnExpiry = Boolean(payload.enableAutoDeleteNotesOnExpiry);
      state.toastDurationSeconds = Number(payload.toastDurationSeconds ?? 5);
      state.lifecycleRuleConfig = payload.lifecycleRuleConfig || null;
      state.lifecycleNotificationsEnabled = Boolean(payload.lifecycleNotificationsEnabled ?? true);
    },
    loadFailed(state, action) {
      state.loading = false;
      state.error = String(action.payload || 'Could not load profile insights');
    },
    setError(state, action) {
      state.error = String(action.payload || '');
    },
    clearError(state) {
      state.error = '';
    },
    setNotificationsOn(state, action) {
      state.notificationsOn = Boolean(action.payload);
    },
    setDeleteMinutes(state, action) {
      state.deleteMinutes = action.payload;
    },
    setEnableAutoDeleteNotesOnExpiry(state, action) {
      state.enableAutoDeleteNotesOnExpiry = Boolean(action.payload);
    },
    setToastDurationSeconds(state, action) {
      state.toastDurationSeconds = action.payload;
    },
    setLifecycleNotificationsEnabled(state, action) {
      state.lifecycleNotificationsEnabled = Boolean(action.payload);
    },
    saveProfileRequested(state) {
      state.savingProfile = true;
      state.error = '';
    },
    saveProfileSucceeded(state, action) {
      const payload = action.payload || {};
      state.savingProfile = false;
      state.error = '';
      state.profile = {
        ...(state.profile || {}),
        notification_delete_minutes: payload.notification_delete_minutes,
        enable_auto_delete_notes_on_expiry: Boolean(payload.enable_auto_delete_notes_on_expiry),
        ui_toast_duration_seconds: payload.ui_toast_duration_seconds ?? 5,
      };
      state.deleteMinutes = Number(payload.notification_delete_minutes ?? state.deleteMinutes);
      state.enableAutoDeleteNotesOnExpiry = Boolean(payload.enable_auto_delete_notes_on_expiry);
      state.toastDurationSeconds = Number(payload.ui_toast_duration_seconds ?? 5);
    },
    saveProfileFailed(state, action) {
      state.savingProfile = false;
      state.error = String(action.payload || 'Could not update profile');
    },
    saveLifecycleRulesRequested(state) {
      state.savingLifecycleRules = true;
      state.error = '';
    },
    saveLifecycleRulesSucceeded(state, action) {
      const payload = action.payload || null;
      state.savingLifecycleRules = false;
      state.error = '';
      state.lifecycleRuleConfig = payload;
      state.lifecycleNotificationsEnabled = Boolean(payload?.enable_student_lifecycle_notifications);
    },
    saveLifecycleRulesFailed(state, action) {
      state.savingLifecycleRules = false;
      state.error = String(action.payload || 'Could not save lifecycle notification settings');
    },
  },
});

export const {
  loadRequested,
  loadSucceeded,
  loadFailed,
  setError,
  clearError,
  setNotificationsOn,
  setDeleteMinutes,
  setEnableAutoDeleteNotesOnExpiry,
  setToastDurationSeconds,
  setLifecycleNotificationsEnabled,
  saveProfileRequested,
  saveProfileSucceeded,
  saveProfileFailed,
  saveLifecycleRulesRequested,
  saveLifecycleRulesSucceeded,
  saveLifecycleRulesFailed,
} = settingsSlice.actions;

export default settingsSlice.reducer;
