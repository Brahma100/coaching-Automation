import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchTodayView, resolveInboxAction } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  resolveActionFailed,
  resolveActionRequested,
  resolveActionSucceeded,
} from '../slices/todaySlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  const teacherId = action.payload?.teacherId;
  try {
    const payload = yield call(fetchTodayView, {
      teacherId: teacherId || undefined,
      bypassCache: true,
    });
    yield put(loadSucceeded(payload));
  } catch (err) {
    yield put(loadFailed(resolveError(err, "Failed to load today's actions.")));
  }
}

function* resolveActionWorker(action) {
  const actionId = action.payload?.actionId;
  const teacherId = action.payload?.teacherId;
  if (!actionId) {
    yield put(resolveActionFailed('Failed to resolve action.'));
    return;
  }
  try {
    yield call(resolveInboxAction, actionId, 'Resolved from Today View');
    let payload = null;
    try {
      payload = yield call(fetchTodayView, {
        teacherId: teacherId || undefined,
        bypassCache: true,
      });
    } catch (err) {
      payload = null;
    }
    yield put(resolveActionSucceeded({ data: payload, actionId }));
  } catch (err) {
    yield put(resolveActionFailed(resolveError(err, 'Failed to resolve action.')));
  }
}

export default function* todaySaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(resolveActionRequested.type, resolveActionWorker);
}
