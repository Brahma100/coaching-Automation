from __future__ import annotations

from app.models import AllowedUser, AllowedUserStatus, Role
from app.services.auth_service import validate_session_token


def normalize_phone(value: str) -> str:
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _normalize_role_input(role: str) -> str:
    role_value = (role or '').strip().lower()
    if role_value not in (Role.TEACHER.value, Role.STUDENT.value):
        raise ValueError('Role must be TEACHER or STUDENT')
    return role_value


def require_admin_session(db, token: str | None) -> dict:
    session = validate_session_token(token)
    if not session:
        raise PermissionError('Unauthorized')

    role = (session.get('role') or '').lower()
    phone = normalize_phone(session.get('phone') or '')
    if role != Role.ADMIN.value or not phone:
        raise PermissionError('Admin access required')

    row = db.query(AllowedUser).filter(AllowedUser.phone == phone).first()
    if not row or row.role != Role.ADMIN.value or row.status != AllowedUserStatus.ACTIVE.value:
        raise PermissionError('Admin access required')

    return session


def list_allowed_users_admin(db) -> list[AllowedUser]:
    return db.query(AllowedUser).order_by(AllowedUser.created_at.desc(), AllowedUser.id.desc()).all()


def invite_allowed_user(db, phone: str, role: str) -> AllowedUser:
    clean_phone = normalize_phone(phone)
    if len(clean_phone) < 10:
        raise ValueError('Phone must contain at least 10 digits')

    role_value = _normalize_role_input(role)
    existing = db.query(AllowedUser).filter(AllowedUser.phone == clean_phone).first()
    if existing:
        raise ValueError('Allowed user already exists for this phone')

    row = AllowedUser(
        phone=clean_phone,
        role=role_value,
        status=AllowedUserStatus.INVITED.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def activate_allowed_user_admin(db, phone: str) -> AllowedUser:
    clean_phone = normalize_phone(phone)
    row = db.query(AllowedUser).filter(AllowedUser.phone == clean_phone).first()
    if not row:
        raise ValueError('Allowed user not found')
    row.status = AllowedUserStatus.ACTIVE.value
    db.commit()
    db.refresh(row)
    return row


def deactivate_allowed_user_admin(db, phone: str) -> AllowedUser:
    clean_phone = normalize_phone(phone)
    row = db.query(AllowedUser).filter(AllowedUser.phone == clean_phone).first()
    if not row:
        raise ValueError('Allowed user not found')
    row.status = AllowedUserStatus.DISABLED.value
    db.commit()
    db.refresh(row)
    return row
