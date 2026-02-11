import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  withCredentials: true,
  timeout: 12000
});
const BACKEND = '/backend';

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
  const { data } = await api.get(`${BACKEND}/api/calendar/${sessionId}`);
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
