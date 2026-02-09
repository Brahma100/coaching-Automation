import secrets
import sys
from datetime import datetime, timedelta

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine
from app.models import ActionToken, PendingAction
from app.scheduler import scheduler, start_scheduler, stop_scheduler
from app.services.action_token_service import _hash_token, create_action_token, verify_and_consume_token
from app.services.rule_config_service import get_effective_rule_config


EXPECTED_SCHEDULER_JOBS = {
    'pre_class_notifications',
    'fee_reminders',
    'daily_briefs',
    'google_backup',
}

GREEN = '\033[32m'
RED = '\033[31m'
RESET = '\033[0m'


def run_check(name, fn):
    try:
        message = fn() or ''
        suffix = f' - {message}' if message else ''
        print(f'{GREEN}PASS{RESET} {name}{suffix}')
        return True
    except Exception as exc:
        print(f'{RED}FAIL{RESET} {name} - {exc}')
        return False


def check_db_connectivity_and_write():
    with engine.begin() as conn:
        conn.execute(text('SELECT 1'))
        conn.execute(text('CREATE TABLE IF NOT EXISTS _healthcheck_probe (id INTEGER PRIMARY KEY, note TEXT)'))
        conn.execute(text("INSERT INTO _healthcheck_probe (note) VALUES ('probe')"))
        conn.execute(text("DELETE FROM _healthcheck_probe WHERE note='probe'"))
        conn.execute(text('DROP TABLE IF EXISTS _healthcheck_probe'))
    return 'connect + write ok'


def check_alembic_head():
    cfg = Config('alembic.ini')
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    if not heads:
        raise RuntimeError('No alembic heads found in repository')

    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()

    if current is None:
        raise RuntimeError('No migration version in DB (run alembic upgrade head)')
    if current not in heads:
        raise RuntimeError(f'DB revision {current} is not at head {sorted(heads)}')
    return f'current={current}'


def check_required_env():
    required = {
        'DATABASE_URL': settings.database_url,
        'TELEGRAM_API_BASE': settings.telegram_api_base,
        'APP_BASE_URL': settings.app_base_url,
        'DEFAULT_UPI_ID': settings.default_upi_id,
        'TELEGRAM_BOT_TOKEN': settings.telegram_bot_token,
    }
    missing = [key for key, value in required.items() if not str(value).strip()]
    if missing:
        raise RuntimeError(f'Missing env vars: {", ".join(missing)}')
    return 'all required vars present'


def check_telegram_api():
    if not settings.telegram_bot_token:
        raise RuntimeError('TELEGRAM_BOT_TOKEN is empty')

    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/getMe"
    res = httpx.get(url, timeout=8)
    if res.status_code != 200:
        raise RuntimeError(f'HTTP {res.status_code} from Telegram')

    payload = res.json()
    if not payload.get('ok'):
        raise RuntimeError(f"Telegram responded not ok: {payload}")
    return 'Telegram getMe ok'


def check_scheduler_jobs_registered():
    start_scheduler()
    try:
        registered = {job.id for job in scheduler.get_jobs()}
        missing = sorted(EXPECTED_SCHEDULER_JOBS - registered)
        if missing:
            raise RuntimeError(f'Missing jobs: {missing}')
        return f'jobs={sorted(registered)}'
    finally:
        stop_scheduler()


def check_rule_config_loaded():
    db = SessionLocal()
    try:
        cfg = get_effective_rule_config(db)
        required_keys = {
            'absence_streak_threshold',
            'notify_parent_on_absence',
            'notify_parent_on_fee_due',
            'reminder_grace_period_days',
            'scope',
        }
        missing = required_keys - set(cfg.keys())
        if missing:
            raise RuntimeError(f'RuleConfig missing keys: {sorted(missing)}')
        return f"scope={cfg.get('scope')}"
    finally:
        db.close()


def check_pending_action_table_accessible():
    db = SessionLocal()
    try:
        _ = db.query(PendingAction).limit(1).all()
        return 'query ok'
    finally:
        db.close()


def check_action_token_generation_and_expiry():
    db = SessionLocal()
    created_ids = []
    try:
        token_obj = create_action_token(
            db,
            action_type='healthcheck-valid',
            payload={'k': 'v'},
            ttl_minutes=2,
        )
        valid_payload = verify_and_consume_token(db, token_obj['token'], expected_action_type='healthcheck-valid')
        if valid_payload.get('k') != 'v':
            raise RuntimeError('Token payload mismatch during consume check')

        consumed = db.query(ActionToken).filter(ActionToken.action_type == 'healthcheck-valid').order_by(ActionToken.id.desc()).first()
        if consumed:
            created_ids.append(consumed.id)

        expired_raw = secrets.token_urlsafe(24)
        expired = ActionToken(
            token_hash=_hash_token(expired_raw),
            action_type='healthcheck-expired',
            payload_json='{}',
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            consumed=False,
            created_at=datetime.utcnow(),
        )
        db.add(expired)
        db.commit()
        db.refresh(expired)
        created_ids.append(expired.id)

        try:
            verify_and_consume_token(db, expired_raw, expected_action_type='healthcheck-expired')
            raise RuntimeError('Expired token unexpectedly validated')
        except ValueError as exc:
            if 'expired' not in str(exc).lower():
                raise RuntimeError(f'Unexpected expiry validation error: {exc}') from exc

        return 'create/consume/expiry checks ok'
    finally:
        if created_ids:
            db.query(ActionToken).filter(ActionToken.id.in_(created_ids)).delete(synchronize_session=False)
            db.commit()
        db.close()


def main():
    checks = [
        ('Database connectivity and write access', check_db_connectivity_and_write),
        ('Alembic migration status at head', check_alembic_head),
        ('Required environment variables present', check_required_env),
        ('Telegram API reachable', check_telegram_api),
        ('Scheduler jobs registered', check_scheduler_jobs_registered),
        ('RuleConfig loaded successfully', check_rule_config_loaded),
        ('PendingAction table accessible', check_pending_action_table_accessible),
        ('ActionToken generation and expiry working', check_action_token_generation_and_expiry),
    ]

    all_ok = True
    for name, fn in checks:
        all_ok = run_check(name, fn) and all_ok

    if not all_ok:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
