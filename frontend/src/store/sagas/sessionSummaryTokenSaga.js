import { call, put, takeLatest } from 'redux-saga/effects';

import { fetchSessionSummary } from '../../services/api';
import { loadFailed, loadRequested, loadSucceeded } from '../slices/sessionSummaryTokenSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  const sessionId = action.payload?.sessionId;
  const token = action.payload?.token || '';
  if (!sessionId || !token) {
    yield put(loadFailed('Session summary unavailable.'));
    return;
  }
  try {
    const payload = yield call(fetchSessionSummary, sessionId, token);
    yield put(loadSucceeded(payload || null));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Session summary unavailable.')));
  }
}

export default function* sessionSummaryTokenSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
}
