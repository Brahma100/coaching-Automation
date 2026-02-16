import { combineReducers } from '@reduxjs/toolkit';

import app from './slices/appSlice.js';
import adminOps from './slices/adminOpsSlice.js';
import actions from './slices/actionsSlice.js';
import attendance from './slices/attendanceSlice.js';
import attendanceToken from './slices/attendanceTokenSlice.js';
import auth from './slices/authSlice.js';
import automationRules from './slices/automationRulesSlice.js';
import batches from './slices/batchesSlice.js';
import brain from './slices/brainSlice.js';
import communicationSettings from './slices/communicationSettingsSlice.js';
import dashboard from './slices/dashboardSlice.js';
import fees from './slices/feesSlice.js';
import homework from './slices/homeworkSlice.js';
import notes from './slices/notesSlice.js';
import risk from './slices/riskSlice.js';
import sessionSummaryToken from './slices/sessionSummaryTokenSlice.js';
import settings from './slices/settingsSlice.js';
import studentPreferences from './slices/studentPreferencesSlice.js';
import students from './slices/studentsSlice.js';
import teacherCalendar from './slices/teacherCalendarSlice.js';
import timeCapacity from './slices/timeCapacitySlice.js';
import today from './slices/todaySlice.js';

const rootReducer = combineReducers({
  app,
  adminOps,
  actions,
  attendance,
  attendanceToken,
  auth,
  automationRules,
  batches,
  brain,
  communicationSettings,
  dashboard,
  fees,
  homework,
  notes,
  risk,
  sessionSummaryToken,
  settings,
  studentPreferences,
  students,
  teacherCalendar,
  timeCapacity,
  today,
});

export default rootReducer;
