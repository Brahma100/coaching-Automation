# Coaching Management App

FastAPI-based coaching automation platform with attendance workflows, fee automation, homework, referrals, Telegram notifications, parent rules, and teacher action queue.

## Student Risk Engine (Read-Only Intelligence Layer)
The Student Risk Engine is additive and advisory:
1. Reads attendance, homework, fee, and optional test trends.
2. Writes only to `student_risk_profiles` and `student_risk_events`.
3. Creates `PendingAction(type='student_risk')` only when a student transitions into `HIGH` risk.
4. Runs daily via scheduler (`student_risk_recompute` job).

Risk factors and weights:
1. Attendance: 40%
2. Homework submissions: 30%
3. Fee dues/overdue: 20%
4. Tests (if available): 10%

Risk level thresholds:
1. `LOW`: score >= 75
2. `MEDIUM`: 50-74
3. `HIGH`: < 50

Teacher workflow:
1. Dashboard shows a **High Risk Students** section.
2. Teacher Action Inbox shows `student_risk` actions.
3. Teachers can mark reviewed, notify parent, or ignore with note.

APIs:
1. `GET /api/risk/students` (via Vite `/api` rewrite to `/risk/students`) with optional `batch_id`.
2. `GET /api/risk/student/{student_id}` for detailed breakdown and reasons.

Risk is advisory, not disciplinary.

## Quick Start
1. `python -m venv .venv`
2. `.venv\\Scripts\\activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`
5. `python scripts/init_db.py` (for local seed only)
6. `alembic upgrade head`
7. `uvicorn app.main:app --reload`

Docs: `/docs`, `/redoc`; UI: `/ui/dashboard`

## Login Flow (OTP)
1. Open `/ui/login`.
2. Enter phone and click **Request OTP**.
3. OTP is sent via Telegram.
4. Enter OTP and click **Verify OTP**.
5. Server validates allowlist authorization for the phone.
5. App stores an HTTP-only cookie (`auth_session`) and redirects to dashboard.

Notes:
1. OTP expiry default is 10 minutes (`AUTH_OTP_EXPIRY_MINUTES`).
2. Session expiry default is 12 hours (`AUTH_SESSION_EXPIRY_HOURS`).
3. If no parent Telegram mapping exists for the phone, set `AUTH_OTP_FALLBACK_CHAT_ID`.
4. OTP verifies identity; allowlist verifies permission.
5. Role in session is sourced from `allowed_users.role` (not from OTP request payload).
6. There is no public signup.

React auth pages:
1. `/login`: OTP login + Password login + Google button.
2. `/signup`: OTP signup + Password signup + Google button.
3. Desktop view shows the left-side student illustration panel; mobile hides it.

Password auth APIs:
1. `POST /auth/signup-password` body: `{ "phone": "...", "password": "..." }`
2. `POST /auth/login-password` body: `{ "phone": "...", "password": "..." }`
3. Allowlist authorization is still enforced before account creation/login.

Google auth API:
1. `POST /auth/google-login`
2. Returns `501` when Google auth is not configured (`AUTH_ENABLE_GOOGLE_LOGIN`, `AUTH_GOOGLE_CLIENT_ID`).

## Student Web UI (Read-Only)
Purpose:
1. Give students a web dashboard to view learning/payment status.
2. Keep Telegram as the primary interaction channel for notifications and actions.
3. Enforce strict read-only access in the student portal.

Routes:
1. `/ui/student/dashboard`
2. `/ui/student/attendance`
3. `/ui/student/homework`
4. `/ui/student/fees`
5. `/ui/student/tests`
6. `/ui/student/announcements`

Student APIs (read-only):
1. `GET /api/student/me`
2. `GET /api/student/dashboard`
3. `GET /api/student/attendance`
4. `GET /api/student/homework`
5. `GET /api/student/fees`

Safety guarantees:
1. Student identity is derived from session phone only (no `student_id` query/body parameter).
2. Student routes require role = `student`.
3. Student web UI is view-only.
4. No create/update/delete actions are exposed in student routes.

## Allowlist Authorization (Required)
`allowed_users` table controls who can actually log in:
1. `phone` (unique)
2. `role` (`admin`, `teacher`, `student`)
3. `status` (`invited`, `active`, `disabled`)

Verification behavior:
1. `POST /auth/request-otp` validates allowlist permission first.
2. Unauthorized/disabled phones are denied at OTP request time with `403`.
3. `POST /auth/verify-otp` requires valid OTP and allowlist permission.
4. If phone is missing in allowlist or user is disabled, login is denied with: `You are not authorized. Please contact admin.`

Admin allowlist management:
1. `admin`: full access to admin APIs/UI and system operations.
2. `teacher`: teaching workflows and dashboard access.
3. `student`: reserved for student-facing access (if enabled in future flows).

Admin allowlist API (`admin` role required; auth via `auth_session` cookie or `Authorization: Bearer <token>`):
1. `GET /api/admin/allowed-users` list allowlisted users.
2. `POST /api/admin/allowed-users/invite` body: `{ "phone": "9999999999", "role": "TEACHER" }`.
3. `POST /api/admin/allowed-users/activate` body: `{ "phone": "9999999999" }`.
4. `POST /api/admin/allowed-users/deactivate` body: `{ "phone": "9999999999" }`.
5. All endpoints enforce admin session + active `allowed_users` admin record.

Admin UI:
1. Open `/ui/admin/allowed-users` to list allowlisted users and activate/deactivate.
2. Open `/ui/admin/allowed-users/invite` to invite new users (`TEACHER` or `STUDENT`).
3. `Manage Users` link appears in top navigation only for admin sessions.

## Teacher/Auth User Setup
1. Preferred: self-onboard from `/ui/login` by requesting OTP with your phone.
2. Ensure Telegram delivery path is configured:
3. Either keep a `Parent` record with the same phone and `telegram_chat_id`.
4. Or set fallback `AUTH_OTP_FALLBACK_CHAT_ID` in `.env`.

## Batch vs Schedule vs Session (Multi-Batch)
Concepts:
1. `Batch`: subject/group metadata (`name`, `subject`, `academic_level`, `active`).
2. `BatchSchedule`: weekday slot for a batch (`weekday`, `start_time`, `duration_minutes`).
3. `ClassSession`: per-date session record generated dynamically from batch schedule.
4. `StudentBatchMap`: many-to-many student membership across batches (`active` soft unlink).

Real coaching example:
1. `Math_X` batch schedules:
2. Monday `08:00` for `60` minutes
3. Wednesday `17:00` for `90` minutes
4. On each matching weekday, class sessions are created for that date when attendance/post-class flow runs.

Safety behavior:
1. Batch delete is soft (`active=false`) only.
2. Historical class sessions, attendance, fees, homework are not deleted.
3. Duplicate active student-batch links are prevented.

Teacher/Admin APIs:
1. `GET /api/batches`
2. `POST /api/batches`
3. `PUT /api/batches/{batch_id}`
4. `DELETE /api/batches/{batch_id}` (soft delete)
5. `POST /api/batches/{batch_id}/schedule`
6. `PUT /api/batch-schedules/{schedule_id}`
7. `DELETE /api/batch-schedules/{schedule_id}`
8. `POST /api/batches/{batch_id}/students`
9. `DELETE /api/batches/{batch_id}/students/{student_id}`
10. `GET /api/students/{student_id}/batches`

Batch UI:
1. `/ui/batches` list batches with schedule summary and student count.
2. `/ui/batches/add` create batch.
3. `/ui/batches/{batch_id}` edit batch, manage schedules, link/unlink students.

## Dashboard Action-First Section
Top section in `/ui/dashboard` now includes:
1. Today session card with attendance link.
2. Pending teacher action count.
3. Fee alerts (overdue and due-soon).
4. Quick links (Add Student, Create Batch, Homework, Referrals).

## Screenshots
1. Login page: `docs/screenshots/login.png` (placeholder)
2. Add student page: `docs/screenshots/add-student.png` (placeholder)
3. Batch management page: `docs/screenshots/batches.png` (placeholder)
4. Dashboard action-first section: `docs/screenshots/dashboard-action-first.png` (placeholder)

## Architecture
```text
                    +----------------------+
                    |  Scheduler (cron)    |
                    | fee/preclass/brief   |
                    +----------+-----------+
                               |
+-----------+      +-----------v------------+      +-------------------+
| UI (Jinja)| ---> | FastAPI Routers        | ---> | Services Layer    |
| /ui/*     |      | attendance/fees/...    |      | pipeline/rules    |
+-----------+      +-----------+------------+      +---------+---------+
                               |                             |
                               v                             v
                     +--------------------+        +---------------------+
                     | SQLAlchemy Models  |        | Telegram Integrations|
                     | SQLite + Alembic   |        | inline actions/tokens|
                     +---------+----------+        +---------------------+
                               |
                               v
                      +-------------------+
                      | Backup to Sheets  |
                      +-------------------+
```

## Database Migrations (Alembic)
Initial setup:
1. `alembic upgrade head`

Useful commands:
1. `alembic history`
2. `alembic current`
3. `alembic downgrade -1`

Migration scripts included:
1. `alembic/versions/20260209_0001_initial_core.py`
2. `alembic/versions/20260209_0002_automation_entities.py`
3. `alembic/versions/20260209_0003_rule_config_pending_actions.py`
4. `alembic/versions/20260209_0004_bootstrap_quiet_backup.py`
5. `alembic/versions/20260209_0005_auth_user.py`
6. `alembic/versions/20260209_0006_student_risk_engine.py`
7. `alembic/versions/20260209_0007_allowed_users_allowlist.py`
8. `alembic/versions/20260209_0008_batch_schedule_multi_batch.py`
9. `alembic/versions/20260209_0009_attendance_session_lifecycle.py`

## Automation-Hardening Features
1. `RuleConfig` supports global + batch-level rule override.
2. Post-class pipeline writes `PendingAction` queue for teacher inbox.
3. Notification idempotency suppresses duplicate sends in a short window.
4. Telegram inline action helper creates signed, short-lived action links.
5. Action token endpoints support one-click secure flows.

## Daily Teacher Brief
Daily Teacher Brief sends each active teacher a morning Telegram summary with:
1. Today's class schedule
2. Absent students summary
3. Pending actions summary
4. Fee dues for current month
5. Homework due soon
6. HIGH risk students summary

Scheduling:
1. Job id: `daily_teacher_brief`
2. Default time: `07:30` server timezone
3. Config: `DAILY_TEACHER_BRIEF_TIME=HH:MM`

Teacher brief API (optional UI use):
1. `GET /api/teacher/brief/today`
2. Requires teacher/admin session.

## Unified Session Attendance (Telegram + Web)
Attendance entry is session-scoped and converges to one pipeline:
1. Telegram trigger creates/uses a `ClassSession` and sends a tokenized attendance link.
2. Web fallback uses `/ui/attendance/manage` to pick batch/date/slot and open the same session sheet.
3. Both paths submit through the same attendance service and run the same post-class pipeline.
4. Session is locked after submit (`submitted`) and non-admin re-submission is blocked.
5. Token links are one-time and consumed on successful submit.

Routes:
1. `GET /ui/attendance/manage`
2. `POST /ui/attendance/manage`
3. `GET /ui/attendance/session/{session_id}` (teacher/admin session or Telegram token)
4. `POST /ui/attendance/session/{session_id}` (same submit endpoint for both entry paths)

Flow diagram:
```text
Telegram -> resolve/create ClassSession -> session attendance sheet -> submit attendance -> post_class_pipeline
Web      -> resolve/create ClassSession -> session attendance sheet -> submit attendance -> post_class_pipeline
```

## Attendance Session Lifecycle (Auto-Close)
Lifecycle:
1. `scheduled`: session exists before class starts.
2. `open`: attendance window is active.
3. `submitted`: attendance submitted and pipeline already processed.
4. `closed`: session finalized after class end + grace.
5. `missed`: no attendance was submitted before auto-close.

Auto-close scheduler:
1. Job id: `auto_close_attendance_sessions`
2. Frequency: every 5 minutes
3. Config: `ATTENDANCE_AUTO_CLOSE_GRACE_MINUTES` (default `10`)

Enforcement:
1. `closed`/`missed` sessions reject attendance submission with:
2. `Attendance window closed for this class.`
3. Missed sessions create a teacher pending action entry.
4. Backend helper `reopen_session(session_id, admin_only=True)` is available for future admin override APIs.

Lifecycle diagram:
```text
scheduled -> open -> submitted -> closed
               \
                -> missed
```

## Teacher Action Inbox
1. Open `/ui/teacher-actions`
2. Review open items from `PendingAction`
3. Resolve with one-click buttons

## Upgrade Instructions
1. Pull latest code.
2. Install/upgrade dependencies: `pip install -r requirements.txt`
3. Apply DB migrations: `alembic upgrade head`
4. Ensure `.env` has `APP_BASE_URL` for Telegram action links.
5. Restart API process.

## Bootstrap Safety
Bootstrap runs automatically on app startup and can be triggered manually:
1. Auto-run at startup: `app/main.py` lifecycle calls bootstrap after schema creation.
2. Manual run: `python bootstrap.py`

Behavior on empty DB:
1. Creates default global `RuleConfig`.
2. Creates default staff users:
3. `admin` (role `admin`, default password seed `admin123`)
4. `teacher` (role `teacher`, default password seed `teacher123`)
5. Logs clearly whether bootstrap executed or skipped.
6. If `allowed_users` is empty, seeds one default admin allowlist record with status `active`.
7. Seed source precedence: `AUTH_ADMIN_PHONE`, then `AUTH_OTP_FALLBACK_CHAT_ID` (digits only).
8. `AUTH_ADMIN_PHONE` is recommended for first setup; there is no public signup.
9. `AUTH_OTP_FALLBACK_CHAT_ID` is normally a Telegram chat id, so use it for seeding only if it is intentionally set to a phone number.
10. Warning emitted: `Default admin allowlisted — remove after setup`.

## Healthcheck
Run:
1. `python healthcheck.py`

Expected output:
1. `✓ PASS ...` for each check when healthy.
2. `✗ FAIL ...` with reason for failing checks.

Exit codes:
1. `0` = healthy
2. `1` = unhealthy

Checks included:
1. Database connectivity and write access
2. Alembic migration status (DB at head)
3. Required environment variables present
4. Telegram API reachability
5. Scheduler jobs registered
6. RuleConfig loading
7. PendingAction table accessibility
8. ActionToken generation + expiry validation

Common failure causes:
1. `No migration version in DB`: run `alembic upgrade head`.
2. Missing env vars (especially `TELEGRAM_BOT_TOKEN`, `APP_BASE_URL`): update `.env`.
3. Telegram reachability failure: invalid bot token, blocked network, or wrong `TELEGRAM_API_BASE`.
4. Missing scheduler jobs: scheduler import/startup error in `app/scheduler.py`.
5. Table access failures for `pending_actions` / `action_tokens`: migrations not applied.

## Backup & Restore (UI)
System page:
1. Open `/ui/system`
2. Click `Backup Now` to trigger immediate Google Sheets backup.
3. Use `Download SQLite DB` to download the current SQLite file.
4. Page displays last backup timestamp and status from `BackupLog`.

Restore approach:
1. Stop the app.
2. Replace current SQLite file with downloaded backup file.
3. Start app and run `alembic upgrade head` to ensure schema is up to date.
