import hashlib
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models import RuleConfig, StaffUser


logger = logging.getLogger(__name__)


def _hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def run_bootstrap(db: Session) -> dict:
    users_count = db.query(StaffUser).count()
    rules_count = db.query(RuleConfig).count()
    should_bootstrap = users_count == 0 and rules_count == 0

    if not should_bootstrap:
        logger.info('bootstrap_skip users=%s rules=%s', users_count, rules_count)
        return {'ran': False, 'users_count': users_count, 'rules_count': rules_count}

    logger.warning('bootstrap_run_empty_db_detected')

    default_rule = RuleConfig(
        batch_id=None,
        absence_streak_threshold=3,
        notify_parent_on_absence=True,
        notify_parent_on_fee_due=True,
        reminder_grace_period_days=0,
        quiet_hours_start=settings.default_quiet_hours_start,
        quiet_hours_end=settings.default_quiet_hours_end,
    )
    db.add(default_rule)

    admin = StaffUser(
        username='admin',
        role='admin',
        password_hash=_hash_password('admin123'),
        is_active=True,
    )
    teacher = StaffUser(
        username='teacher',
        role='teacher',
        password_hash=_hash_password('teacher123'),
        is_active=True,
    )
    db.add_all([admin, teacher])
    db.commit()

    logger.warning('bootstrap_complete created_default_rule_and_staff_users')
    return {'ran': True, 'created_users': 2, 'created_rules': 1}
