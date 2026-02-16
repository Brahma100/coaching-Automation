import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchHomework } from '../../services/api';
import { loadFailed, loadRequested, loadSucceeded } from '../slices/homeworkSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchHomework);
    yield put(loadSucceeded(normalizeList(payload?.rows ?? payload)));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load homework')));
  }
}

export default function* homeworkSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
