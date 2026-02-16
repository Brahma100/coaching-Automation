import { eventChannel } from 'redux-saga';
import { all, call, fork, put, take, takeLatest } from 'redux-saga/effects';

import {
  createCalendarOverride,
  createTimeBlock,
  deleteTimeBlock,
  fetchAdminBatches,
  fetchBatchCapacity,
  fetchRescheduleOptions,
  fetchTimeAvailability,
  fetchWeeklyLoad,
  subscribeDataSync,
} from '../../services/api';
import {
  createOverrideRequested,
  createTimeBlockRequested,
  deleteTimeBlockRequested,
  incrementSyncTick,
  loadAvailabilityFailed,
  loadAvailabilityRequested,
  loadAvailabilitySucceeded,
  loadBatchesFailed,
  loadBatchesRequested,
  loadBatchesSucceeded,
  loadCapacityFailed,
  loadCapacityRequested,
  loadCapacitySucceeded,
  loadRescheduleFailed,
  loadRescheduleRequested,
  loadRescheduleSucceeded,
  loadWeeklyFailed,
  loadWeeklyRequested,
  loadWeeklySucceeded,
} from '../slices/timeCapacitySlice.js';

function addDaysToInputDate(inputDate, daysToAdd) {
  const base = new Date(`${inputDate}T00:00:00`);
  if (Number.isNaN(base.getTime())) return inputDate;
  base.setDate(base.getDate() + Number(daysToAdd || 0));
  return base.toISOString().slice(0, 10);
}

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function* loadBatchesWorker(action) {
  try {
    const forDate = action.payload?.forDate;
    const rows = yield call(fetchAdminBatches, { forDate });
    yield put(loadBatchesSucceeded(normalizeList(rows).filter((row) => row?.active !== false)));
  } catch {
    yield put(loadBatchesFailed());
  }
}

function* loadAvailabilityWorker(action) {
  try {
    const date = action.payload?.date;
    const data = yield call(fetchTimeAvailability, { date });
    yield put(loadAvailabilitySucceeded(data || { busy_slots: [], free_slots: [] }));
  } catch {
    yield put(loadAvailabilityFailed());
  }
}

function* loadCapacityWorker() {
  try {
    const rows = yield call(fetchBatchCapacity);
    yield put(loadCapacitySucceeded(normalizeList(rows)));
  } catch {
    yield put(loadCapacityFailed());
  }
}

function* loadRescheduleWorker(action) {
  const payload = action.payload || {};
  const batchId = payload.batchId;
  const date = payload.date;
  const weeksVisible = Math.max(1, Number(payload.weeksVisible || 1));
  if (!batchId) {
    yield put(loadRescheduleSucceeded([]));
    return;
  }
  try {
    const requests = Array.from({ length: weeksVisible }, (_, idx) => (
      call(fetchRescheduleOptions, {
        batchId,
        date: addDaysToInputDate(date, idx * 7),
      })
    ));
    const results = yield all(requests);
    const merged = [];
    for (const rows of results) {
      if (Array.isArray(rows)) merged.push(...rows);
    }
    const deduped = [];
    const seen = new Set();
    for (const row of merged.sort((a, b) => String(a.start || '').localeCompare(String(b.start || '')))) {
      const key = `${row.batch_id || batchId}:${row.start || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(row);
    }
    yield put(loadRescheduleSucceeded(deduped));
  } catch {
    yield put(loadRescheduleFailed());
  }
}

function* loadWeeklyWorker(action) {
  try {
    const weekStart = action.payload?.weekStart;
    const data = yield call(fetchWeeklyLoad, { weekStart });
    yield put(loadWeeklySucceeded(data || { daily_hours: [] }));
  } catch {
    yield put(loadWeeklyFailed());
  }
}

function createDataSyncChannel() {
  return eventChannel((emit) => {
    const unsubscribe = subscribeDataSync((event) => emit(event || {}));
    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  });
}

function* watchTimeCapacityDataSync() {
  const channel = yield call(createDataSyncChannel);
  try {
    while (true) {
      const event = yield take(channel);
      const domains = Array.isArray(event?.domains) ? event.domains : [];
      if (!domains.includes('time_capacity') && !domains.includes('calendar') && !domains.includes('batches')) continue;
      yield put(incrementSyncTick());
    }
  } finally {
    channel.close();
  }
}

function* createTimeBlockWorker(action) {
  const payload = action.payload || {};
  try {
    const row = yield call(createTimeBlock, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, row || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to create time block';
      yield call(payload.onError, message);
    }
  }
}

function* deleteTimeBlockWorker(action) {
  const payload = action.payload || {};
  try {
    yield call(deleteTimeBlock, payload.blockId);
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess);
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to delete time block';
      yield call(payload.onError, message);
    }
  }
}

function* createOverrideWorker(action) {
  const payload = action.payload || {};
  try {
    const row = yield call(createCalendarOverride, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, row || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to save override';
      yield call(payload.onError, message);
    }
  }
}

export default function* timeCapacitySaga() {
  yield fork(watchTimeCapacityDataSync);
  yield takeLatest(loadBatchesRequested.type, loadBatchesWorker);
  yield takeLatest(loadAvailabilityRequested.type, loadAvailabilityWorker);
  yield takeLatest(loadCapacityRequested.type, loadCapacityWorker);
  yield takeLatest(loadRescheduleRequested.type, loadRescheduleWorker);
  yield takeLatest(loadWeeklyRequested.type, loadWeeklyWorker);
  yield takeLatest(createTimeBlockRequested.type, createTimeBlockWorker);
  yield takeLatest(deleteTimeBlockRequested.type, deleteTimeBlockWorker);
  yield takeLatest(createOverrideRequested.type, createOverrideWorker);
}
