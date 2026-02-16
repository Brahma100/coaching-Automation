import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchAdminOpsDashboard } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
} from '../slices/adminOpsSlice.js';

function resolveError(err, fallback) {
  return {
    message: err?.response?.data?.detail || err?.message || fallback,
    status: err?.response?.status || null,
  };
}

function* loadWorker() {
  try {
    const payload = yield call(fetchAdminOpsDashboard);
    yield put(loadSucceeded({ data: payload || null, updatedAt: new Date().toISOString() }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Could not load operations dashboard')));
  }
}

export default function* adminOpsSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
