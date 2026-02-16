import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchRisk } from '../../services/api';
import { loadFailed, loadRequested, loadSucceeded } from '../slices/riskSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchRisk);
    yield put(loadSucceeded(normalizeList(payload?.rows ?? payload)));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load risk insights')));
  }
}

export default function* riskSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
