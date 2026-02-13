import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,
  timeout: 12000
});
const BACKEND = '/backend';
const TOAST_DURATION_MS_KEY = 'coaching-toast-duration-ms';

let apiErrorNotifier = null;

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

export async function fetchAdminBatches() {
  const { data } = await api.get(`${BACKEND}/api/batches`);
  return data;
}

export async function createBatch(payload) {
  const { data } = await api.post(`${BACKEND}/api/batches`, payload);
  return data;
}

export async function updateBatch(batchId, payload) {
  const { data } = await api.put(`${BACKEND}/api/batches/${batchId}`, payload);
  return data;
}

export async function deleteBatch(batchId) {
  const { data } = await api.delete(`${BACKEND}/api/batches/${batchId}`);
  return data;
}

export async function addBatchSchedule(batchId, payload) {
  const { data } = await api.post(`${BACKEND}/api/batches/${batchId}/schedule`, payload);
  return data;
}

export async function updateBatchSchedule(scheduleId, payload) {
  const { data } = await api.put(`${BACKEND}/api/batch-schedules/${scheduleId}`, payload);
  return data;
}

export async function deleteBatchSchedule(scheduleId) {
  const { data } = await api.delete(`${BACKEND}/api/batch-schedules/${scheduleId}`);
  return data;
}

export async function fetchBatchStudents(batchId) {
  const { data } = await api.get(`${BACKEND}/api/batches/${batchId}/students`);
  return data;
}

export async function linkStudentToBatch(batchId, studentId) {
  const { data } = await api.post(`${BACKEND}/api/batches/${batchId}/students`, { student_id: studentId });
  return data;
}

export async function unlinkStudentFromBatch(batchId, studentId) {
  const { data } = await api.delete(`${BACKEND}/api/batches/${batchId}/students/${studentId}`);
  return data;
}

export async function fetchAttendanceByBatch(batchId) {
  const { data } = await api.get(`${BACKEND}/attendance/batch/${batchId}/today`);
  return data;
}

export async function fetchAttendanceManageOptions(batchId) {
  const query = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : '';
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

export async function fetchTodayView(teacherId) {
  const query = teacherId ? `?teacher_id=${encodeURIComponent(teacherId)}` : '';
  const { data } = await api.get(`${BACKEND}/api/dashboard/today${query}`);
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
  return data;
}

export async function updateCalendarOverride(overrideId, payload) {
  const { data } = await api.put(`${BACKEND}/api/calendar/override/${overrideId}`, payload);
  return data;
}

export async function deleteCalendarOverride(overrideId) {
  const { data } = await api.delete(`${BACKEND}/api/calendar/override/${overrideId}`);
  return data;
}

export async function validateCalendarConflicts(payload) {
  const { data } = await api.post(`${BACKEND}/api/calendar/conflicts/validate`, payload);
  return data;
}

export default api;
