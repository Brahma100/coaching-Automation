import { createSlice } from '@reduxjs/toolkit';

const initialLoginState = {
  mode: 'otp',
  otpStep: 'phone',
  phone: '',
  otp: '',
  password: '',
  loading: false,
  message: '',
  error: '',
};

const initialSignupState = {
  mode: 'otp',
  otpStep: 'phone',
  phone: '',
  otp: '',
  password: '',
  confirmPassword: '',
  loading: false,
  message: '',
  error: '',
};

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    login: initialLoginState,
    signup: initialSignupState,
  },
  reducers: {
    setLoginMode(state, action) {
      const mode = String(action.payload || 'otp');
      state.login.mode = mode;
      state.login.otpStep = 'phone';
      state.login.otp = '';
      state.login.message = '';
      state.login.error = '';
    },
    setLoginField(state, action) {
      const field = String(action.payload?.field || '');
      if (!field || !Object.prototype.hasOwnProperty.call(state.login, field)) return;
      state.login[field] = action.payload?.value || '';
    },
    setLoginOtpStep(state, action) {
      state.login.otpStep = String(action.payload || 'phone');
      if (state.login.otpStep === 'phone') {
        state.login.otp = '';
      }
      state.login.message = '';
      state.login.error = '';
    },
    loginRequestOtpRequested(state) {
      state.login.loading = true;
      state.login.error = '';
      state.login.message = '';
    },
    loginRequestOtpSucceeded(state) {
      state.login.loading = false;
      state.login.otpStep = 'otp';
      state.login.message = 'OTP sent via Telegram.';
    },
    loginRequestOtpFailed(state, action) {
      state.login.loading = false;
      state.login.error = String(action.payload || 'Failed to request OTP');
    },
    loginVerifyOtpRequested(state) {
      state.login.loading = true;
      state.login.error = '';
      state.login.message = '';
    },
    loginVerifyOtpSucceeded(state) {
      state.login.loading = false;
    },
    loginVerifyOtpFailed(state, action) {
      state.login.loading = false;
      state.login.error = String(action.payload || 'OTP verification failed');
    },
    loginPasswordRequested(state) {
      state.login.loading = true;
      state.login.error = '';
      state.login.message = '';
    },
    loginPasswordSucceeded(state) {
      state.login.loading = false;
    },
    loginPasswordFailed(state, action) {
      state.login.loading = false;
      state.login.error = String(action.payload || 'Password login failed');
    },
    loginGoogleRequested(state) {
      state.login.loading = true;
      state.login.error = '';
      state.login.message = '';
    },
    loginGoogleSucceeded(state) {
      state.login.loading = false;
    },
    loginGoogleFailed(state, action) {
      state.login.loading = false;
      state.login.error = String(action.payload || 'Google login failed');
    },

    setSignupMode(state, action) {
      const mode = String(action.payload || 'otp');
      state.signup.mode = mode;
      state.signup.otpStep = 'phone';
      state.signup.otp = '';
      state.signup.message = '';
      state.signup.error = '';
    },
    setSignupField(state, action) {
      const field = String(action.payload?.field || '');
      if (!field || !Object.prototype.hasOwnProperty.call(state.signup, field)) return;
      state.signup[field] = action.payload?.value || '';
    },
    setSignupOtpStep(state, action) {
      state.signup.otpStep = String(action.payload || 'phone');
      if (state.signup.otpStep === 'phone') {
        state.signup.otp = '';
      }
      state.signup.message = '';
      state.signup.error = '';
    },
    signupRequestOtpRequested(state) {
      state.signup.loading = true;
      state.signup.error = '';
      state.signup.message = '';
    },
    signupRequestOtpSucceeded(state) {
      state.signup.loading = false;
      state.signup.otpStep = 'otp';
      state.signup.message = 'OTP sent via Telegram.';
    },
    signupRequestOtpFailed(state, action) {
      state.signup.loading = false;
      state.signup.error = String(action.payload || 'Failed to request OTP');
    },
    signupVerifyOtpRequested(state) {
      state.signup.loading = true;
      state.signup.error = '';
      state.signup.message = '';
    },
    signupVerifyOtpSucceeded(state) {
      state.signup.loading = false;
    },
    signupVerifyOtpFailed(state, action) {
      state.signup.loading = false;
      state.signup.error = String(action.payload || 'OTP verification failed');
    },
    signupPasswordRequested(state) {
      state.signup.loading = true;
      state.signup.error = '';
      state.signup.message = '';
    },
    signupPasswordSucceeded(state) {
      state.signup.loading = false;
    },
    signupPasswordFailed(state, action) {
      state.signup.loading = false;
      state.signup.error = String(action.payload || 'Password signup failed');
    },
    signupGoogleRequested(state) {
      state.signup.loading = true;
      state.signup.error = '';
      state.signup.message = '';
    },
    signupGoogleSucceeded(state) {
      state.signup.loading = false;
    },
    signupGoogleFailed(state, action) {
      state.signup.loading = false;
      state.signup.error = String(action.payload || 'Google signup failed');
    },
  },
});

export const {
  setLoginMode,
  setLoginField,
  setLoginOtpStep,
  loginRequestOtpRequested,
  loginRequestOtpSucceeded,
  loginRequestOtpFailed,
  loginVerifyOtpRequested,
  loginVerifyOtpSucceeded,
  loginVerifyOtpFailed,
  loginPasswordRequested,
  loginPasswordSucceeded,
  loginPasswordFailed,
  loginGoogleRequested,
  loginGoogleSucceeded,
  loginGoogleFailed,
  setSignupMode,
  setSignupField,
  setSignupOtpStep,
  signupRequestOtpRequested,
  signupRequestOtpSucceeded,
  signupRequestOtpFailed,
  signupVerifyOtpRequested,
  signupVerifyOtpSucceeded,
  signupVerifyOtpFailed,
  signupPasswordRequested,
  signupPasswordSucceeded,
  signupPasswordFailed,
  signupGoogleRequested,
  signupGoogleSucceeded,
  signupGoogleFailed,
} = authSlice.actions;

export default authSlice.reducer;
