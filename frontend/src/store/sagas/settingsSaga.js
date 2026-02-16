import { all, call, put, select, takeLatest } from 'redux-saga/effects';

import {
  fetchRuleConfigEffective,
  fetchTeacherProfile,
  fetchTodayBrief,
  setGlobalToastDurationSeconds,
  updateTeacherProfile,
  upsertRuleConfig,
} from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveLifecycleRulesFailed,
  saveLifecycleRulesRequested,
  saveLifecycleRulesSucceeded,
  saveProfileFailed,
  saveProfileRequested,
  saveProfileSucceeded,
} from '../slices/settingsSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  const isAdmin = Boolean(action.payload?.isAdmin);
  try {
    const tasks = [call(fetchTodayBrief), call(fetchTeacherProfile)];
    if (isAdmin) tasks.push(call(fetchRuleConfigEffective));
    const [briefPayload, profilePayload, lifecycleRulesPayload] = yield all(tasks);
    const toastSeconds = Number(profilePayload?.ui_toast_duration_seconds ?? 5);
    yield call(setGlobalToastDurationSeconds, toastSeconds);
    yield put(loadSucceeded({
      brief: briefPayload || null,
      profile: profilePayload || null,
      deleteMinutes: profilePayload?.notification_delete_minutes ?? 15,
      enableAutoDeleteNotesOnExpiry: Boolean(profilePayload?.enable_auto_delete_notes_on_expiry),
      toastDurationSeconds: toastSeconds,
      lifecycleRuleConfig: isAdmin ? (lifecycleRulesPayload || null) : null,
      lifecycleNotificationsEnabled: isAdmin
        ? Boolean(lifecycleRulesPayload?.enable_student_lifecycle_notifications)
        : true,
    }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Could not load profile insights')));
  }
}

function* saveProfileWorker() {
  try {
    const state = yield select((root) => root.settings || {});
    const payload = yield call(updateTeacherProfile, {
      notification_delete_minutes: Number(state.deleteMinutes),
      enable_auto_delete_notes_on_expiry: Boolean(state.enableAutoDeleteNotesOnExpiry),
      ui_toast_duration_seconds: Number(state.toastDurationSeconds),
    });
    yield call(setGlobalToastDurationSeconds, payload?.ui_toast_duration_seconds ?? 5);
    yield put(saveProfileSucceeded(payload || {}));
  } catch (err) {
    yield put(saveProfileFailed(resolveError(err, 'Could not update profile')));
  }
}

function* saveLifecycleRulesWorker() {
  try {
    const state = yield select((root) => root.settings || {});
    yield call(upsertRuleConfig, {
      batch_id: null,
      absence_streak_threshold: Number(state.lifecycleRuleConfig?.absence_streak_threshold ?? 3),
      notify_parent_on_absence: Boolean(state.lifecycleRuleConfig?.notify_parent_on_absence ?? true),
      notify_parent_on_fee_due: Boolean(state.lifecycleRuleConfig?.notify_parent_on_fee_due ?? true),
      enable_student_lifecycle_notifications: Boolean(state.lifecycleNotificationsEnabled),
      reminder_grace_period_days: Number(state.lifecycleRuleConfig?.reminder_grace_period_days ?? 0),
      quiet_hours_start: String(state.lifecycleRuleConfig?.quiet_hours_start || '22:00'),
      quiet_hours_end: String(state.lifecycleRuleConfig?.quiet_hours_end || '06:00'),
    });
    const refreshed = yield call(fetchRuleConfigEffective);
    yield put(saveLifecycleRulesSucceeded(refreshed || null));
  } catch (err) {
    yield put(saveLifecycleRulesFailed(resolveError(err, 'Could not save lifecycle notification settings')));
  }
}

export default function* settingsSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(saveProfileRequested.type, saveProfileWorker);
  yield takeLatest(saveLifecycleRulesRequested.type, saveLifecycleRulesWorker);
}
