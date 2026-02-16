import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,
  timeout: 12000
});
const BACKEND = '/backend';
const TOAST_DURATION_MS_KEY = 'coaching-toast-duration-ms';
const DATA_SYNC_STORAGE_KEY = 'coaching:data-sync';
const DATA_SYNC_EVENT_NAME = 'coaching:data-sync';

let apiErrorNotifier = null;

function uniqueSyncId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function publishDataSync(domains = [], meta = {}) {
  if (typeof window === 'undefined') return;
  const safeDomains = Array.isArray(domains)
    ? [...new Set(domains.map((value) => String(value || '').trim()).filter(Boolean))]
    : [];
  if (!safeDomains.length) return;
  const payload = {
    id: uniqueSyncId(),
    ts: Date.now(),
    domains: safeDomains,
    ...meta,
  };
  try {
    window.dispatchEvent(new CustomEvent(DATA_SYNC_EVENT_NAME, { detail: payload }));
  } catch {
    // no-op
  }
  try {
    window.localStorage.setItem(DATA_SYNC_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // no-op
  }
}

export function subscribeDataSync(handler) {
  if (typeof window === 'undefined' || typeof handler !== 'function') return () => {};
  let lastSeenId = '';
  const consume = (payload) => {
    if (!payload || typeof payload !== 'object') return;
    if (payload.id && payload.id === lastSeenId) return;
    lastSeenId = payload.id || lastSeenId;
    handler(payload);
  };
  const onCustomEvent = (event) => {
    consume(event?.detail);
  };
  const onStorage = (event) => {
    if (event.key !== DATA_SYNC_STORAGE_KEY || !event.newValue) return;
    try {
      const payload = JSON.parse(event.newValue);
      consume(payload);
    } catch {
      // no-op
    }
  };
  window.addEventListener(DATA_SYNC_EVENT_NAME, onCustomEvent);
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(DATA_SYNC_EVENT_NAME, onCustomEvent);
    window.removeEventListener('storage', onStorage);
  };
}

function getDefaultToastDurationMs() {
  try {
    const raw = window.localStorage.getItem(TOAST_DURATION_MS_KEY);
    const value = Number(raw);
    if (Number.isFinite(value) && value >= 1000 && value <= 30000) return value;
  } catch {
    // no-op
  }
  return 5000;
}

export function setGlobalApiErrorNotifier(handler) {
  apiErrorNotifier = typeof handler === 'function' ? handler : null;
}

export function notifyGlobalToast({ tone = 'info', message = '', duration } = {}) {
  if (!apiErrorNotifier) return;
  apiErrorNotifier({
    tone,
    message: String(message || ''),
    duration: duration || getDefaultToastDurationMs(),
  });
}

export function setGlobalToastDurationSeconds(seconds) {
  const value = Number(seconds);
  const bounded = Number.isFinite(value) ? Math.max(1, Math.min(30, Math.round(value))) : 5;
  try {
    window.localStorage.setItem(TOAST_DURATION_MS_KEY, String(bounded * 1000));
  } catch {
    // no-op
  }
}

export function getGlobalToastDurationSeconds() {
  return Math.round(getDefaultToastDurationMs() / 1000);
}

function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .slice(0, 3)
      .map((item) => {
        if (!item || typeof item !== 'object') return String(item);
        const loc = Array.isArray(item.loc) ? item.loc.filter((part) => part !== 'body').join('.') : '';
        const msg = typeof item.msg === 'string' ? item.msg : '';
        if (loc && msg) return `${loc}: ${msg}`;
        if (msg) return msg;
        return '';
      })
      .filter(Boolean)
      .join(' | ') || 'Request failed';
  }
  if (detail && typeof detail === 'object') {
    try {
      return JSON.stringify(detail);
    } catch {
      return 'Request failed';
    }
  }
  if (typeof err?.message === 'string' && err.message.trim()) return err.message;
  return 'Request failed';
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const silent = Boolean(error?.config?.headers?.['x-silent-error-toast']);
    const canceled = error?.code === 'ERR_CANCELED';
    if (!silent && !canceled && apiErrorNotifier) {
      apiErrorNotifier({
        tone: 'error',
        message: formatApiError(error),
        duration: getDefaultToastDurationMs(),
      });
    }
    return Promise.reject(error);
  }
);

export async function requestOtp(phone) {
  const { data } = await api.post(`${BACKEND}/auth/request-otp`, { phone });
  return data;
}

export async function verifyOtp(phone, otp) {
  const { data } = await api.post(`${BACKEND}/auth/verify-otp`, { phone, otp, next: '/dashboard' });
  return data;
}

export async function signupPassword(phone, password) {
  const { data } = await api.post(`${BACKEND}/auth/signup-password`, { phone, password, next: '/dashboard' });
  return data;
}

export async function loginPassword(phone, password) {
  const { data } = await api.post(`${BACKEND}/auth/login-password`, { phone, password, next: '/dashboard' });
  return data;
}

export async function googleLogin(idToken = '') {
  const { data } = await api.post(`${BACKEND}/auth/google-login`, { id_token: idToken, next: '/dashboard' });
  return data;
}

export async function logout() {
  await api.post(`${BACKEND}/auth/logout`);
}

export async function onboardCheckSlug(slug, setupToken = '') {
  const params = new URLSearchParams();
  params.set('slug', String(slug || ''));
  const { data } = await api.get(`${BACKEND}/api/onboard/check-slug?${params.toString()}`);
  return data;
}

export async function onboardCreateCenter(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/center`, payload);
  return data;
}

export async function onboardFetchState(setupToken) {
  const params = new URLSearchParams();
  params.set('setup_token', String(setupToken || ''));
  const { data } = await api.get(`${BACKEND}/api/onboard/state?${params.toString()}`);
  return data;
}

export async function onboardReserveSlug(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/reserve-slug`, payload);
  return data;
}

export async function onboardCreateAdmin(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/admin`, payload);
  return data;
}

export async function onboardAcademicSetup(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/academic-setup`, payload);
  return data;
}

export async function onboardInviteTeachers(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/teachers`, payload);
  return data;
}

export async function onboardImportStudents(payload) {
  const body = new FormData();
  body.set('setup_token', String(payload?.setup_token || ''));
  if (payload?.file) body.set('file', payload.file);
  const { data } = await api.post(`${BACKEND}/api/onboard/students/import`, body, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function onboardFinish(payload) {
  const { data } = await api.post(`${BACKEND}/api/onboard/finish`, payload);
  return data;
}

export async function fetchActivationStatus() {
  const { data } = await api.get(`${BACKEND}/api/activation/status`);
  return data;
}

export async function completeActivation() {
  const { data } = await api.post(`${BACKEND}/api/activation/complete`);
  return data;
}

export async function fetchTodayBrief() {
  const { data } = await api.get(`${BACKEND}/api/teacher/brief/today`);
  return data;
}

export async function fetchTeacherProfile() {
  const { data } = await api.get(`${BACKEND}/api/teacher/profile`);
  return data;
}

export async function updateTeacherProfile(payload) {
  const { data } = await api.put(`${BACKEND}/api/teacher/profile`, payload);
  return data;
}

export async function fetchTelegramLinkStatus() {
  const { data } = await api.get(`${BACKEND}/api/telegram/link/status`);
  return data;
}

export async function startTelegramLink(ttlSeconds = 600) {
  const { data } = await api.post(`${BACKEND}/api/telegram/link/start`, { ttl_seconds: ttlSeconds });
  return data;
}

export async function fetchTeacherCommunicationSettings() {
  const { data } = await api.get(`${BACKEND}/api/teacher/communication-settings`);
  return data;
}

export async function fetchIntegrations() {
  const { data } = await api.get(`${BACKEND}/api/integrations`);
  return data;
}

export async function connectIntegration(provider, configJson = {}) {
  const { data } = await api.post(`${BACKEND}/api/integrations/${encodeURIComponent(String(provider || ''))}/connect`, {
    config_json: configJson,
  });
  return data;
}

export async function disconnectIntegration(provider) {
  const { data } = await api.post(`${BACKEND}/api/integrations/${encodeURIComponent(String(provider || ''))}/disconnect`, {});
  return data;
}

export async function updateTeacherCommunicationSettings(payload) {
  const { data } = await api.put(`${BACKEND}/api/teacher/communication-settings`, payload);
  return data;
}

export async function fetchTeacherCommunicationHealth() {
  const { data } = await api.get(`${BACKEND}/api/teacher/communication-settings/health`);
  return data;
}

export async function sendTeacherCommunicationTestMessage(message = 'Test message from Communication settings') {
  const { data } = await api.post(`${BACKEND}/api/teacher/communication-settings/test-message`, { message });
  return data;
}

export async function fetchTeacherAutomationRules() {
  const { data } = await api.get(`${BACKEND}/api/teacher/automation-rules`);
  return data;
}

export async function updateTeacherAutomationRules(payload) {
  const { data } = await api.put(`${BACKEND}/api/teacher/automation-rules`, payload);
  return data;
}

export async function fetchRuleConfigEffective(batchId = null) {
  const params = new URLSearchParams();
  if (batchId !== null && batchId !== undefined) params.set('batch_id', String(batchId));
  const query = params.toString();
  const { data } = await api.get(`${BACKEND}/rules/effective${query ? `?${query}` : ''}`);
  return data;
}

export async function upsertRuleConfig(payload) {
  const { data } = await api.post(`${BACKEND}/rules/upsert`, payload);
  return data;
}

export async function validateToken(token, sessionId, expectedType = '') {
  const params = new URLSearchParams();
  params.set('token', token || '');
  params.set('session_id', String(sessionId));
  if (expectedType) params.set('expected', expectedType);
  const { data } = await api.get(`${BACKEND}/api/tokens/validate?${params.toString()}`);
  return data;
}

export async function fetchSessionSummary(sessionId, token) {
  const params = new URLSearchParams();
  params.set('token', token || '');
  const { data } = await api.get(`${BACKEND}/api/session/summary/${sessionId}?${params.toString()}`);
  return data;
}

export async function fetchStudentMe() {
  const { data } = await api.get(`${BACKEND}/api/student/me`);
  return data;
}

export async function fetchStudentPreferences() {
  const { data } = await api.get(`${BACKEND}/api/student/preferences`);
  return data;
}

export async function updateStudentPreferences(payload) {
  const { data } = await api.put(`${BACKEND}/api/student/preferences`, payload);
  return data;
}

export async function fetchAdminOpsDashboard() {
  const { data } = await api.get(`${BACKEND}/api/admin/ops-dashboard`);
  return data;
}

export async function fetchStudents() {
  const { data } = await api.get(`${BACKEND}/students`);
  return data;
}

export async function createStudent(payload) {
  const body = new URLSearchParams();
  body.set('name', payload.name || '');
  body.set('phone', payload.phone || '');
  body.set('batch_id', String(payload.batch_id || ''));
  body.set('parent_phone', payload.parent_phone || '');
  await api.post(`${BACKEND}/students/create`, body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
}

export async function updateStudent(studentId, payload) {
  const { data } = await api.put(`${BACKEND}/students/${studentId}`, payload);
  return data;
}

export async function deleteStudent(studentId) {
  const { data } = await api.delete(`${BACKEND}/students/${studentId}`);
  return data;
}

export async function createReferral(studentId) {
  const { data } = await api.post(`${BACKEND}/referral/create`, { student_id: studentId });
  return data;
}

export async function fetchBatches() {
  const { data } = await api.get(`${BACKEND}/batches`);
  return data;
}

export async function fetchAdminBatches({ forDate } = {}) {
  const params = new URLSearchParams();
  if (forDate) params.set('for_date', String(forDate));
  const query = params.toString();
  const { data } = await api.get(`${BACKEND}/api/batches${query ? `?${query}` : ''}`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

export async function createBatch(payload) {
  const { data } = await api.post(`${BACKEND}/api/batches`, payload);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'create_batch' });
  return data;
}

export async function updateBatch(batchId, payload) {
  const { data } = await api.put(`${BACKEND}/api/batches/${batchId}`, payload);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'update_batch', batch_id: Number(batchId) || null });
  return data;
}

export async function deleteBatch(batchId) {
  const { data } = await api.delete(`${BACKEND}/api/batches/${batchId}`);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'delete_batch', batch_id: Number(batchId) || null });
  return data;
}

export async function addBatchSchedule(batchId, payload) {
  const { data } = await api.post(`${BACKEND}/api/batches/${batchId}/schedule`, payload);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'add_batch_schedule', batch_id: Number(batchId) || null });
  return data;
}

export async function updateBatchSchedule(scheduleId, payload) {
  const { data } = await api.put(`${BACKEND}/api/batch-schedules/${scheduleId}`, payload);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'update_batch_schedule', schedule_id: Number(scheduleId) || null });
  return data;
}

export async function deleteBatchSchedule(scheduleId) {
  const { data } = await api.delete(`${BACKEND}/api/batch-schedules/${scheduleId}`);
  publishDataSync(['batches', 'calendar', 'time_capacity'], { action: 'delete_batch_schedule', schedule_id: Number(scheduleId) || null });
  return data;
}

export async function fetchBatchStudents(batchId) {
  const { data } = await api.get(`${BACKEND}/api/batches/${batchId}/students`);
  return data;
}

export async function linkStudentToBatch(batchId, studentId) {
  const { data } = await api.post(`${BACKEND}/api/batches/${batchId}/students`, { student_id: studentId });
  publishDataSync(['batches', 'time_capacity'], { action: 'link_student_to_batch', batch_id: Number(batchId) || null, student_id: Number(studentId) || null });
  return data;
}

export async function unlinkStudentFromBatch(batchId, studentId) {
  const { data } = await api.delete(`${BACKEND}/api/batches/${batchId}/students/${studentId}`);
  publishDataSync(['batches', 'time_capacity'], { action: 'unlink_student_from_batch', batch_id: Number(batchId) || null, student_id: Number(studentId) || null });
  return data;
}

export async function fetchAttendanceByBatch(batchId) {
  const { data } = await api.get(`${BACKEND}/attendance/batch/${batchId}/today`);
  return data;
}

export async function fetchAttendanceManageOptions(batchId, attendanceDate) {
  const params = new URLSearchParams();
  if (batchId) params.set('batch_id', String(batchId));
  if (attendanceDate) params.set('attendance_date', String(attendanceDate));
  const query = params.toString() ? `?${params.toString()}` : '';
  const { data } = await api.get(`${BACKEND}/api/attendance/manage/options${query}`);
  return data;
}

export async function openAttendanceSession(payload) {
  const { data } = await api.post(`${BACKEND}/api/attendance/manage/open`, payload);
  return data;
}

export async function fetchAttendanceSession(sessionId, token = '') {
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  const { data } = await api.get(`${BACKEND}/api/attendance/session/${sessionId}${query}`);
  return data;
}

export async function submitAttendanceSession(sessionId, payload) {
  const { data } = await api.post(`${BACKEND}/api/attendance/session/${sessionId}/submit`, payload);
  return data;
}

export async function fetchFees() {
  const { data } = await api.get(`${BACKEND}/fee/dashboard`);
  return data;
}

export async function fetchHomework() {
  const { data } = await api.get(`${BACKEND}/homework/list`);
  return data;
}

export async function fetchNotes(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const { data } = await api.get(`${BACKEND}/api/notes${suffix}`);
  return data;
}

export async function fetchNotesMetadata() {
  const { data } = await api.get(`${BACKEND}/api/notes/metadata`);
  return data;
}

export async function fetchNotesAnalytics() {
  const { data } = await api.get(`${BACKEND}/api/notes/analytics`);
  return data;
}

export async function uploadNote(formData, onProgress) {
  const { data } = await api.post(`${BACKEND}/api/notes/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || 0;
      if (!total) {
        onProgress(0);
        return;
      }
      onProgress(Math.max(0, Math.min(100, Math.round((event.loaded / total) * 100))));
    }
  });
  return data;
}

export async function updateNote(noteId, formData, onProgress) {
  const { data } = await api.put(`${BACKEND}/api/notes/${noteId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || 0;
      if (!total) {
        onProgress(0);
        return;
      }
      onProgress(Math.max(0, Math.min(100, Math.round((event.loaded / total) * 100))));
    }
  });
  return data;
}

function extractFilename(contentDisposition, fallback = 'note.pdf') {
  if (!contentDisposition) return fallback;
  const utfMatch = contentDisposition.match(/filename\\*=UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
  const plainMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  if (plainMatch?.[1]) return plainMatch[1];
  return fallback;
}

export async function downloadNote(noteId, onProgress) {
  const response = await api.get(`${BACKEND}/api/notes/${noteId}/download`, {
    responseType: 'blob',
    timeout: 120000,
    onDownloadProgress: (event) => {
      if (!onProgress) return;
      const total = event.total || 0;
      if (!total) {
        onProgress(0);
        return;
      }
      onProgress(Math.max(0, Math.min(100, Math.round((event.loaded / total) * 100))));
    }
  });
  const fileName = extractFilename(response.headers?.['content-disposition'], `note-${noteId}.pdf`);
  const href = window.URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = href;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(href);
}

export async function deleteNote(noteId) {
  const { data } = await api.delete(`${BACKEND}/api/notes/${noteId}`);
  return data;
}

export async function fetchDriveStatus() {
  const { data } = await api.get(`${BACKEND}/api/drive/status`);
  return data;
}

export async function disconnectDrive() {
  const { data } = await api.post(`${BACKEND}/api/drive/disconnect`);
  return data;
}

export async function fetchActions() {
  const { data } = await api.get(`${BACKEND}/actions/list-open`);
  return data;
}

export async function resolveAction(actionId) {
  const { data } = await api.post(`${BACKEND}/actions/resolve`, { action_id: actionId });
  return data;
}

export async function resolveInboxAction(actionId, resolution_note = '') {
  const { data } = await api.post(`${BACKEND}/api/inbox/actions/${actionId}/resolve`, { resolution_note });
  return data;
}

export async function reviewRiskAction(actionId) {
  const { data } = await api.post(`${BACKEND}/actions/risk/${actionId}/review`, {});
  return data;
}

export async function ignoreRiskAction(actionId, note = '') {
  const { data } = await api.post(`${BACKEND}/actions/risk/${actionId}/ignore`, { note });
  return data;
}

export async function notifyRiskParent(actionId) {
  const { data } = await api.post(`${BACKEND}/actions/risk/${actionId}/notify-parent`, {});
  return data;
}

export async function fetchRisk() {
  const { data } = await api.get(`${BACKEND}/risk/students`);
  return data;
}

export async function fetchDashboardBundle() {
  const [brief, students, fees, homework, actions, risk, batches] = await Promise.all([
    fetchTodayBrief(),
    fetchStudents(),
    fetchFees(),
    fetchHomework(),
    fetchActions(),
    fetchRisk(),
    fetchBatches().catch(() => [])
  ]);

  return { brief, students, fees, homework, actions, risk, batches };
}

export async function fetchTodayView({ teacherId, bypassCache = false } = {}) {
  const params = new URLSearchParams();
  if (teacherId) params.set('teacher_id', String(teacherId));
  if (bypassCache) params.set('bypass_cache', '1');
  const query = params.toString();
  const { data } = await api.get(`${BACKEND}/api/dashboard/today${query ? `?${query}` : ''}`);
  return data;
}

export async function fetchOperationalBrain({ bypassCache = false } = {}) {
  const params = new URLSearchParams();
  if (bypassCache) params.set('bypass_cache', '1');
  const query = params.toString();
  const { data } = await api.get(`${BACKEND}/api/brain${query ? `?${query}` : ''}`);
  return data;
}

export async function fetchTeacherCalendar({ start, end, view = 'week', teacherId, bypassCache = false }) {
  const params = new URLSearchParams();
  params.set('start', start);
  params.set('end', end);
  params.set('view', view);
  if (teacherId) params.set('teacher_id', String(teacherId));
  if (bypassCache) params.set('bypass_cache', '1');
  const { data } = await api.get(`${BACKEND}/api/calendar?${params.toString()}`);
  return data;
}

export async function fetchCalendarSession(sessionId) {
  const { data } = await api.get(`${BACKEND}/api/calendar/session/${sessionId}`);
  return data;
}

export async function fetchCalendarAnalytics({ start, end, teacherId, bypassCache = false }) {
  const params = new URLSearchParams();
  params.set('start', start);
  params.set('end', end);
  if (teacherId) params.set('teacher_id', String(teacherId));
  if (bypassCache) params.set('bypass_cache', '1');
  const { data } = await api.get(`${BACKEND}/api/calendar/analytics?${params.toString()}`);
  return data;
}

export async function syncCalendarHolidays({ startYear, years = 5, countryCode = 'IN' } = {}) {
  const params = new URLSearchParams();
  if (startYear) params.set('start_year', String(startYear));
  params.set('years', String(years));
  params.set('country_code', String(countryCode || 'IN').toUpperCase());
  const { data } = await api.post(`${BACKEND}/api/calendar/holidays/sync?${params.toString()}`);
  return data;
}

export async function createCalendarOverride(payload) {
  const { data } = await api.post(`${BACKEND}/api/calendar/override`, payload);
  publishDataSync(['calendar', 'time_capacity'], { action: 'create_calendar_override', batch_id: Number(payload?.batch_id) || null });
  return data;
}

export async function updateCalendarOverride(overrideId, payload) {
  const { data } = await api.put(`${BACKEND}/api/calendar/override/${overrideId}`, payload);
  publishDataSync(['calendar', 'time_capacity'], { action: 'update_calendar_override', override_id: Number(overrideId) || null });
  return data;
}

export async function deleteCalendarOverride(overrideId) {
  const { data } = await api.delete(`${BACKEND}/api/calendar/override/${overrideId}`);
  publishDataSync(['calendar', 'time_capacity'], { action: 'delete_calendar_override', override_id: Number(overrideId) || null });
  return data;
}

export async function validateCalendarConflicts(payload) {
  const { data } = await api.post(`${BACKEND}/api/calendar/conflicts/validate`, payload);
  return data;
}

export async function fetchTimeAvailability({ date, teacherId } = {}) {
  const params = new URLSearchParams();
  params.set('date', String(date || ''));
  if (teacherId) params.set('teacher_id', String(teacherId));
  const { data } = await api.get(`${BACKEND}/api/time/availability?${params.toString()}`);
  return data?.data || {};
}

export async function fetchBatchCapacity() {
  const { data } = await api.get(`${BACKEND}/api/time/batch-capacity`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

export async function fetchRescheduleOptions({ batchId, date, teacherId } = {}) {
  const params = new URLSearchParams();
  params.set('batch_id', String(batchId || ''));
  params.set('date', String(date || ''));
  if (teacherId) params.set('teacher_id', String(teacherId));
  const { data } = await api.get(`${BACKEND}/api/time/reschedule-options?${params.toString()}`);
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

export async function fetchWeeklyLoad({ weekStart, teacherId } = {}) {
  const params = new URLSearchParams();
  params.set('week_start', String(weekStart || ''));
  if (teacherId) params.set('teacher_id', String(teacherId));
  const { data } = await api.get(`${BACKEND}/api/time/weekly-load?${params.toString()}`);
  return data?.data || {};
}

export async function createTimeBlock(payload) {
  const { data } = await api.post(`${BACKEND}/api/time/block`, payload);
  publishDataSync(['time_capacity', 'calendar'], { action: 'create_time_block' });
  return data?.data || {};
}

export async function deleteTimeBlock(blockId, teacherId) {
  const query = teacherId ? `?teacher_id=${encodeURIComponent(teacherId)}` : '';
  const { data } = await api.delete(`${BACKEND}/api/time/block/${blockId}${query}`);
  publishDataSync(['time_capacity', 'calendar'], { action: 'delete_time_block', block_id: Number(blockId) || null });
  return data?.data || { ok: false };
}

export default api;
