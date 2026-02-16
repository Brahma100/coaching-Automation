import { all, fork } from 'redux-saga/effects';

import adminOpsSaga from './adminOpsSaga.js';
import actionsSaga from './actionsSaga.js';
import appSaga from './appSaga.js';
import attendanceSaga from './attendanceSaga.js';
import attendanceTokenSaga from './attendanceTokenSaga.js';
import authSaga from './authSaga.js';
import automationRulesSaga from './automationRulesSaga.js';
import batchesSaga from './batchesSaga.js';
import brainSaga from './brainSaga.js';
import communicationSettingsSaga from './communicationSettingsSaga.js';
import dashboardSaga from './dashboardSaga.js';
import feesSaga from './feesSaga.js';
import homeworkSaga from './homeworkSaga.js';
import notesSaga from './notesSaga.js';
import riskSaga from './riskSaga.js';
import sessionSummaryTokenSaga from './sessionSummaryTokenSaga.js';
import settingsSaga from './settingsSaga.js';
import studentPreferencesSaga from './studentPreferencesSaga.js';
import studentsSaga from './studentsSaga.js';
import teacherCalendarSaga from './teacherCalendarSaga.js';
import timeCapacitySaga from './timeCapacitySaga.js';
import todaySaga from './todaySaga.js';

export default function* rootSaga() {
  yield all([
    fork(appSaga),
    fork(adminOpsSaga),
    fork(actionsSaga),
    fork(attendanceSaga),
    fork(attendanceTokenSaga),
    fork(authSaga),
    fork(automationRulesSaga),
    fork(batchesSaga),
    fork(brainSaga),
    fork(communicationSettingsSaga),
    fork(dashboardSaga),
    fork(feesSaga),
    fork(homeworkSaga),
    fork(notesSaga),
    fork(riskSaga),
    fork(sessionSummaryTokenSaga),
    fork(settingsSaga),
    fork(studentPreferencesSaga),
    fork(studentsSaga),
    fork(teacherCalendarSaga),
    fork(timeCapacitySaga),
    fork(todaySaga),
  ]);
}
