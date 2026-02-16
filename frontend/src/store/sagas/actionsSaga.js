import { call, put, takeLatest } from 'redux-saga/effects';

import {
  fetchActions,
  ignoreRiskAction,
  notifyRiskParent,
  resolveAction,
  reviewRiskAction,
} from '../../services/api';
import {
  loadFailed,
  loadRequested,
  loadSucceeded,
  runActionFailed,
  runActionRequested,
  runActionSucceeded,
} from '../slices/actionsSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* fetchRows() {
  const payload = yield call(fetchActions);
  return normalizeList(payload?.rows ?? payload);
}

function* loadWorker() {
  try {
    const rows = yield call(fetchRows);
    yield put(loadSucceeded(rows));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load actions')));
  }
}

function* runActionWorker(action) {
  const payload = action.payload || {};
  const rowId = Number(payload.rowId || 0);
  const kind = String(payload.kind || '');
  const note = String(payload.note || '');
  if (!rowId) {
    yield put(runActionFailed('Action failed'));
    return;
  }
  try {
    if (kind === 'resolve') {
      const response = yield call(resolveAction, rowId);
      if (response?.integration_required) {
        throw {
          integrationRequired: true,
          provider: response?.provider || 'telegram',
          integrationMessage: response?.message || 'Connect Telegram to enable notifications',
          message: response?.message || 'Integration required',
        };
      }
    } else if (kind === 'review') {
      const response = yield call(reviewRiskAction, rowId);
      if (response?.integration_required) {
        throw {
          integrationRequired: true,
          provider: response?.provider || 'telegram',
          integrationMessage: response?.message || 'Connect Telegram to enable notifications',
          message: response?.message || 'Integration required',
        };
      }
    } else if (kind === 'notify') {
      const response = yield call(notifyRiskParent, rowId);
      if (response?.integration_required) {
        throw {
          integrationRequired: true,
          provider: response?.provider || 'telegram',
          integrationMessage: response?.message || 'Connect Telegram to enable notifications',
          message: response?.message || 'Integration required',
        };
      }
    } else if (kind === 'ignore') {
      const response = yield call(ignoreRiskAction, rowId, note);
      if (response?.integration_required) {
        throw {
          integrationRequired: true,
          provider: response?.provider || 'telegram',
          integrationMessage: response?.message || 'Connect Telegram to enable notifications',
          message: response?.message || 'Integration required',
        };
      }
    } else {
      throw new Error('Action failed');
    }
    const rows = yield call(fetchRows);
    yield put(runActionSucceeded(rows));
  } catch (err) {
    if (err?.integrationRequired) {
      yield put(
        runActionFailed({
          message: err?.message || 'Integration required',
          integrationRequired: true,
          provider: err?.provider || 'telegram',
          integrationMessage: err?.integrationMessage || 'Connect Telegram to enable notifications',
        }),
      );
      return;
    }
    yield put(runActionFailed(resolveError(err, 'Action failed')));
  }
}

export default function* actionsSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(runActionRequested.type, runActionWorker);
}
