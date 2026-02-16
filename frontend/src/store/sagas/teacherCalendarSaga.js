import { eventChannel } from 'redux-saga';
import { all, call, fork, put, select, take, takeLatest } from 'redux-saga/effects';

import {
  createCalendarOverride,
  deleteCalendarOverride,
  fetchBatches,
  fetchCalendarAnalytics,
  fetchCalendarSession,
  fetchTeacherCalendar,
  openAttendanceSession,
  subscribeDataSync,
  syncCalendarHolidays,
  updateCalendarOverride,
  validateCalendarConflicts,
} from '../../services/api';
import {
  createOverrideRequested,
  deleteOverrideRequested,
  loadAnalyticsFailed,
  loadAnalyticsRequested,
  loadAnalyticsSucceeded,
  loadCalendarFailed,
  loadCalendarRequested,
  loadCalendarSucceeded,
  loadSessionFailed,
  loadSessionRequested,
  loadSessionSucceeded,
  markHolidaySyncDone,
  openAttendanceRequested,
  updateOverrideRequested,
  validateConflictsRequested,
} from '../slices/teacherCalendarSlice.js';

const DEFAULT_PREFS = {
  snap_interval: 30,
  work_day_start: '07:00',
  work_day_end: '20:00',
  default_view: 'week',
};
const HOLIDAY_SYNC_STORAGE_KEY = 'teacherCalendar.holidaySyncAt';
const HOLIDAY_SYNC_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function formatDateLocal(dt) {
  const year = dt.getFullYear();
  const month = String(dt.getMonth() + 1).padStart(2, '0');
  const day = String(dt.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseCalendarDateTime(isoString) {
  if (!isoString || typeof isoString !== 'string') return new Date(isoString);
  const hasExplicitOffset = /([zZ]|[+-]\d{2}:\d{2})$/.test(isoString);
  if (hasExplicitOffset) return new Date(isoString);
  const match = isoString.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return new Date(isoString);
  const [, y, mo, d, h, mi, s] = match;
  return new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s || '0'), 0);
}

function minutesSinceMidnight(isoString) {
  const dt = parseCalendarDateTime(isoString);
  return dt.getHours() * 60 + dt.getMinutes();
}

function formatClockLabel(dt) {
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatTimeRange(startIso, endIso) {
  const start = formatClockLabel(parseCalendarDateTime(startIso));
  const end = formatClockLabel(parseCalendarDateTime(endIso));
  return `${start} - ${end}`;
}

function parsePreferences(raw) {
  if (!raw) return DEFAULT_PREFS;
  try {
    if (typeof raw === 'string') return { ...DEFAULT_PREFS, ...JSON.parse(raw) };
    return { ...DEFAULT_PREFS, ...raw };
  } catch {
    return DEFAULT_PREFS;
  }
}

function startOfWeek(sourceDate) {
  const dt = new Date(sourceDate);
  const day = dt.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  dt.setDate(dt.getDate() + diff);
  dt.setHours(0, 0, 0, 0);
  return dt;
}

function rangeForView(anchorDate, view) {
  const base = new Date(anchorDate);
  base.setHours(0, 0, 0, 0);
  if (view === 'day') return { start: base, end: base };
  if (view === 'week') {
    const start = startOfWeek(base);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return { start, end };
  }
  if (view === 'month') {
    const start = new Date(base.getFullYear(), base.getMonth(), 1);
    const end = new Date(base.getFullYear(), base.getMonth() + 1, 0);
    return { start, end };
  }
  const start = new Date(base);
  const end = new Date(base);
  end.setDate(start.getDate() + 13);
  return { start, end };
}

function buildEvents(items) {
  const now = new Date();
  const todayKey = formatDateLocal(now);
  return items.map((item) => {
    const uid = item.session_id ? `session-${item.session_id}` : `batch-${item.batch_id}-${item.start_datetime}`;
    const startMinutes = minutesSinceMidnight(item.start_datetime);
    const startDt = parseCalendarDateTime(item.start_datetime);
    const endDt = parseCalendarDateTime(item.end_datetime);
    const serverStatus = item.status || 'upcoming';
    const normalizedStatus = serverStatus === 'cancelled'
      ? 'cancelled'
      : (startDt <= now && endDt >= now ? 'live' : (endDt < now ? 'completed' : 'upcoming'));

    let colorClass = 'calendar-tone-default';
    const isCurrent = startDt <= now && endDt >= now;
    const isPast = endDt < now;
    const isUpcomingToday = formatDateLocal(startDt) === todayKey && startDt > now;
    if (isCurrent) colorClass = 'calendar-tone-current';
    else if (isPast) colorClass = 'calendar-tone-past';
    else if (isUpcomingToday) colorClass = 'calendar-tone-today-upcoming';

    return {
      ...item,
      status: normalizedStatus,
      uid,
      is_current: isCurrent,
      start_minutes: startMinutes,
      time_label: formatTimeRange(item.start_datetime, item.end_datetime),
      color_class: colorClass,
    };
  });
}

function normalizeList(value) {
  return Array.isArray(value) ? value : [];
}

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function createDataSyncChannel() {
  return eventChannel((emit) => {
    const unsubscribe = subscribeDataSync((event) => emit(event || {}));
    return () => {
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  });
}

function* safeFetchBatches() {
  try {
    return yield call(fetchBatches);
  } catch {
    return [];
  }
}

function* runHolidaySyncOnce() {
  const isDone = yield select((state) => Boolean(state.teacherCalendar?.holidaySyncDone));
  if (isDone) return;
  const nowMs = Date.now();
  try {
    const lastSyncRaw = window.localStorage.getItem(HOLIDAY_SYNC_STORAGE_KEY);
    const lastSyncMs = Number(lastSyncRaw || 0);
    if (Number.isFinite(lastSyncMs) && lastSyncMs > 0 && (nowMs - lastSyncMs) < HOLIDAY_SYNC_TTL_MS) {
      yield put(markHolidaySyncDone());
      return;
    }
  } catch {
    // Ignore storage access errors and continue.
  }
  yield put(markHolidaySyncDone());
  yield fork(function* holidaySyncTask() {
    try {
      yield call(syncCalendarHolidays, {
        startYear: new Date().getFullYear(),
        years: 1,
        countryCode: 'IN',
      });
      try {
        window.localStorage.setItem(HOLIDAY_SYNC_STORAGE_KEY, String(Date.now()));
      } catch {
        // Ignore storage write errors.
      }
    } catch {
      // Keep calendar usable even if holiday sync endpoint/API is temporarily unavailable.
    }
  });
}

function* loadCalendarWorker(action) {
  const payload = action.payload || {};
  const force = Boolean(payload.force);
  const start = String(payload.start || '');
  const end = String(payload.end || '');
  const view = String(payload.view || 'week');
  const teacherId = payload.teacherId;
  const isAdmin = Boolean(payload.isAdmin);
  try {
    const existingCatalog = yield select((state) => state.teacherCalendar?.batchCatalog || []);
    const shouldLoadCatalog = force || existingCatalog.length === 0;
    const calendarPayload = yield call(fetchTeacherCalendar, {
      start,
      end,
      view,
      teacherId: isAdmin ? teacherId : undefined,
      bypassCache: Boolean(force),
    });

    // Render calendar immediately; catalog hydration can finish in background.
    yield put(loadCalendarSucceeded({
      items: buildEvents(normalizeList(calendarPayload?.items)),
      batchCatalog: normalizeList(existingCatalog),
      holidays: normalizeList(calendarPayload?.holidays),
      preferences: parsePreferences(calendarPayload?.preferences),
    }));
    // Run holiday sync only after calendar render path is complete.
    yield fork(runHolidaySyncOnce);

    if (shouldLoadCatalog) {
      const batchesPayload = yield call(safeFetchBatches);
      const nextCatalog = normalizeList(batchesPayload);
      if (nextCatalog.length > 0) {
        const state = yield select((root) => root.teacherCalendar || {});
        yield put(loadCalendarSucceeded({
          items: normalizeList(state.items),
          batchCatalog: nextCatalog,
          holidays: normalizeList(state.holidays),
          preferences: state.preferences || DEFAULT_PREFS,
        }));
      }
    }
  } catch (err) {
    yield put(loadCalendarFailed(resolveError(err, 'Failed to load calendar.')));
  }
}

function* loadAnalyticsWorker(action) {
  const payload = action.payload || {};
  const start = String(payload.start || '');
  const end = String(payload.end || '');
  const teacherId = payload.teacherId;
  const isAdmin = Boolean(payload.isAdmin);
  try {
    const data = yield call(fetchCalendarAnalytics, {
      start,
      end,
      teacherId: isAdmin ? teacherId : undefined,
    });
    const map = {};
    (data?.days || []).forEach((row) => {
      if (row?.date) map[row.date] = row;
    });
    yield put(loadAnalyticsSucceeded(map));
  } catch {
    yield put(loadAnalyticsFailed());
  }
}

function* loadSessionWorker(action) {
  const sessionId = Number(action.payload?.sessionId || 0);
  if (!sessionId) {
    yield put(loadSessionSucceeded(null));
    return;
  }
  try {
    const details = yield call(fetchCalendarSession, sessionId);
    yield put(loadSessionSucceeded(details));
  } catch {
    yield put(loadSessionFailed());
  }
}

function* watchCalendarDataSync() {
  const channel = yield call(createDataSyncChannel);
  try {
    while (true) {
      const event = yield take(channel);
      const domains = Array.isArray(event?.domains) ? event.domains : [];
      if (!domains.includes('calendar') && !domains.includes('time_capacity') && !domains.includes('batches')) continue;
      const state = yield select((root) => root.teacherCalendar || {});
      const view = String(state.view || 'week');
      const anchorDate = String(state.anchorDate || formatDateLocal(new Date()));
      const range = rangeForView(new Date(anchorDate), view);
      yield put(loadCalendarRequested({
        force: false,
        silent: true,
        start: formatDateLocal(range.start),
        end: formatDateLocal(range.end),
        view,
        teacherId: state.teacherId || '',
        isAdmin: Boolean(state.isAdmin),
      }));
    }
  } finally {
    channel.close();
  }
}

function* openAttendanceWorker(action) {
  const payload = action.payload || {};
  try {
    const response = yield call(openAttendanceSession, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, response || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to open attendance';
      yield call(payload.onError, message);
    }
  }
}

function* validateConflictsWorker(action) {
  const payload = action.payload || {};
  try {
    const response = yield call(validateCalendarConflicts, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, response || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Conflict validation failed';
      yield call(payload.onError, message);
    }
  }
}

function* createOverrideWorker(action) {
  const payload = action.payload || {};
  try {
    const response = yield call(createCalendarOverride, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, response || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to save override';
      yield call(payload.onError, message);
    }
  }
}

function* updateOverrideWorker(action) {
  const payload = action.payload || {};
  try {
    const response = yield call(updateCalendarOverride, payload.overrideId, payload.body || {});
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess, response || {});
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to save override';
      yield call(payload.onError, message);
    }
  }
}

function* deleteOverrideWorker(action) {
  const payload = action.payload || {};
  try {
    yield call(deleteCalendarOverride, payload.overrideId);
    if (typeof payload.onSuccess === 'function') {
      yield call(payload.onSuccess);
    }
  } catch (err) {
    if (typeof payload.onError === 'function') {
      const message = err?.response?.data?.detail || err?.message || 'Failed to delete override';
      yield call(payload.onError, message);
    }
  }
}

export default function* teacherCalendarSaga() {
  yield fork(watchCalendarDataSync);
  yield takeLatest(loadCalendarRequested.type, loadCalendarWorker);
  yield takeLatest(loadAnalyticsRequested.type, loadAnalyticsWorker);
  yield takeLatest(loadSessionRequested.type, loadSessionWorker);
  yield takeLatest(openAttendanceRequested.type, openAttendanceWorker);
  yield takeLatest(validateConflictsRequested.type, validateConflictsWorker);
  yield takeLatest(createOverrideRequested.type, createOverrideWorker);
  yield takeLatest(updateOverrideRequested.type, updateOverrideWorker);
  yield takeLatest(deleteOverrideRequested.type, deleteOverrideWorker);
}
