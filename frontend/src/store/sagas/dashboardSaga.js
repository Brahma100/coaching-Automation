import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchDashboardBundle } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
} from '../slices/dashboardSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchDashboardBundle);
    yield put(loadSucceeded(payload));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load dashboard')));
  }
}

export default function* dashboardSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
