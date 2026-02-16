import { call, put, select, takeLatest } from 'redux-saga/effects';

import { fetchTeacherAutomationRules, updateTeacherAutomationRules } from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveFailed,
  saveRequested,
  saveSucceeded,
} from '../slices/automationRulesSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker() {
  try {
    const payload = yield call(fetchTeacherAutomationRules);
    yield put(loadSucceeded(payload || {}));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Could not load automation rules')));
  }
}

function* saveWorker() {
  try {
    const rules = yield select((state) => state.automationRules?.rules || {});
    const payload = yield call(updateTeacherAutomationRules, rules);
    yield put(saveSucceeded(payload || rules));
  } catch (err) {
    yield put(saveFailed(resolveError(err, 'Could not save automation rules')));
  }
}

export default function* automationRulesSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(saveRequested.type, saveWorker);
}
