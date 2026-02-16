import React from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';

import {
  onboardAcademicSetup,
  onboardCheckSlug,
  onboardCreateAdmin,
  onboardCreateCenter,
  onboardFetchState,
  onboardFinish,
  onboardImportStudents,
  onboardInviteTeachers,
  onboardReserveSlug,
} from '../services/api.js';

const STORAGE_KEY = 'coaching:onboard:draft:v2';
const STEP_KEYS = [
  'welcome',
  'center_setup',
  'subdomain_selection',
  'admin_creation',
  'academic_setup',
  'teacher_invite',
  'student_import',
  'finish',
];
const STEP_LABELS = [
  'Welcome',
  'Center Details',
  'Choose Subdomain',
  'Admin Setup',
  'Academic Setup',
  'Teachers (Optional)',
  'Students Import (Optional)',
  'Success',
];

function parseTeachers(input) {
  return String(input || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = '', phone = '', subject = ''] = line.split(',').map((part) => part.trim());
      return { name, phone, subject };
    });
}

function stepIndexFromKey(stepKey) {
  const idx = STEP_KEYS.indexOf(stepKey);
  return idx >= 0 ? idx : 0;
}

function Onboard() {
  const [loading, setLoading] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');
  const [currentStep, setCurrentStep] = React.useState(0);
  const [setupToken, setSetupToken] = React.useState('');
  const [slugAvailability, setSlugAvailability] = React.useState(null);
  const [suggestions, setSuggestions] = React.useState([]);
  const [csvFile, setCsvFile] = React.useState(null);
  const [csvValidation, setCsvValidation] = React.useState(null);
  const [stateMeta, setStateMeta] = React.useState(null);

  const [form, setForm] = React.useState({
    centerName: '',
    city: '',
    timezone: 'Asia/Kolkata',
    academicType: 'school',
    slug: '',
    adminName: '',
    adminPhone: '',
    adminPassword: '',
    classesCsv: 'Class 9, Class 10, Class 11, Class 12',
    subjectsCsv: 'Mathematics, Science, English',
    teacherRows: '',
  });

  React.useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return;
      setForm((prev) => ({ ...prev, ...(parsed.form || {}) }));
      setSetupToken(String(parsed.setupToken || ''));
      setCurrentStep(Number(parsed.currentStep) || 0);
    } catch {
      // no-op
    }
  }, []);

  React.useEffect(() => {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          form,
          setupToken,
          currentStep,
          ts: Date.now(),
        })
      );
    } catch {
      // no-op
    }
  }, [form, setupToken, currentStep]);

  React.useEffect(() => {
    if (!setupToken) return;
    let active = true;
    onboardFetchState(setupToken)
      .then((resp) => {
        if (!active) return;
        const state = resp?.state || null;
        setStateMeta(state);
        if (state?.current_step) {
          setCurrentStep((prev) => Math.max(prev, stepIndexFromKey(state.current_step)));
        }
        if (state?.temp_slug && !form.slug) {
          setForm((prev) => ({ ...prev, slug: state.temp_slug }));
        }
      })
      .catch(() => {
        // ignore resume failures
      });
    return () => {
      active = false;
    };
  }, [setupToken]);

  const onField = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event?.target?.value ?? '' }));

  const withAction = async (fn) => {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      await fn();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const progressPercent = Math.max(8, Math.min(100, ((currentStep + 1) / STEP_LABELS.length) * 100));

  const checkSlug = async () => {
    const resp = await onboardCheckSlug(form.slug);
    setSlugAvailability(Boolean(resp?.available));
    setSuggestions(Array.isArray(resp?.suggestions) ? resp.suggestions : []);
    if (!resp?.available) throw new Error(resp?.reason || 'Slug unavailable');
  };

  const onStart = () => setCurrentStep(1);

  const submitCenter = () =>
    withAction(async () => {
      if (!form.centerName.trim()) throw new Error('Center name is required');
      const resp = await onboardCreateCenter({
        name: form.centerName,
        city: form.city,
        timezone: form.timezone,
        academic_type: form.academicType,
      });
      const token = String(resp?.state?.setup_token || '');
      if (!token) throw new Error('Missing onboarding token');
      setSetupToken(token);
      setStateMeta(resp?.state || null);
      if (resp?.slug_suggestion) {
        setForm((prev) => ({ ...prev, slug: resp.slug_suggestion }));
      }
      setSuggestions(Array.isArray(resp?.suggestions) ? resp.suggestions : []);
      setCurrentStep(2);
      setMessage('Center created. Choose your subdomain.');
    });

  const submitSubdomain = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      await checkSlug();
      const resp = await onboardReserveSlug({ setup_token: setupToken, slug: form.slug });
      setStateMeta(resp?.state || null);
      setCurrentStep(3);
      setMessage('Subdomain reserved successfully.');
    });

  const submitAdmin = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      if (!form.adminPhone.trim()) throw new Error('Admin phone is required');
      if ((form.adminPassword || '').length < 8) throw new Error('Password must be at least 8 characters');
      const resp = await onboardCreateAdmin({
        setup_token: setupToken,
        name: form.adminName,
        phone: form.adminPhone,
        password: form.adminPassword,
      });
      setStateMeta(resp?.state || null);
      setCurrentStep(4);
      setMessage('Admin created. Login remains unchanged until finish.');
    });

  const submitAcademic = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      const classes = form.classesCsv.split(',').map((x) => x.trim()).filter(Boolean);
      const subjects = form.subjectsCsv.split(',').map((x) => x.trim()).filter(Boolean);
      const resp = await onboardAcademicSetup({ setup_token: setupToken, classes, subjects });
      setStateMeta(resp?.state || null);
      setCurrentStep(5);
      setMessage('Academic defaults saved.');
    });

  const submitTeachers = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      const teachers = parseTeachers(form.teacherRows);
      const resp = await onboardInviteTeachers({ setup_token: setupToken, teachers });
      setStateMeta(resp?.state || null);
      setCurrentStep(6);
      setMessage('Teacher invite list saved.');
    });

  const submitStudents = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      const resp = await onboardImportStudents({ setup_token: setupToken, file: csvFile });
      setStateMeta(resp?.state || null);
      setCsvValidation(resp?.validation || null);
      setCurrentStep(7);
      const parsedCount = Number(resp?.summary?.parsed_rows || 0);
      const invalidCount = Number(resp?.summary?.invalid_rows || 0);
      const missingHeaders = Array.isArray(resp?.summary?.missing_headers) ? resp.summary.missing_headers : [];
      if (missingHeaders.length) {
        setMessage(`CSV missing required headers: ${missingHeaders.join(', ')}`);
        return;
      }
      setMessage(`Parsed and stored ${parsedCount} row(s). Invalid row(s): ${invalidCount}.`);
    });

  const submitFinish = () =>
    withAction(async () => {
      if (!setupToken) throw new Error('Onboarding session missing');
      const resp = await onboardFinish({ setup_token: setupToken });
      setStateMeta(resp?.state || null);
      setMessage('Onboarding completed. You can login now.');
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // no-op
      }
    });

  const renderStep = () => {
    if (currentStep === 0) {
      return (
        <div className="space-y-3">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Setup your coaching institute in guided steps with resume support.
          </p>
          <button onClick={onStart} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white">
            Start Onboarding
          </button>
        </div>
      );
    }
    if (currentStep === 1) {
      return (
        <div className="space-y-3">
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Center Name" value={form.centerName} onChange={onField('centerName')} />
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="City" value={form.city} onChange={onField('city')} />
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Timezone" value={form.timezone} onChange={onField('timezone')} />
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Academic Type (school/jee/neet)" value={form.academicType} onChange={onField('academicType')} />
          <button disabled={loading} onClick={submitCenter} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Create Center</button>
        </div>
      );
    }
    if (currentStep === 2) {
      return (
        <div className="space-y-3">
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Subdomain slug" value={form.slug} onChange={onField('slug')} />
          {slugAvailability === false ? <p className="text-xs font-semibold text-rose-600">Slug unavailable. Pick another or suggestion below.</p> : null}
          {suggestions.length ? (
            <div className="flex flex-wrap gap-2">
              {suggestions.map((item) => (
                <button key={item} type="button" onClick={() => setForm((prev) => ({ ...prev, slug: item }))} className="rounded-full border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-600 dark:border-slate-700 dark:text-slate-300">{item}</button>
              ))}
            </div>
          ) : null}
          <button disabled={loading} onClick={submitSubdomain} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Reserve Subdomain</button>
        </div>
      );
    }
    if (currentStep === 3) {
      return (
        <div className="space-y-3">
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Admin Name" value={form.adminName} onChange={onField('adminName')} />
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Admin Phone" value={form.adminPhone} onChange={onField('adminPhone')} />
          <input type="password" className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Admin Password" value={form.adminPassword} onChange={onField('adminPassword')} />
          <button disabled={loading} onClick={submitAdmin} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Create Admin</button>
        </div>
      );
    }
    if (currentStep === 4) {
      return (
        <div className="space-y-3">
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Classes (comma separated)" value={form.classesCsv} onChange={onField('classesCsv')} />
          <input className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Subjects (comma separated)" value={form.subjectsCsv} onChange={onField('subjectsCsv')} />
          <button disabled={loading} onClick={submitAcademic} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Save Academic Defaults</button>
        </div>
      );
    }
    if (currentStep === 5) {
      return (
        <div className="space-y-3">
          <textarea className="min-h-[120px] w-full rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700 dark:bg-slate-800" placeholder="Optional teachers, one per line: name,phone,subject" value={form.teacherRows} onChange={onField('teacherRows')} />
          <button disabled={loading} onClick={submitTeachers} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Save Teachers</button>
        </div>
      );
    }
    if (currentStep === 6) {
      return (
        <div className="space-y-3">
          <input type="file" accept=".csv,text/csv" onChange={(event) => setCsvFile(event?.target?.files?.[0] || null)} className="block w-full rounded-xl border border-slate-300 px-4 py-3 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold dark:border-slate-700 dark:bg-slate-800" />
          <p className="text-xs text-slate-500 dark:text-slate-400">CSV columns: name, guardian_phone, batch</p>
          <button disabled={loading || !csvFile} onClick={submitStudents} className="rounded-xl bg-[#2f7bf6] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Parse and Store CSV</button>
          {Array.isArray(csvValidation?.missing_headers) && csvValidation.missing_headers.length ? (
            <p className="text-xs font-semibold text-rose-600">Missing headers: {csvValidation.missing_headers.join(', ')}</p>
          ) : null}
          {Array.isArray(csvValidation?.row_errors) && csvValidation.row_errors.length ? (
            <div className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-800 dark:bg-rose-950/20 dark:text-rose-300">
              {csvValidation.row_errors.slice(0, 5).map((item, idx) => (
                <p key={`${item?.row || idx}-${idx}`}>Row {item?.row}: {Array.isArray(item?.errors) ? item.errors.join(', ') : 'Invalid row'}</p>
              ))}
              {csvValidation.row_errors.length > 5 ? <p>+ {csvValidation.row_errors.length - 5} more row error(s)</p> : null}
            </div>
          ) : null}
          <button disabled={loading} onClick={() => setCurrentStep(7)} className="rounded-xl border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200">Skip</button>
        </div>
      );
    }
    return (
      <div className="space-y-3">
        <p className="text-sm text-slate-600 dark:text-slate-300">Finalize onboarding and continue to login.</p>
        <button disabled={loading} onClick={submitFinish} className="rounded-xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">Finish Onboarding</button>
        <Link className="inline-block rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200" to="/login">Go to Login</Link>
      </div>
    );
  };

  return (
    <div className="onboard-shell min-h-screen p-4 sm:p-8">
      <div className="mx-auto max-w-4xl rounded-3xl border border-slate-200 bg-white/95 p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900/95 sm:p-8">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Institute Onboarding</h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Guided setup with autosave and resume support.</p>
          </div>
          <Link className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200" to="/login">Back to login</Link>
        </div>

        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <span>{STEP_LABELS[currentStep]}</span>
            <span>{Math.round(progressPercent)}%</span>
          </div>
          <div className="onboard-progress-track"><div className="onboard-progress-fill" style={{ width: `${progressPercent}%` }} /></div>
        </div>

        <div className="mb-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {STEP_LABELS.map((label, idx) => (
            <div key={label} className={`rounded-lg border px-3 py-2 text-xs font-semibold ${idx <= currentStep ? 'border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300' : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400'}`}>
              {idx + 1}. {label}
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.24 }}
          >
            {renderStep()}
          </motion.div>
        </AnimatePresence>

        {message ? <p className="mt-4 text-sm font-semibold text-emerald-600">{message}</p> : null}
        {error ? <p className="mt-4 text-sm font-semibold text-rose-600">{error}</p> : null}
        {stateMeta?.temp_slug ? <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">Reserved slug: <span className="font-semibold">{stateMeta.temp_slug}</span></p> : null}
      </div>
    </div>
  );
}

export default Onboard;
