import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchOperationalBrain } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
} from '../slices/brainSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  try {
    const payload = yield call(fetchOperationalBrain, {
      bypassCache: Boolean(action.payload?.bypassCache),
    });
    yield put(loadSucceeded(payload));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load operational brain')));
  }
}

export default function* brainSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
