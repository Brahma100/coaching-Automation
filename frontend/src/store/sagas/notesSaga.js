import { all, call, put, select, takeLatest } from 'redux-saga/effects';

import {
  deleteNote,
  disconnectDrive,
  downloadNote,
  fetchDriveStatus,
  fetchTeacherProfile,
  fetchNotes,
  fetchNotesAnalytics,
  fetchNotesMetadata,
  updateNote,
  uploadNote,
} from '../../services/api';
import {
  deleteFailed,
  deleteRequested,
  deleteSucceeded,
  disconnectDriveFailed,
  disconnectDriveRequested,
  disconnectDriveSucceeded,
  loadAutoDeletePrefFailed,
  loadAutoDeletePrefRequested,
  loadAutoDeletePrefSucceeded,
  loadDriveStatusFailed,
  loadDriveStatusRequested,
  loadDriveStatusSucceeded,
  loadFailed,
  loadRequested,
  loadSucceeded,
  downloadRequested,
  uploadRequested,
  autoDeleteRequested,
} from '../slices/notesSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* loadWorker(action) {
  const payload = action.payload || {};
  const providedFilters = payload.filters;
  const filters = providedFilters || (yield select((state) => state.notes?.filters || {}));
  try {
    const [notePayload, metaPayload, analyticsPayload] = yield all([
      call(fetchNotes, filters),
      call(fetchNotesMetadata),
      call(fetchNotesAnalytics),
    ]);
    yield put(loadSucceeded({
      notes: notePayload?.items || [],
      pagination: notePayload?.pagination || { page: 1, page_size: 12, total: 0, total_pages: 1 },
      metadata: metaPayload || { subjects: [], chapters: [], topics: [], tags: [], batches: [] },
      analytics: analyticsPayload || { total_notes: 0, total_subjects: 0, total_tags: 0, total_downloads: 0 },
    }));
  } catch (err) {
    yield put(loadFailed(resolveError(err, 'Failed to load notes')));
  }
}

export default function* notesSaga() {
  yield takeLatest(loadRequested.type, loadWorker);
  yield takeLatest(loadAutoDeletePrefRequested.type, loadAutoDeletePrefWorker);
  yield takeLatest(loadDriveStatusRequested.type, loadDriveStatusWorker);
  yield takeLatest(disconnectDriveRequested.type, disconnectDriveWorker);
  yield takeLatest(deleteRequested.type, deleteWorker);
  yield takeLatest(uploadRequested.type, uploadWorker);
  yield takeLatest(downloadRequested.type, downloadWorker);
  yield takeLatest(autoDeleteRequested.type, autoDeleteWorker);
}

function* loadAutoDeletePrefWorker() {
  try {
    const profile = yield call(fetchTeacherProfile);
    yield put(loadAutoDeletePrefSucceeded(Boolean(profile?.enable_auto_delete_notes_on_expiry)));
  } catch {
    yield put(loadAutoDeletePrefFailed());
  }
}

function* loadDriveStatusWorker() {
  try {
    const status = yield call(fetchDriveStatus);
    yield put(loadDriveStatusSucceeded(Boolean(status?.connected)));
  } catch {
    yield put(loadDriveStatusFailed());
  }
}

function* disconnectDriveWorker(action) {
  const onSuccess = action.payload?.onSuccess;
  const onError = action.payload?.onError;
  try {
    yield call(disconnectDrive);
    yield put(disconnectDriveSucceeded());
    if (typeof onSuccess === 'function') onSuccess();
  } catch (err) {
    yield put(disconnectDriveFailed());
    if (typeof onError === 'function') onError(resolveError(err, 'Could not disconnect Drive'));
  }
}

function* deleteWorker(action) {
  const noteId = Number(action.payload?.noteId || 0);
  const onSuccess = action.payload?.onSuccess;
  const onError = action.payload?.onError;
  if (!noteId) {
    yield put(deleteFailed('Delete failed'));
    if (typeof onError === 'function') onError('Delete failed');
    return;
  }
  try {
    yield call(deleteNote, noteId);
    yield put(deleteSucceeded());
    yield put(loadRequested());
    if (typeof onSuccess === 'function') onSuccess();
  } catch (err) {
    const message = resolveError(err, 'Delete failed');
    yield put(deleteFailed(message));
    if (typeof onError === 'function') onError(message);
  }
}

function* uploadWorker(action) {
  const payload = action.payload || {};
  const editingNoteId = Number(payload.editingNoteId || 0);
  const formData = payload.formData;
  const onProgress = payload.onProgress;
  const onSuccess = payload.onSuccess;
  const onError = payload.onError;
  try {
    const result = editingNoteId
      ? yield call(updateNote, editingNoteId, formData, onProgress)
      : yield call(uploadNote, formData, onProgress);
    yield put(loadRequested());
    if (typeof onSuccess === 'function') onSuccess(result);
  } catch (err) {
    if (typeof onError === 'function') {
      onError(resolveError(err, editingNoteId ? 'Update failed' : 'Upload failed'));
    }
  }
}

function* downloadWorker(action) {
  const payload = action.payload || {};
  const noteId = Number(payload.noteId || 0);
  const onProgress = payload.onProgress;
  const onSuccess = payload.onSuccess;
  const onError = payload.onError;
  if (!noteId) {
    if (typeof onError === 'function') onError('Download failed');
    return;
  }
  try {
    yield call(downloadNote, noteId, onProgress);
    yield put(loadRequested());
    if (typeof onSuccess === 'function') onSuccess();
  } catch (err) {
    if (typeof onError === 'function') onError(resolveError(err, 'Download failed'));
  }
}

function* autoDeleteWorker(action) {
  const noteIds = Array.isArray(action.payload?.noteIds) ? action.payload.noteIds : [];
  const onDone = action.payload?.onDone;
  if (!noteIds.length) {
    if (typeof onDone === 'function') onDone({ successCount: 0, failedCount: 0 });
    return;
  }
  const results = yield call(() => Promise.allSettled(noteIds.map((id) => deleteNote(id))));
  const successCount = results.filter((row) => row.status === 'fulfilled').length;
  const failedCount = results.length - successCount;
  if (successCount > 0) {
    yield put(loadRequested());
  }
  if (typeof onDone === 'function') onDone({ successCount, failedCount });
}
