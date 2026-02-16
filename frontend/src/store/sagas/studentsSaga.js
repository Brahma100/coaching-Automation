import { all, call, put, takeLatest } from 'redux-saga/effects';

import {
  createReferral,
  createStudent,
  deleteStudent,
  fetchBatches,
  fetchStudents,
  updateStudent,
} from '../../services/api';
import {
  addReferralFailed,
  addReferralRequested,
  addReferralSucceeded,
  deleteStudentFailed,
  deleteStudentRequested,
  deleteStudentSucceeded,
  loadFailed,
  loadRequested,
  loadSucceeded,
  saveStudentFailed,
  saveStudentRequested,
  saveStudentSucceeded,
} from '../slices/studentsSlice.js';

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* safeFetchBatches() {
  try {
    const payload = yield call(fetchBatches);
    return payload;
  } catch {
    return [];
  }
}

function* loadWorker() {
  try {
    const [studentsPayload, batchesPayload] = yield all([
      call(fetchStudents),
      call(safeFetchBatches),
    ]);
    const rows = normalizeList(studentsPayload?.rows ?? studentsPayload);
    const batches = normalizeList(batchesPayload?.rows ?? batchesPayload);
    yield put(loadSucceeded({ rows, batches }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load students')));
  }
}

function* saveStudentWorker(action) {
  const payload = action.payload || {};
  const mode = String(payload.mode || '');
  const formData = payload.formData || {};
  const editingStudentId = Number(payload.editingStudentId || 0);
  if (!String(formData.name || '').trim() || !String(formData.batch_id || '')) {
    yield put(saveStudentFailed('Name and Batch are required'));
    return;
  }
  try {
    if (mode === 'add') {
      yield call(createStudent, formData);
    } else if (editingStudentId > 0) {
      yield call(updateStudent, editingStudentId, {
        name: formData.name,
        phone: formData.phone,
        batch_id: Number(formData.batch_id),
        parent_phone: formData.parent_phone,
      });
    } else {
      throw new Error('Invalid student target');
    }
    yield put(saveStudentSucceeded());
    yield put(loadRequested());
  } catch (err) {
    yield put(saveStudentFailed(resolveError(err, 'Save failed')));
  }
}

function* deleteStudentWorker(action) {
  const studentId = Number(action.payload?.studentId || 0);
  if (!studentId) {
    yield put(deleteStudentFailed('Delete failed'));
    return;
  }
  try {
    yield call(deleteStudent, studentId);
    yield put(deleteStudentSucceeded());
    yield put(loadRequested());
  } catch (err) {
    yield put(deleteStudentFailed(resolveError(err, 'Delete failed')));
  }
}

function* addReferralWorker(action) {
  const studentId = Number(action.payload?.studentId || 0);
  if (!studentId) {
    yield put(addReferralFailed('Referral failed'));
    return;
  }
  try {
    yield call(createReferral, studentId);
    yield put(addReferralSucceeded());
  } catch (err) {
    yield put(addReferralFailed(resolveError(err, 'Referral failed')));
  }
}

export default function* studentsSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(saveStudentRequested.type, saveStudentWorker);
  yield takeLatest(deleteStudentRequested.type, deleteStudentWorker);
  yield takeLatest(addReferralRequested.type, addReferralWorker);
}
