import { call, put, select, takeLatest } from 'redux-saga/effects';

import { googleLogin, loginPassword, requestOtp, signupPassword, verifyOtp } from '../../services/api';
import {
  loginGoogleFailed,
  loginGoogleRequested,
  loginGoogleSucceeded,
  loginPasswordFailed,
  loginPasswordRequested,
  loginPasswordSucceeded,
  loginRequestOtpFailed,
  loginRequestOtpRequested,
  loginRequestOtpSucceeded,
  loginVerifyOtpFailed,
  loginVerifyOtpRequested,
  loginVerifyOtpSucceeded,
  signupGoogleFailed,
  signupGoogleRequested,
  signupGoogleSucceeded,
  signupPasswordFailed,
  signupPasswordRequested,
  signupPasswordSucceeded,
  signupRequestOtpFailed,
  signupRequestOtpRequested,
  signupRequestOtpSucceeded,
  signupVerifyOtpFailed,
  signupVerifyOtpRequested,
  signupVerifyOtpSucceeded,
} from '../slices/authSlice.js';

function resolveError(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

function* runSuccessCallback(action, data = null) {
  const onSuccess = action.payload?.onSuccess;
  if (typeof onSuccess === 'function') {
    yield call(onSuccess, data);
  }
}

function* loginRequestOtpWorker() {
  try {
    const phone = yield select((state) => state.auth?.login?.phone || '');
    yield call(requestOtp, phone);
    yield put(loginRequestOtpSucceeded());
  } catch (err) {
    yield put(loginRequestOtpFailed(resolveError(err, 'Failed to request OTP')));
  }
}

function* loginVerifyOtpWorker(action) {
  try {
    const loginState = yield select((state) => state.auth?.login || {});
    const payload = yield call(verifyOtp, loginState.phone, loginState.otp);
    yield put(loginVerifyOtpSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(loginVerifyOtpFailed(resolveError(err, 'OTP verification failed')));
  }
}

function* loginPasswordWorker(action) {
  try {
    const loginState = yield select((state) => state.auth?.login || {});
    const payload = yield call(loginPassword, loginState.phone, loginState.password);
    yield put(loginPasswordSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(loginPasswordFailed(resolveError(err, 'Password login failed')));
  }
}

function* loginGoogleWorker(action) {
  try {
    const payload = yield call(googleLogin, '');
    yield put(loginGoogleSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(loginGoogleFailed(resolveError(err, 'Google login failed')));
  }
}

function* signupRequestOtpWorker() {
  try {
    const phone = yield select((state) => state.auth?.signup?.phone || '');
    yield call(requestOtp, phone);
    yield put(signupRequestOtpSucceeded());
  } catch (err) {
    yield put(signupRequestOtpFailed(resolveError(err, 'Failed to request OTP')));
  }
}

function* signupVerifyOtpWorker(action) {
  try {
    const signupState = yield select((state) => state.auth?.signup || {});
    const payload = yield call(verifyOtp, signupState.phone, signupState.otp);
    yield put(signupVerifyOtpSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(signupVerifyOtpFailed(resolveError(err, 'OTP verification failed')));
  }
}

function* signupPasswordWorker(action) {
  try {
    const signupState = yield select((state) => state.auth?.signup || {});
    if (signupState.password !== signupState.confirmPassword) {
      throw new Error('Passwords do not match');
    }
    const payload = yield call(signupPassword, signupState.phone, signupState.password);
    yield put(signupPasswordSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(signupPasswordFailed(resolveError(err, 'Password signup failed')));
  }
}

function* signupGoogleWorker(action) {
  try {
    const payload = yield call(googleLogin, '');
    yield put(signupGoogleSucceeded());
    yield* runSuccessCallback(action, payload);
  } catch (err) {
    yield put(signupGoogleFailed(resolveError(err, 'Google signup failed')));
  }
}

export default function* authSaga() {
  yield takeLatest(loginRequestOtpRequested.type, loginRequestOtpWorker);
  yield takeLatest(loginVerifyOtpRequested.type, loginVerifyOtpWorker);
  yield takeLatest(loginPasswordRequested.type, loginPasswordWorker);
  yield takeLatest(loginGoogleRequested.type, loginGoogleWorker);

  yield takeLatest(signupRequestOtpRequested.type, signupRequestOtpWorker);
  yield takeLatest(signupVerifyOtpRequested.type, signupVerifyOtpWorker);
  yield takeLatest(signupPasswordRequested.type, signupPasswordWorker);
  yield takeLatest(signupGoogleRequested.type, signupGoogleWorker);
}
