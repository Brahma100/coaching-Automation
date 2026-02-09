import hashlib
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AllowedUser, AllowedUserStatus, Role, RuleConfig, StaffUser


logger = logging.getLogger(__name__)


def _hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _normalize_phone(value: str) -> str:
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _seed_default_allowed_admin_if_needed(db: Session) -> dict:
    count = db.query(AllowedUser).count()
    if count > 0:
        return {'seeded': False, 'reason': 'allowlist_not_empty'}

    candidate_phone = _normalize_phone(settings.auth_admin_phone)
    source = 'AUTH_ADMIN_PHONE'
    if not candidate_phone:
        candidate_phone = _normalize_phone(settings.auth_otp_fallback_chat_id)
        source = 'AUTH_OTP_FALLBACK_CHAT_ID'

    if not candidate_phone:
        logger.warning('allowlist_seed_skipped missing_admin_phone_source')
        return {'seeded': False, 'reason': 'no_phone_source'}
    if len(candidate_phone) < 10:
        logger.warning('allowlist_seed_skipped invalid_phone_source source=%s', source)
        return {'seeded': False, 'reason': 'invalid_phone_source', 'source': source}

    row = AllowedUser(
        phone=candidate_phone,
        role=Role.ADMIN.value,
        status=AllowedUserStatus.ACTIVE.value,
    )
    db.add(row)
    db.commit()
    logger.warning('Default admin allowlisted - remove after setup (source=%s)', source)
    return {'seeded': True, 'phone': candidate_phone, 'source': source}


def _ensure_auth_admin_phone_allowlisted(db: Session) -> dict:
    candidate_phone = _normalize_phone(settings.auth_admin_phone)
    if not candidate_phone:
        return {'ensured': False, 'reason': 'no_auth_admin_phone'}
    if len(candidate_phone) < 10:
        logger.warning('auth_admin_phone_allowlist_skipped invalid_phone')
        return {'ensured': False, 'reason': 'invalid_auth_admin_phone'}

    row = db.query(AllowedUser).filter(AllowedUser.phone == candidate_phone).first()
    if not row:
        row = AllowedUser(
            phone=candidate_phone,
            role=Role.ADMIN.value,
            status=AllowedUserStatus.ACTIVE.value,
        )
        db.add(row)
        db.commit()
        logger.warning('AUTH_ADMIN_PHONE inserted into allowlist as active admin')
        return {'ensured': True, 'inserted': True, 'phone': candidate_phone}

    changed = False
    if row.role != Role.ADMIN.value:
        row.role = Role.ADMIN.value
        changed = True
    if row.status != AllowedUserStatus.ACTIVE.value:
        row.status = AllowedUserStatus.ACTIVE.value
        changed = True
    if changed:
        db.commit()
        logger.warning('AUTH_ADMIN_PHONE allowlist entry updated to active admin')
    return {'ensured': True, 'inserted': False, 'updated': changed, 'phone': candidate_phone}


def run_bootstrap(db: Session) -> dict:
    users_count = db.query(StaffUser).count()
    rules_count = db.query(RuleConfig).count()
    should_bootstrap = users_count == 0 and rules_count == 0

    if not should_bootstrap:
        allowlist_result = _seed_default_allowed_admin_if_needed(db)
        admin_phone_result = _ensure_auth_admin_phone_allowlisted(db)
        logger.info('bootstrap_skip users=%s rules=%s', users_count, rules_count)
        return {
            'ran': False,
            'users_count': users_count,
            'rules_count': rules_count,
            'allowlist': allowlist_result,
            'auth_admin_phone': admin_phone_result,
        }

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

    allowlist_result = _seed_default_allowed_admin_if_needed(db)
    admin_phone_result = _ensure_auth_admin_phone_allowlisted(db)

    logger.warning('bootstrap_complete created_default_rule_and_staff_users')
    return {
        'ran': True,
        'created_users': 2,
        'created_rules': 1,
        'allowlist': allowlist_result,
        'auth_admin_phone': admin_phone_result,
    }
