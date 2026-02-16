from __future__ import annotations

import csv
import io
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.cache import cache, cache_key
from app.config import settings
from app.core.phone import normalize_phone as _core_normalize_phone
from app.models import (
    AllowedUser,
    AuthUser,
    Batch,
    Center,
    OnboardingState,
    RuleConfig,
    Subject,
    Tag,
    TeacherAutomationRule,
    TeacherCommunicationSettings,
)
from app.services.auth_service import _hash_password, _issue_session_token, add_allowed_user

ONBOARDING_STEPS = [
    'welcome',
    'center_setup',
    'subdomain_selection',
    'admin_creation',
    'academic_setup',
    'teacher_invite',
    'student_import',
    'finish',
]


def normalize_slug(value: str) -> str:
    raw = (value or '').strip().lower()
    chars: list[str] = []
    prev_dash = False
    for char in raw:
        if char.isalnum():
            chars.append(char)
            prev_dash = False
            continue
        if char in {'-', '_', ' '} and not prev_dash:
            chars.append('-')
            prev_dash = True
    return ''.join(chars).strip('-')


def _normalize_phone(value: str) -> str:
    # DEPRECATED: use app.core.phone.normalize_phone directly.
    return _core_normalize_phone(value)


def _now_utc() -> datetime:
    return datetime.utcnow().replace(tzinfo=None)


def _slug_suggestions(name: str, city: str = '') -> list[str]:
    base_parts = [normalize_slug(name), normalize_slug(city)]
    base = '-'.join(part for part in base_parts if part).strip('-')
    if len(base) < 3:
        base = f'center-{secrets.randbelow(9000) + 1000}'
    suggestions = [base]
    for idx in range(2, 6):
        suggestions.append(f'{base}-{idx}')
    deduped: list[str] = []
    for item in suggestions:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _load_payload(row: OnboardingState) -> dict:
    try:
        payload = json.loads(row.payload_json or '{}')
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault('steps', {})
    return payload


def _save_payload(row: OnboardingState, payload: dict, *, current_step: str | None = None) -> None:
    row.payload_json = json.dumps(payload, separators=(',', ':'))
    if current_step:
        row.current_step = current_step
    row.updated_at = _now_utc()


def _step_progress(row: OnboardingState) -> int:
    if row.is_completed:
        return 100
    step = row.current_step or ONBOARDING_STEPS[0]
    try:
        idx = ONBOARDING_STEPS.index(step)
    except ValueError:
        idx = 0
    return int(((idx + 1) / len(ONBOARDING_STEPS)) * 100)


def serialize_state(row: OnboardingState) -> dict:
    payload = _load_payload(row)
    return {
        'onboarding_id': int(row.id),
        'setup_token': row.setup_token,
        'center_id': int(row.center_id),
        'temp_slug': row.temp_slug,
        'reserved_slug': row.reserved_slug,
        'status': row.status,
        'current_step': row.current_step,
        'is_completed': bool(row.is_completed),
        'progress_percent': _step_progress(row),
        'payload': payload,
    }


def get_onboarding_state(db: Session, setup_token: str, *, actor_center_id: int = 0) -> OnboardingState:
    token = (setup_token or '').strip()
    if not token:
        raise ValueError('setup_token is required')
    row = db.query(OnboardingState).filter(OnboardingState.setup_token == token).first()
    if not row:
        raise ValueError('Onboarding state not found')
    if int(actor_center_id or 0) > 0 and int(row.center_id or 0) != int(actor_center_id):
        raise ValueError('Cross-center onboarding access denied')
    return row


def check_slug_availability(db: Session, slug: str, *, skip_setup_token: str = '') -> tuple[bool, str]:
    clean_slug = normalize_slug(slug)
    if len(clean_slug) < 3:
        return False, 'Slug must be at least 3 characters'

    key = cache_key('onboard_slug_availability', clean_slug)
    cached = cache.get_cached(key)
    if isinstance(cached, dict) and not skip_setup_token:
        return bool(cached.get('available')), str(cached.get('reason') or '')

    if db.query(Center.id).filter(func.lower(Center.slug) == clean_slug).first():
        result = (False, 'Slug is already in use')
        cache.set_cached(key, {'available': False, 'reason': result[1]}, ttl=30)
        return result

    now = _now_utc()
    lock_q = db.query(OnboardingState).filter(
        func.lower(OnboardingState.temp_slug) == clean_slug,
        OnboardingState.is_completed.is_(False),
    )
    if skip_setup_token:
        lock_q = lock_q.filter(OnboardingState.setup_token != skip_setup_token)
    lock = lock_q.first()
    if lock and (lock.lock_expires_at is None or lock.lock_expires_at > now):
        result = (False, 'Slug is temporarily reserved')
        if not skip_setup_token:
            cache.set_cached(key, {'available': False, 'reason': result[1]}, ttl=30)
        return result

    result = (True, '')
    if not skip_setup_token:
        cache.set_cached(key, {'available': True, 'reason': ''}, ttl=30)
    return result


def create_center_setup(
    db: Session,
    *,
    name: str,
    city: str,
    timezone: str,
    academic_type: str,
) -> tuple[OnboardingState, list[str]]:
    clean_name = (name or '').strip()
    clean_city = (city or '').strip()
    clean_timezone = (timezone or '').strip() or settings.app_timezone
    clean_academic_type = (academic_type or '').strip()
    if not clean_name:
        raise ValueError('Center name is required')

    suggestions = _slug_suggestions(clean_name, clean_city)
    chosen_slug = ''
    for suggestion in suggestions:
        available, _ = check_slug_availability(db, suggestion)
        if available:
            chosen_slug = suggestion
            break
    if not chosen_slug:
        chosen_slug = f"{suggestions[0]}-{secrets.randbelow(9000) + 1000}"

    center = Center(name=clean_name, slug=chosen_slug, timezone=clean_timezone)
    db.add(center)
    db.flush()

    state = OnboardingState(
        center_id=int(center.id),
        temp_slug=chosen_slug,
        reserved_slug=chosen_slug,
        setup_token=secrets.token_urlsafe(24),
        status='in_progress',
        current_step='center_setup',
        is_completed=False,
        lock_expires_at=_now_utc() + timedelta(hours=24),
    )
    payload = {
        'center': {
            'name': clean_name,
            'city': clean_city,
            'timezone': clean_timezone,
            'academic_type': clean_academic_type,
        },
        'steps': {
            'center_setup': {
                'completed_at': _now_utc().isoformat(),
            }
        },
    }
    state.payload_json = json.dumps(payload, separators=(',', ':'))
    db.add(state)
    db.commit()
    db.refresh(state)
    cache.invalidate(cache_key('onboard_slug_availability', chosen_slug))
    return state, suggestions


def reserve_slug(
    db: Session,
    *,
    setup_token: str,
    slug: str,
    actor_center_id: int = 0,
) -> OnboardingState:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    clean_slug = normalize_slug(slug)
    available, reason = check_slug_availability(db, clean_slug, skip_setup_token=row.setup_token)
    if not available:
        raise ValueError(reason or 'Slug unavailable')

    center = db.query(Center).filter(Center.id == row.center_id).first()
    if not center:
        raise ValueError('Center not found')

    center.slug = clean_slug
    row.temp_slug = clean_slug
    row.reserved_slug = clean_slug
    row.lock_expires_at = _now_utc() + timedelta(hours=24)
    payload = _load_payload(row)
    payload['steps']['subdomain_selection'] = {
        'slug': clean_slug,
        'reserved_at': _now_utc().isoformat(),
    }
    _save_payload(row, payload, current_step='subdomain_selection')
    db.commit()
    db.refresh(row)
    cache.invalidate(cache_key('onboard_slug_availability', clean_slug))
    return row


def create_admin_user(
    db: Session,
    *,
    setup_token: str,
    name: str,
    phone: str,
    password: str,
    actor_center_id: int = 0,
) -> tuple[OnboardingState, str]:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Admin phone must contain at least 10 digits')
    password_raw = (password or '').strip()
    if len(password_raw) < 8:
        raise ValueError('Admin password must be at least 8 characters')

    add_allowed_user(db, clean_phone, 'admin')
    user = db.query(AuthUser).filter(AuthUser.phone == clean_phone).first()
    if not user:
        user = AuthUser(phone=clean_phone, role='admin', center_id=row.center_id)
        db.add(user)
        db.flush()
    user.role = 'admin'
    user.center_id = row.center_id
    user.password_hash = _hash_password(password_raw)

    center = db.query(Center).filter(Center.id == row.center_id).first()
    if center:
        center.owner_user_id = int(user.id)

    # Auto-create teacher profile preferences for admin to keep existing flows stable.
    comms = db.query(TeacherCommunicationSettings).filter(TeacherCommunicationSettings.teacher_id == int(user.id)).first()
    if not comms:
        db.add(TeacherCommunicationSettings(teacher_id=int(user.id)))
    automation = db.query(TeacherAutomationRule).filter(TeacherAutomationRule.teacher_id == int(user.id)).first()
    if not automation:
        db.add(TeacherAutomationRule(teacher_id=int(user.id)))

    allowed_user = db.query(AllowedUser).filter(AllowedUser.phone == clean_phone).first()
    if not allowed_user:
        raise ValueError('Failed to create allowed admin user')
    session_data = _issue_session_token(db, user, allowed_user)

    payload = _load_payload(row)
    payload['admin'] = {'name': (name or '').strip(), 'phone': clean_phone, 'user_id': int(user.id)}
    payload['steps']['admin_creation'] = {'completed_at': _now_utc().isoformat()}
    _save_payload(row, payload, current_step='admin_creation')
    db.commit()
    db.refresh(row)
    return row, str(session_data.get('token') or '')


def setup_academic_defaults(
    db: Session,
    *,
    setup_token: str,
    classes: list[str],
    subjects: list[str],
    actor_center_id: int = 0,
) -> tuple[OnboardingState, dict]:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    class_values = [str(item or '').strip() for item in (classes or []) if str(item or '').strip()]
    subject_values = [str(item or '').strip() for item in (subjects or []) if str(item or '').strip()]
    if not class_values:
        class_values = ['Class 9', 'Class 10', 'Class 11', 'Class 12']
    if not subject_values:
        subject_values = ['Mathematics', 'Science', 'English']

    created_subjects = 0
    created_tags = 0
    for name in subject_values:
        exists = db.query(Subject.id).filter(func.lower(Subject.name) == name.lower()).first()
        if exists:
            continue
        db.add(Subject(name=name, code=''))
        created_subjects += 1

    default_tags = ['Homework', 'Revision', 'Exam', 'Announcements']
    for tag_name in default_tags:
        exists = db.query(Tag.id).filter(func.lower(Tag.name) == tag_name.lower()).first()
        if exists:
            continue
        db.add(Tag(name=tag_name))
        created_tags += 1

    payload = _load_payload(row)
    payload['academic_defaults'] = {
        'classes': class_values,
        'subjects': subject_values,
        'note_folders': ['Class Notes', 'Homework Sheets', 'Exam Papers'],
    }
    payload['steps']['academic_setup'] = {'completed_at': _now_utc().isoformat()}
    _save_payload(row, payload, current_step='academic_setup')
    db.commit()
    db.refresh(row)
    return row, {
        'created_subjects': created_subjects,
        'created_tags': created_tags,
        'classes': class_values,
    }


def invite_teachers(
    db: Session,
    *,
    setup_token: str,
    teachers: list[dict],
    actor_center_id: int = 0,
) -> tuple[OnboardingState, dict]:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    prepared: list[dict] = []
    for teacher in (teachers or []):
        phone = _normalize_phone(str((teacher or {}).get('phone', '')))
        if len(phone) < 10:
            continue
        prepared.append(
            {
                'name': str((teacher or {}).get('name', '')).strip(),
                'phone': phone,
                'subject': str((teacher or {}).get('subject', '')).strip(),
            }
        )

    phones = [item['phone'] for item in prepared]
    existing_allowed = {
        row.phone: row
        for row in db.query(AllowedUser).filter(AllowedUser.phone.in_(phones)).all()
    } if phones else {}

    invited = 0
    updated = 0
    to_insert: list[AllowedUser] = []
    for item in prepared:
        if item['phone'] in existing_allowed:
            existing_allowed[item['phone']].role = 'teacher'
            updated += 1
            continue
        to_insert.append(AllowedUser(phone=item['phone'], role='teacher', status='invited'))
        invited += 1

    if to_insert:
        db.add_all(to_insert)

    payload = _load_payload(row)
    payload['teacher_invites'] = {'count': len(prepared), 'rows': prepared}
    payload['steps']['teacher_invite'] = {'completed_at': _now_utc().isoformat()}
    _save_payload(row, payload, current_step='teacher_invite')
    db.commit()
    db.refresh(row)
    return row, {'invited': invited, 'updated': updated}


def parse_students_csv(file_bytes: bytes) -> dict:
    text = file_bytes.decode('utf-8-sig', errors='ignore')
    reader = csv.DictReader(io.StringIO(text))
    required_headers = ['name', 'guardian_phone', 'batch']
    raw_headers = [str(item or '').strip() for item in (reader.fieldnames or [])]
    normalized_headers = [header.lower() for header in raw_headers]
    missing_headers = [header for header in required_headers if header not in normalized_headers]
    extra_headers = [header for header in raw_headers if header.lower() not in required_headers]

    rows: list[dict] = []
    row_errors: list[dict] = []
    header_key_map = {header.lower(): header for header in raw_headers}
    for index, raw in enumerate(reader, start=2):
        if not raw:
            continue
        source_name = str(raw.get(header_key_map.get('name', ''), '') or '').strip()
        source_guardian = str(raw.get(header_key_map.get('guardian_phone', ''), '') or '').strip()
        source_batch = str(raw.get(header_key_map.get('batch', ''), '') or '').strip()

        error_items: list[str] = []
        if not source_name:
            error_items.append('name is required')
        guardian_phone = _normalize_phone(source_guardian)
        if source_guardian and len(guardian_phone) < 10:
            error_items.append('guardian_phone must contain at least 10 digits')

        if error_items:
            row_errors.append(
                {
                    'row': index,
                    'errors': error_items,
                    'raw': {
                        'name': source_name,
                        'guardian_phone': source_guardian,
                        'batch': source_batch,
                    },
                }
            )
            continue

        rows.append(
            {
                'name': source_name,
                'guardian_phone': guardian_phone,
                'batch': source_batch,
            }
        )

    return {
        'required_headers': required_headers,
        'headers': raw_headers,
        'missing_headers': missing_headers,
        'extra_headers': extra_headers,
        'rows': rows,
        'row_errors': row_errors,
        'total_rows': len(rows) + len(row_errors),
    }


def store_imported_students(
    db: Session,
    *,
    setup_token: str,
    parsed_rows: list[dict],
    validation_report: dict | None = None,
    actor_center_id: int = 0,
) -> tuple[OnboardingState, dict]:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    report = validation_report or {}
    row_errors = report.get('row_errors') if isinstance(report, dict) else []
    missing_headers = report.get('missing_headers') if isinstance(report, dict) else []
    payload = _load_payload(row)
    payload['student_import'] = {
        'requested': len(parsed_rows),
        'parsed_rows': parsed_rows,
        'validation_report': report,
        'has_errors': bool(row_errors) or bool(missing_headers),
        'stored_only': True,
    }
    payload['steps']['student_import'] = {'completed_at': _now_utc().isoformat()}
    _save_payload(row, payload, current_step='student_import')
    db.commit()
    db.refresh(row)
    return row, {
        'parsed_rows': len(parsed_rows),
        'invalid_rows': len(row_errors) if isinstance(row_errors, list) else 0,
        'missing_headers': missing_headers if isinstance(missing_headers, list) else [],
    }


def finish_onboarding(db: Session, *, setup_token: str, actor_center_id: int = 0) -> OnboardingState:
    row = get_onboarding_state(db, setup_token, actor_center_id=actor_center_id)
    payload = _load_payload(row)

    # Default automation/rules templates (additive and idempotent).
    rule = db.query(RuleConfig).filter(RuleConfig.batch_id.is_(None)).first()
    if not rule:
        db.add(RuleConfig(batch_id=None))

    admin_users = db.query(AuthUser).filter(AuthUser.center_id == row.center_id, AuthUser.role == 'admin').all()
    for user in admin_users:
        comms = db.query(TeacherCommunicationSettings).filter(TeacherCommunicationSettings.teacher_id == int(user.id)).first()
        if not comms:
            db.add(TeacherCommunicationSettings(teacher_id=int(user.id)))
        automation = db.query(TeacherAutomationRule).filter(TeacherAutomationRule.teacher_id == int(user.id)).first()
        if not automation:
            db.add(TeacherAutomationRule(teacher_id=int(user.id)))

    payload['steps']['finish'] = {'completed_at': _now_utc().isoformat()}
    row.status = 'completed'
    row.is_completed = True
    row.completed_at = _now_utc()
    row.lock_expires_at = None
    _save_payload(row, payload, current_step='finish')
    db.commit()
    db.refresh(row)
    cache.invalidate(cache_key('onboard_slug_availability', row.temp_slug))
    return row


def is_center_onboarding_incomplete(db: Session, center_id: int) -> bool:
    cid = int(center_id or 0)
    if cid <= 0:
        return False
    row = db.query(OnboardingState.id).filter(
        OnboardingState.center_id == cid,
        OnboardingState.is_completed.is_(False),
    ).first()
    return bool(row)


# Backward-compatible wrappers used by previous onboarding router.
def import_students(db: Session, *, setup_token: str, students: list[dict], actor_center_id: int = 0):
    parsed_rows = []
    for item in students or []:
        name = str((item or {}).get('name', '')).strip()
        if not name:
            continue
        parsed_rows.append(
            {
                'name': name,
                'guardian_phone': _normalize_phone(str((item or {}).get('guardian_phone', ''))),
                'batch': str((item or {}).get('batch', '')),
            }
        )
    return store_imported_students(db, setup_token=setup_token, parsed_rows=parsed_rows, actor_center_id=actor_center_id)


def mark_subdomain_selection(db: Session, *, setup_token: str, slug: str, actor_center_id: int = 0) -> OnboardingState:
    return reserve_slug(db, setup_token=setup_token, slug=slug, actor_center_id=actor_center_id)
