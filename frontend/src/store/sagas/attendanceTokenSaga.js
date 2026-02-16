import { call, put, select, takeLatest } from 'redux-saga/effects';

import { fetchAttendanceSession, submitAttendanceSession } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  submitFailed,
  submitRequested,
  submitSucceeded,
} from '../slices/attendanceTokenSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function normalizeStatus(value) {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'present') return 'Present';
  if (raw === 'absent') return 'Absent';
  if (raw === 'late') return 'Late';
  return 'Present';
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  const sessionId = action.payload?.sessionId;
  const token = action.payload?.token || '';
  if (!sessionId || !token) {
    yield put(loadFailed('Failed to load attendance sheet'));
    return;
  }
  try {
    const payload = yield call(fetchAttendanceSession, sessionId, token);
    yield put(loadSucceeded({ sheet: payload || null, rows: normalizeList(payload?.rows) }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load attendance sheet')));
  }
}

function* submitWorker(action) {
  const sessionId = Number(action.payload?.sessionId);
  const token = action.payload?.token || '';
  if (!sessionId) {
    yield put(submitFailed('Failed to submit attendance'));
    return;
  }
  try {
    const rows = yield select((state) => state.attendanceToken?.rows || []);
    yield call(submitAttendanceSession, sessionId, {
      token: token || null,
      records: rows.map((row) => ({
        student_id: row.student_id,
        status: normalizeStatus(row.status),
        comment: row.comment || '',
      })),
    });
    yield put(submitSucceeded());
  } catch (err) {
    yield put(submitFailed(resolveError(err, 'Failed to submit attendance')));
  }
}

export default function* attendanceTokenSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(submitRequested.type, submitWorker);
}
