import { call, put, takeLatest } from 'redux-saga/effects';

import {
  fetchAttendanceManageOptions,
  fetchAttendanceSession,
  openAttendanceSession,
  submitAttendanceSession,
} from '../../services/api';
import {
  loadOptionsFailed,
  loadOptionsRequested,
  loadOptionsSucceeded,
  loadSessionFailed,
  loadSessionRequested,
  loadSessionSucceeded,
  openSessionFailed,
  openSessionRequested,
  openSessionSucceeded,
  submitSessionFailed,
  submitSessionRequested,
  submitSessionSucceeded,
} from '../slices/attendanceSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadOptionsWorker(action) {
  const payload = action.payload || {};
  const batchId = String(payload.batchId || '');
  const preferredScheduleId = String(payload.preferredScheduleId || '');
  const attendanceDate = String(payload.attendanceDate || '');
  try {
    const response = yield call(fetchAttendanceManageOptions, batchId, attendanceDate);
    const batchRows = normalizeList(response?.batches);
    const scheduleRows = normalizeList(response?.schedules);
    const resolvedBatchId = String(response?.selected_batch_id || batchRows[0]?.id || '');
    const hasPreferredSchedule = Boolean(
      preferredScheduleId && scheduleRows.some((slot) => String(slot.id) === preferredScheduleId)
    );
    const resolvedScheduleId = hasPreferredSchedule ? preferredScheduleId : String(scheduleRows[0]?.id || '');
    yield put(
      loadOptionsSucceeded({
        batches: batchRows,
        schedules: scheduleRows,
        selectedBatchId: resolvedBatchId,
        selectedScheduleId: resolvedScheduleId,
      })
    );
  } catch (err) {
    yield put(loadOptionsFailed(resolveError(err, 'Failed to load attendance options')));
  }
}

function* loadSessionWorker(action) {
  const payload = action.payload || {};
  const sessionId = payload.sessionId;
  const token = String(payload.token || '');
  if (!sessionId) return;
  try {
    const response = yield call(fetchAttendanceSession, sessionId, token);
    yield put(
      loadSessionSucceeded({
        sheet: response || null,
        rows: normalizeList(response?.rows),
        selectedBatchId: String(response?.session?.batch_id || ''),
        selectedDate: response?.attendance_date ? String(response.attendance_date) : '',
      })
    );
  } catch (err) {
    yield put(loadSessionFailed(resolveError(err, 'Failed to load attendance sheet')));
  }
}

function* openSessionWorker(action) {
  const payload = action.payload || {};
  try {
    const response = yield call(openAttendanceSession, {
      batch_id: Number(payload.selectedBatchId),
      schedule_id: payload.selectedScheduleId ? Number(payload.selectedScheduleId) : null,
      attendance_date: payload.selectedDate,
    });
    const sessionId = String(response?.session_id || '');
    if (!sessionId) throw new Error('Session id missing in response');
    yield put(openSessionSucceeded({ sessionId }));
    yield put(loadSessionRequested({ sessionId, token: '' }));
  } catch (err) {
    yield put(openSessionFailed(resolveError(err, 'Failed to open attendance sheet')));
  }
}

function* submitSessionWorker(action) {
  const payload = action.payload || {};
  try {
    yield call(submitAttendanceSession, Number(payload.sessionId), {
      token: payload.token || null,
      records: normalizeList(payload.records),
    });
    yield put(submitSessionSucceeded());
    yield put(loadSessionRequested({ sessionId: String(payload.sessionId || ''), token: '' }));
  } catch (err) {
    yield put(submitSessionFailed(resolveError(err, 'Failed to submit attendance')));
  }
}

export default function* attendanceSaga() {
  yield takeLatest(loadOptionsRequested.type, loadOptionsWorker);
  yield takeLatest(loadSessionRequested.type, loadSessionWorker);
  yield takeLatest(openSessionRequested.type, openSessionWorker);
  yield takeLatest(submitSessionRequested.type, submitSessionWorker);
}
