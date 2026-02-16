import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchFees } from '../../services/api';
import { loadFailed, loadRequested, loadSucceeded } from '../slices/feesSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchFees);
    yield put(loadSucceeded({
      due: normalizeList(payload?.due),
      overdue: normalizeList(payload?.overdue),
      paid: normalizeList(payload?.paid),
    }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load fees')));
  }
}

export default function* feesSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
