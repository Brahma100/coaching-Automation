import { all, call, put, select, takeLatest } from 'redux-saga/effects';

import {
  fetchTeacherCommunicationHealth,
  fetchTeacherCommunicationSettings,
  sendTeacherCommunicationTestMessage,
  updateTeacherCommunicationSettings,
} from '../../services/api';
import {
  healthCheckFailed,
  healthCheckRequested,
  healthCheckSucceeded,
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveFailed,
  saveRequested,
  saveSucceeded,
  testFailed,
  testRequested,
  testSucceeded,
} from '../slices/communicationSettingsSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const [settingsPayload, healthPayload] = yield all([
      call(fetchTeacherCommunicationSettings),
      call(fetchTeacherCommunicationHealth),
    ]);
    yield put(loadSucceeded({
      provider: settingsPayload?.provider || 'telegram',
      providerConfig: settingsPayload?.provider_config_json || {},
      enabledEvents: settingsPayload?.enabled_events,
      quietStart: settingsPayload?.quiet_hours?.start || '22:00',
      quietEnd: settingsPayload?.quiet_hours?.end || '06:00',
      deleteTimer: Number(settingsPayload?.delete_timer_minutes || 15),
      connection: healthPayload || settingsPayload?.connection_status || { healthy: false, status: 'unknown', message: 'Unknown' },
      communicationMode: String(settingsPayload?.communication_mode || 'embedded').toLowerCase(),
      externalDashboardUrl: String(settingsPayload?.external_dashboard_url || ''),
    }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Could not load communication settings')));
  }
}

function* saveWorker() {
  try {
    const state = yield select((root) => root.communicationSettings || {});
    const payload = yield call(updateTeacherCommunicationSettings, {
      provider: state.provider,
      provider_config_json: state.providerConfig,
      enabled_events: state.enabledEvents,
      quiet_hours: { start: state.quietStart, end: state.quietEnd },
      delete_timer_minutes: Number(state.deleteTimer || 15),
    });
    yield put(saveSucceeded({ connection: payload?.connection_status || state.connection }));
  } catch (err) {
    yield put(saveFailed(resolveError(err, 'Could not save communication settings')));
  }
}

function* healthCheckWorker() {
  try {
    const payload = yield call(fetchTeacherCommunicationHealth);
    yield put(healthCheckSucceeded(payload || { healthy: false, status: 'unknown', message: 'Unknown' }));
  } catch (err) {
    yield put(healthCheckFailed(resolveError(err, 'Health check failed')));
  }
}

function* testWorker() {
  try {
    const state = yield select((root) => root.communicationSettings || {});
    const payload = yield call(sendTeacherCommunicationTestMessage, state.testMessage);
    const ok = Boolean(payload?.result?.ok);
    yield put(testSucceeded({
      connection: payload?.connection_status || state.connection,
      feedback: ok ? 'Test message sent' : 'Test message failed',
    }));
  } catch (err) {
    yield put(testFailed(resolveError(err, 'Could not send test message')));
  }
}

export default function* communicationSettingsSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(saveRequested.type, saveWorker);
  yield takeLatest(healthCheckRequested.type, healthCheckWorker);
  yield takeLatest(testRequested.type, testWorker);
}
