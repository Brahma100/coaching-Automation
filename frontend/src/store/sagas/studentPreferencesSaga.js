import { call, put, select, takeLatest } from 'redux-saga/effects';

import { fetchStudentPreferences, updateStudentPreferences } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveFailed,
  saveRequested,
  saveSucceeded,
} from '../slices/studentPreferencesSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchStudentPreferences);
    yield put(loadSucceeded(payload || {}));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Could not load preferences.')));
  }
}

function* saveWorker() {
  try {
    const values = yield select((state) => state.studentPreferences?.values || {});
    const payload = yield call(updateStudentPreferences, values);
    yield put(saveSucceeded(payload || values));
  } catch (err) {
    yield put(saveFailed(resolveError(err, 'Could not save preferences.')));
  }
}

export default function* studentPreferencesSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(saveRequested.type, saveWorker);
}
