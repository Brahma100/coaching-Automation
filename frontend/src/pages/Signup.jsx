import React from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FiMoon, FiSun } from 'react-icons/fi';
import { useDispatch, useSelector } from 'react-redux';

import boyReading from '../assets/boy-reading.png';
import useTheme from '../hooks/useTheme';
import {
  setSignupField,
  setSignupMode,
  setSignupOtpStep,
  signupGoogleRequested,
  signupPasswordRequested,
  signupRequestOtpRequested,
  signupVerifyOtpRequested,
} from '../store/slices/authSlice.js';

function Signup() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isDark, toggleTheme } = useTheme();
  const { mode, otpStep, phone, otp, password, confirmPassword, loading, message, error } = useSelector((state) => state.auth?.signup || {});

  const goNext = React.useCallback(() => {
    const next = searchParams.get('next') || '/dashboard';
    navigate(next, { replace: true });
  }, [navigate, searchParams]);

  const onRequestOtp = (event) => {
    event.preventDefault();
    dispatch(signupRequestOtpRequested());
  };

  const onVerifyOtpSignup = (event) => {
    event.preventDefault();
    dispatch(signupVerifyOtpRequested({ onSuccess: goNext }));
  };

  const onPasswordSignup = (event) => {
    event.preventDefault();
    dispatch(signupPasswordRequested({ onSuccess: goNext }));
  };

  const onGoogleSignup = () => {
    dispatch(signupGoogleRequested({ onSuccess: goNext }));
  };

  return (
    <div className="auth-shell flex min-h-screen items-center justify-center p-4 lg:p-8">
      <div className="w-full max-w-[1120px]">
      <div className="auth-card mx-auto grid w-full overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl lg:grid-cols-[440px,1fr] dark:border-slate-700 dark:bg-slate-900">
        <aside className="relative hidden lg:block">
          <div className="absolute inset-0 bg-[#f25c05]" />
          <img src={boyReading} alt="Student reading" className="relative h-full w-full object-cover" />
        </aside>
        <main className="relative p-8 sm:p-12">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="absolute right-6 top-6 grid h-10 w-10 place-items-center rounded-full border border-slate-300 bg-white text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
          >
            {isDark ? <FiSun className="h-4 w-4" /> : <FiMoon className="h-4 w-4" />}
          </button>
          <div className="mb-8">
            <p className="text-2xl font-extrabold tracking-tight">
              <span className="text-[#48bf6d]">Learning</span>
              <span className="text-[#2f7bf6]">Mate</span>
            </p>
            <h1 className="mt-8 text-3xl font-bold text-slate-900 dark:text-slate-100">Sign Up</h1>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Create your account with OTP or password</p>
          </div>

          <div className="mb-4 inline-flex rounded-xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-800">
            <button
              type="button"
              onClick={() => dispatch(setSignupMode('otp'))}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${mode === 'otp' ? 'bg-[#2f7bf6] text-white shadow' : 'text-slate-700 dark:text-slate-200'}`}
            >
              OTP Signup
            </button>
            <button
              type="button"
              onClick={() => dispatch(setSignupMode('password'))}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${mode === 'password' ? 'bg-[#2f7bf6] text-white shadow' : 'text-slate-700 dark:text-slate-200'}`}
            >
              Password Signup
            </button>
          </div>

          {mode === 'otp' ? (
            <form
              onSubmit={otpStep === 'phone' ? onRequestOtp : onVerifyOtpSignup}
              className="space-y-4"
              autoComplete="on"
            >
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {otpStep === 'phone' ? 'Phone' : 'OTP'}
              </label>
              <input
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-[#2f7bf6] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                name={otpStep === 'phone' ? 'phone' : 'otp'}
                type={otpStep === 'phone' ? 'tel' : 'text'}
                autoComplete={otpStep === 'phone' ? 'username' : 'one-time-code'}
                value={otpStep === 'phone' ? phone : otp}
                onChange={(e) => (
                  otpStep === 'phone'
                    ? dispatch(setSignupField({ field: 'phone', value: e.target.value }))
                    : dispatch(setSignupField({ field: 'otp', value: e.target.value }))
                )}
                placeholder={otpStep === 'phone' ? 'Enter phone number' : 'Enter OTP'}
              />
              <button
                type="submit"
                disabled={loading}
                className="action-glow-btn w-full rounded-xl bg-[#2f7bf6] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                {otpStep === 'phone' ? 'Request OTP' : 'Verify OTP & Create Account'}
              </button>
              {otpStep === 'otp' ? (
                <button
                  type="button"
                  onClick={() => {
                    dispatch(setSignupOtpStep('phone'));
                  }}
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
                >
                  Change Phone Number
                </button>
              ) : null}
            </form>
          ) : (
            <form onSubmit={onPasswordSignup} className="space-y-4" autoComplete="on">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">Phone</label>
              <input
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-[#2f7bf6] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                name="username"
                type="tel"
                autoComplete="username"
                value={phone}
                onChange={(e) => dispatch(setSignupField({ field: 'phone', value: e.target.value }))}
                placeholder="Enter phone number"
              />
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">Password</label>
              <input
                type="password"
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-[#2f7bf6] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                name="new_password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => dispatch(setSignupField({ field: 'password', value: e.target.value }))}
                placeholder="Enter password"
              />
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">Confirm Password</label>
              <input
                type="password"
                className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none focus:border-[#2f7bf6] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                name="confirm_password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => dispatch(setSignupField({ field: 'confirmPassword', value: e.target.value }))}
                placeholder="Confirm password"
              />
              <button
                type="submit"
                disabled={loading}
                className="action-glow-btn w-full rounded-xl bg-[#2f7bf6] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
              >
                Create Account
              </button>
            </form>
          )}

          <button
            type="button"
            onClick={onGoogleSignup}
            disabled={loading}
            className="action-glow-btn google-anim-btn mt-4 w-full rounded-xl px-4 py-3 text-sm font-semibold text-slate-700 disabled:opacity-60 dark:text-slate-100"
          >
            <span>Sign up with Google</span>
          </button>

          {message ? <p className="mt-4 text-sm text-emerald-600">{message}</p> : null}
          {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}

          <p className="mt-6 text-sm text-slate-600 dark:text-slate-300">
            Already have an account? <Link to="/login" className="font-semibold text-[#2f7bf6]">Login</Link>
          </p>
        </main>
      </div>
      <div className="auth-motion-wrap mt-4 hidden md:block">
        <div className="auth-motion-track">
          {['Campus Energy', 'Study Boost', 'Quiz Ready', 'Fast Recall', 'Deep Focus', 'Topper Mode', 'Buddy Learn', 'Track Progress', 'Campus Energy', 'Study Boost', 'Quiz Ready', 'Fast Recall', 'Deep Focus', 'Topper Mode', 'Buddy Learn', 'Track Progress'].map((label, idx) => (
            <span key={`${label}-${idx}`} className="auth-chip">{label}</span>
          ))}
        </div>
      </div>
      </div>
    </div>
  );
}

export default Signup;
