# Coaching Management App

FastAPI-based coaching automation platform with attendance workflows, fee automation, homework, referrals, Telegram notifications, parent rules, and teacher action queue.

## Quick Start
1. `python -m venv .venv`
2. `.venv\\Scripts\\activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`
5. `python scripts/init_db.py` (for local seed only)
6. `uvicorn app.main:app --reload`

Docs: `/docs`, `/redoc`; UI: `/ui/dashboard`

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

## Automation-Hardening Features
1. `RuleConfig` supports global + batch-level rule override.
2. Post-class pipeline writes `PendingAction` queue for teacher inbox.
3. Notification idempotency suppresses duplicate sends in a short window.
4. Telegram inline action helper creates signed, short-lived action links.
5. Action token endpoints support one-click secure flows.

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
