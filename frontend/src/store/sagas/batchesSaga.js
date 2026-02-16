import { eventChannel } from 'redux-saga';
import { all, call, fork, put, select, take, takeLatest } from 'redux-saga/effects';

import {
  addBatchSchedule,
  createBatch,
  deleteBatch,
  deleteBatchSchedule,
  fetchAdminBatches,
  fetchBatchStudents,
  fetchStudents,
  linkStudentToBatch,
  unlinkStudentFromBatch,
  updateBatch,
  updateBatchSchedule,
  subscribeDataSync,
} from '../../services/api';
import {
  addScheduleFailed,
  addScheduleRequested,
  addScheduleSucceeded,
  deleteBatchFailed,
  deleteBatchRequested,
  deleteBatchSucceeded,
  deleteScheduleFailed,
  deleteScheduleRequested,
  deleteScheduleSucceeded,
  linkStudentFailed,
  linkStudentRequested,
  linkStudentSucceeded,
  loadBatchStudentsFailed,
  loadBatchStudentsRequested,
  loadBatchStudentsSucceeded,
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveBatchFailed,
  saveBatchRequested,
  saveBatchSucceeded,
  saveScheduleFailed,
  saveScheduleRequested,
  saveScheduleSucceeded,
  unlinkStudentFailed,
  unlinkStudentRequested,
  unlinkStudentSucceeded,
} from '../slices/batchesSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function toNullableNumber(value) {
  const parsed = Number(value || 0);
  return parsed > 0 ? parsed : null;
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function resolveSelectedBatchId({ prevSelectedBatchId, requestedBatchId, nextBatches }) {
  const prevId = toNullableNumber(prevSelectedBatchId);
  const requestedId = toNullableNumber(requestedBatchId);
  const firstId = toNullableNumber(nextBatches[0]?.id);
  const hasPrev = Boolean(prevId && nextBatches.some((row) => Number(row.id) === prevId));
  const hasPreferred = Boolean(requestedId && nextBatches.some((row) => Number(row.id) === requestedId));
  if (hasPrev && (!hasPreferred || prevId === requestedId)) return prevId;
  if (hasPreferred) return requestedId;
  return firstId;
}

function* loadWorker(action) {
  const payload = action.payload || {};
  const requestedBatchId = payload.requestedBatchId;
  const forDate = payload.forDate;
  try {
    const prevSelectedBatchId = yield select((state) => state.batches?.selectedBatchId);
    const [batchesPayload, studentsPayload] = yield all([
      call(fetchAdminBatches, { forDate }),
      call(fetchStudents),
    ]);
    const nextBatches = normalizeList(batchesPayload?.rows ?? batchesPayload);
    const nextStudents = normalizeList(studentsPayload?.rows ?? studentsPayload);
    const selectedBatchId = resolveSelectedBatchId({
      prevSelectedBatchId,
      requestedBatchId,
      nextBatches,
    });
    let batchStudents = [];
    if (selectedBatchId) {
      const linkedPayload = yield call(fetchBatchStudents, selectedBatchId);
      batchStudents = normalizeList(linkedPayload);
    }
    yield put(
      loadSucceeded({
        batches: nextBatches,
        students: nextStudents,
        selectedBatchId,
        batchStudents,
      })
    );
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load batches')));
  }
}

function* loadBatchStudentsWorker(action) {
  const batchId = toNullableNumber(action.payload?.batchId);
  if (!batchId) {
    yield put(loadBatchStudentsSucceeded([]));
    return;
  }
  try {
    const payload = yield call(fetchBatchStudents, batchId);
    yield put(loadBatchStudentsSucceeded(normalizeList(payload)));
  } catch {
    yield put(loadBatchStudentsFailed());
  }
}

function* saveBatchWorker(action) {
  const payload = action.payload || {};
  const mode = String(payload.mode || '');
  const batchId = toNullableNumber(payload.batchId);
  const form = payload.form || {};
  try {
    if (mode === 'add') {
      yield call(createBatch, form);
    } else if (batchId) {
      yield call(updateBatch, batchId, form);
    } else {
      throw new Error('Invalid batch target');
    }
    yield put(saveBatchSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(saveBatchFailed(resolveError(err, 'Batch save failed')));
  }
}

function* deleteBatchWorker(action) {
  const payload = action.payload || {};
  const batchId = toNullableNumber(payload.batchId);
  if (!batchId) {
    yield put(deleteBatchFailed('Batch delete failed'));
    return;
  }
  try {
    yield call(deleteBatch, batchId);
    yield put(deleteBatchSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(deleteBatchFailed(resolveError(err, 'Batch delete failed')));
  }
}

function* addScheduleWorker(action) {
  const payload = action.payload || {};
  const batchId = toNullableNumber(payload.batchId);
  if (!batchId) {
    yield put(addScheduleFailed('Schedule add failed'));
    return;
  }
  try {
    yield call(addBatchSchedule, batchId, {
      weekday: Number(payload.form?.weekday),
      start_time: payload.form?.start_time,
      duration_minutes: Number(payload.form?.duration_minutes),
    });
    yield put(addScheduleSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(addScheduleFailed(resolveError(err, 'Schedule add failed')));
  }
}

function* saveScheduleWorker(action) {
  const payload = action.payload || {};
  const scheduleId = toNullableNumber(payload.scheduleId);
  if (!scheduleId) {
    yield put(saveScheduleFailed('Schedule update failed'));
    return;
  }
  try {
    yield call(updateBatchSchedule, scheduleId, {
      weekday: Number(payload.form?.weekday),
      start_time: payload.form?.start_time,
      duration_minutes: Number(payload.form?.duration_minutes),
    });
    yield put(saveScheduleSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(saveScheduleFailed(resolveError(err, 'Schedule update failed')));
  }
}

function* deleteScheduleWorker(action) {
  const payload = action.payload || {};
  const scheduleId = toNullableNumber(payload.scheduleId);
  if (!scheduleId) {
    yield put(deleteScheduleFailed('Schedule delete failed'));
    return;
  }
  try {
    yield call(deleteBatchSchedule, scheduleId);
    yield put(deleteScheduleSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(deleteScheduleFailed(resolveError(err, 'Schedule delete failed')));
  }
}

function* linkStudentWorker(action) {
  const payload = action.payload || {};
  const batchId = toNullableNumber(payload.batchId);
  const studentId = toNullableNumber(payload.studentId);
  if (!batchId || !studentId) {
    yield put(linkStudentFailed('Student link failed'));
    return;
  }
  try {
    yield call(linkStudentToBatch, batchId, studentId);
    const linkedPayload = yield call(fetchBatchStudents, batchId);
    yield put(loadBatchStudentsSucceeded(normalizeList(linkedPayload)));
    yield put(linkStudentSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(linkStudentFailed(resolveError(err, 'Student link failed')));
  }
}

function* unlinkStudentWorker(action) {
  const payload = action.payload || {};
  const batchId = toNullableNumber(payload.batchId);
  const studentId = toNullableNumber(payload.studentId);
  if (!batchId || !studentId) {
    yield put(unlinkStudentFailed('Student unlink failed'));
    return;
  }
  try {
    yield call(unlinkStudentFromBatch, batchId, studentId);
    const linkedPayload = yield call(fetchBatchStudents, batchId);
    yield put(loadBatchStudentsSucceeded(normalizeList(linkedPayload)));
    yield put(unlinkStudentSucceeded());
    yield put(loadRequested({ requestedBatchId: payload.requestedBatchId, forDate: payload.forDate }));
  } catch (err) {
    yield put(unlinkStudentFailed(resolveError(err, 'Student unlink failed')));
  }
}

function toTodayInput() {
  return new Date().toISOString().slice(0, 10);
}

function createDataSyncChannel() {
  return eventChannel((emit) => {
    const unsubscribe = subscribeDataSync((event) => emit(event || {}));
    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  });
}

function* watchBatchesDataSync() {
  const channel = yield call(createDataSyncChannel);
  try {
    while (true) {
      const event = yield take(channel);
      const domains = Array.isArray(event?.domains) ? event.domains : [];
      if (!domains.includes('batches')) continue;
      const requestedBatchId = yield select((state) => state.batches?.requestedBatchId);
      yield put(loadRequested({ requestedBatchId, forDate: toTodayInput() }));
    }
  } finally {
    channel.close();
  }
}

export default function* batchesSaga() {
  yield fork(watchBatchesDataSync);
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(loadBatchStudentsRequested.type, loadBatchStudentsWorker);
  yield takeLatest(saveBatchRequested.type, saveBatchWorker);
  yield takeLatest(deleteBatchRequested.type, deleteBatchWorker);
  yield takeLatest(addScheduleRequested.type, addScheduleWorker);
  yield takeLatest(saveScheduleRequested.type, saveScheduleWorker);
  yield takeLatest(deleteScheduleRequested.type, deleteScheduleWorker);
  yield takeLatest(linkStudentRequested.type, linkStudentWorker);
  yield takeLatest(unlinkStudentRequested.type, unlinkStudentWorker);
}
