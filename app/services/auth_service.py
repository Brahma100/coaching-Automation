from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.core.phone import normalize_phone as _core_normalize_phone
from app.domain.communication_gateway import send_event as gateway_send_event
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Parent, Role
from app.services.center_scope_service import get_or_create_default_center_id
from app.services.rate_limit_service import check_rate_limit


_REVOKED_TOKENS: set[str] = set()
_TOKENS_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


class AuthAuthorizationError(ValueError):
    """Raised when a phone is not authorized to request/login via OTP."""


def _normalize_phone(phone: str) -> str:
    # DEPRECATED: use app.core.phone.normalize_phone directly.
    return _core_normalize_phone(phone)


def _mask_phone(phone: str) -> str:
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 4:
        return '***'
    return f'***{clean_phone[-4:]}'


def _phone_candidates(phone: str) -> list[str]:
    clean_phone = _normalize_phone(phone)
    if not clean_phone:
        return []
    candidates = [clean_phone]
    if len(clean_phone) > 10:
        last10 = clean_phone[-10:]
        if last10 not in candidates:
            candidates.append(last10)
    return candidates


def _find_auth_user_by_phone(db: Session, phone: str) -> AuthUser | None:
    candidates = _phone_candidates(phone)
    if not candidates:
        return None
    # Prefer exact normalized phone match first.
    exact = db.query(AuthUser).filter(AuthUser.phone == candidates[0]).first()
    if exact:
        return exact
    for candidate in candidates[1:]:
        user = db.query(AuthUser).filter(AuthUser.phone == candidate).first()
        if user:
            return user
    return None


def _hash_otp(phone: str, otp: str) -> str:
    payload = f'{settings.auth_secret}:{_normalize_phone(phone)}:{otp}'.encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _hash_password(password: str) -> str:
    if len(password or '') < 8:
        raise ValueError('Password must be at least 8 characters')
    salt = secrets.token_hex(16)
    iterations = 120000
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${derived.hex()}'


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iter_raw, salt, digest_hex = password_hash.split('$', 3)
        if algo != 'pbkdf2_sha256':
            return False
        iterations = int(iter_raw)
        derived = hashlib.pbkdf2_hmac('sha256', (password or '').encode('utf-8'), salt.encode('utf-8'), iterations).hex()
        return hmac.compare_digest(derived, digest_hex)
    except Exception:
        return False


def _validate_allowlist_for_login(db: Session, clean_phone: str) -> AllowedUser:
    allowed_user = lookup_allowed_user(db, clean_phone)
    if not allowed_user:
        logger.warning('auth_allowlist_denied_request phone=%s', _mask_phone(clean_phone))
        raise AuthAuthorizationError('You are not authorized. Please contact admin.')
    if allowed_user.status == AllowedUserStatus.DISABLED.value:
        logger.warning('auth_allowlist_disabled_request phone=%s', _mask_phone(clean_phone))
        raise AuthAuthorizationError('You are not authorized. Please contact admin.')
    if allowed_user.status not in (AllowedUserStatus.INVITED.value, AllowedUserStatus.ACTIVE.value):
        logger.warning(
            'auth_allowlist_invalid_status_request phone=%s status=%s',
            _mask_phone(clean_phone),
            allowed_user.status,
        )
        raise AuthAuthorizationError('You are not authorized. Please contact admin.')
    return allowed_user


def _find_telegram_chat_id_for_phone(db: Session, phone: str) -> str:
    auth_user = _find_auth_user_by_phone(db, phone)
    if auth_user and auth_user.telegram_chat_id:
        return auth_user.telegram_chat_id
    parent = db.query(Parent).filter(Parent.phone == phone).first()
    if parent and parent.telegram_chat_id:
        return parent.telegram_chat_id
    if auth_user:
        return ''
    return settings.auth_otp_fallback_chat_id


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')


def _b64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode('ascii'))


def _encode_jwt(payload: dict) -> str:
    header = {'alg': 'HS256', 'typ': 'JWT'}
    header_part = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_part = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f'{header_part}.{payload_part}'.encode('ascii')
    signature = hmac.new(settings.auth_secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    signature_part = _b64url_encode(signature)
    return f'{header_part}.{payload_part}.{signature_part}'


def _decode_jwt(token: str) -> dict | None:
    try:
        header_part, payload_part, signature_part = token.split('.')
    except ValueError:
        return None

    signing_input = f'{header_part}.{payload_part}'.encode('ascii')
    expected_signature = hmac.new(settings.auth_secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    provided_signature = _b64url_decode(signature_part)
    if not hmac.compare_digest(provided_signature, expected_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part).decode('utf-8'))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def request_otp(db: Session, phone: str, *, time_provider: TimeProvider = default_time_provider) -> dict:
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Phone must contain at least 10 digits')

    allowed_user = _validate_allowlist_for_login(db, clean_phone)

    user = _find_auth_user_by_phone(db, clean_phone)
    scoped_center_id = int((user.center_id if user else 0) or get_or_create_default_center_id(db) or 1)
    check_rate_limit(
        db,
        center_id=scoped_center_id,
        scope_type='user',
        scope_key=clean_phone,
        action_name='auth_request_otp',
        max_requests=5,
        window_seconds=300,
        time_provider=time_provider,
    )

    if not user:
        user = AuthUser(
            phone=clean_phone,
            role=allowed_user.role,
            center_id=scoped_center_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.role != allowed_user.role:
        user.role = allowed_user.role
        db.commit()

    otp = f'{secrets.randbelow(1000000):06d}'
    user.last_otp = _hash_otp(clean_phone, otp)
    user.otp_created_at = time_provider.now().replace(tzinfo=None)
    db.commit()

    chat_id = _find_telegram_chat_id_for_phone(db, clean_phone)
    if not chat_id:
        raise ValueError('Your number is not linked to Telegram. Please link Telegram first from Settings.')

    message = (
        f'Your coaching login OTP is {otp}. '
        f'It expires in {settings.auth_otp_expiry_minutes} minutes.'
    )
    delivery = gateway_send_event(
        'auth.otp.requested',
        {
            'db': db,
            'tenant_id': settings.communication_tenant_id,
            'user_id': str(user.id),
            'event_payload': {'phone': clean_phone, 'purpose': 'otp_login'},
            'message': message,
            'channels': ['telegram'],
            'critical': True,
            'entity_type': 'auth_user',
            'entity_id': int(user.id),
            'center_id': int(user.center_id or scoped_center_id or 1),
            'notification_type': 'auth_otp',
            'teacher_id': int(user.id),
        },
        [{'chat_id': chat_id, 'user_id': str(user.id)}],
    )
    sent = bool(delivery and delivery[0].get('ok'))
    if not sent:
        raise ValueError('Failed to send OTP via Telegram')

    return {
        'phone': clean_phone,
        'role': allowed_user.role,
        'expires_in_minutes': settings.auth_otp_expiry_minutes,
    }


def _issue_session_token(
    db: Session,
    user: AuthUser,
    allowed_user: AllowedUser,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    now = time_provider.now()
    center_id = int(user.center_id or 0)
    if center_id <= 0:
        center_id = get_or_create_default_center_id(db)
        user.center_id = center_id
        db.commit()
        db.refresh(user)
    if allowed_user.status == AllowedUserStatus.INVITED.value:
        allowed_user.status = AllowedUserStatus.ACTIVE.value
        db.commit()

    token = _encode_jwt(
        {
            'sub': user.id,
            'phone': user.phone,
            'role': allowed_user.role,
            'center_id': center_id,
            'iat': int(now.timestamp()),
        }
    )
    with _TOKENS_LOCK:
        _REVOKED_TOKENS.discard(token)
    return {
        'token': token,
        'user_id': user.id,
        'phone': user.phone,
        'role': allowed_user.role,
        'center_id': center_id,
        'expires_at': None,
    }


def lookup_allowed_user(db: Session, phone: str) -> AllowedUser | None:
    candidates = _phone_candidates(phone)
    if not candidates:
        return None
    exact = db.query(AllowedUser).filter(AllowedUser.phone == candidates[0]).first()
    if exact:
        return exact
    for candidate in candidates[1:]:
        row = db.query(AllowedUser).filter(AllowedUser.phone == candidate).first()
        if row:
            return row
    return None


def add_allowed_user(db: Session, phone: str, role: str) -> AllowedUser:
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Phone must contain at least 10 digits')

    role_value = (role or '').strip().lower()
    allowed_roles = {Role.ADMIN.value, Role.TEACHER.value, Role.STUDENT.value}
    if role_value not in allowed_roles:
        raise ValueError('Role must be one of: admin, teacher, student')

    row = lookup_allowed_user(db, clean_phone)
    if not row:
        row = AllowedUser(
            phone=clean_phone,
            role=role_value,
            status=AllowedUserStatus.INVITED.value,
        )
        db.add(row)
    else:
        row.role = role_value
        if row.status == AllowedUserStatus.DISABLED.value:
            row.status = AllowedUserStatus.INVITED.value
    db.commit()
    db.refresh(row)
    return row


def deactivate_allowed_user(db: Session, phone: str) -> AllowedUser:
    row = lookup_allowed_user(db, phone)
    if not row:
        raise ValueError('Allowed user not found')
    row.status = AllowedUserStatus.DISABLED.value
    db.commit()
    db.refresh(row)
    return row


def list_allowed_users(db: Session) -> list[AllowedUser]:
    return db.query(AllowedUser).order_by(AllowedUser.created_at.desc(), AllowedUser.id.desc()).all()


def verify_otp(
    db: Session,
    phone: str,
    otp: str,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    clean_phone = _normalize_phone(phone)
    user = _find_auth_user_by_phone(db, clean_phone)
    if not user:
        raise ValueError('User not found')
    if not user.otp_created_at or not user.last_otp:
        raise ValueError('OTP not requested')

    try:
        allowed_user = _validate_allowlist_for_login(db, clean_phone)
    except AuthAuthorizationError as exc:
        raise ValueError(str(exc)) from exc

    now = time_provider.now().replace(tzinfo=None)
    if user.otp_created_at + timedelta(minutes=settings.auth_otp_expiry_minutes) < now:
        raise ValueError('OTP expired')

    if _hash_otp(clean_phone, otp) != user.last_otp:
        raise ValueError('Invalid OTP')

    payload = _issue_session_token(db, user, allowed_user, time_provider=time_provider)
    logger.info('auth_login_success phone=%s role=%s', _mask_phone(clean_phone), allowed_user.role)
    return payload


def signup_password(
    db: Session,
    phone: str,
    password: str,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Phone must contain at least 10 digits')
    allowed_user = _validate_allowlist_for_login(db, clean_phone)

    user = _find_auth_user_by_phone(db, clean_phone)
    if not user:
        user = AuthUser(
            phone=clean_phone,
            role=allowed_user.role,
            center_id=get_or_create_default_center_id(db),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.role != allowed_user.role:
        user.role = allowed_user.role
        db.commit()

    user.password_hash = _hash_password(password)
    db.commit()
    db.refresh(user)
    return _issue_session_token(db, user, allowed_user, time_provider=time_provider)


def login_password(
    db: Session,
    phone: str,
    password: str,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    clean_phone = _normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Phone must contain at least 10 digits')
    allowed_user = _validate_allowlist_for_login(db, clean_phone)
    user = _find_auth_user_by_phone(db, clean_phone)
    if not user:
        raise ValueError('User not found')
    if user.role != allowed_user.role:
        user.role = allowed_user.role
        db.commit()
    if not user.password_hash:
        raise ValueError('Password login not setup for this account')
    if not _verify_password(password, user.password_hash):
        raise ValueError('Invalid credentials')
    return _issue_session_token(db, user, allowed_user, time_provider=time_provider)


def google_login(db: Session, id_token: str) -> dict:
    _ = id_token
    if not settings.auth_enable_google_login or not settings.auth_google_client_id:
        raise ValueError('Google login is not configured')
    raise ValueError('Google login token verification is not configured in this environment')


def validate_session_token(token: str | None) -> dict | None:
    if not token:
        return None
    with _TOKENS_LOCK:
        if token in _REVOKED_TOKENS:
            return None

    payload = _decode_jwt(token)
    if not payload:
        return None

    role = payload.get('role')
    phone = payload.get('phone')
    user_id = payload.get('sub')
    center_id = int(payload.get('center_id') or 0)
    if center_id <= 0:
        center_id = 1
    if not role or not phone or user_id is None:
        return None

    return {
        'user_id': user_id,
        'phone': phone,
        'role': role,
        'center_id': center_id,
        'expires_at': None,
    }


def clear_session_token(token: str | None) -> None:
    if not token:
        return
    with _TOKENS_LOCK:
        _REVOKED_TOKENS.add(token)
