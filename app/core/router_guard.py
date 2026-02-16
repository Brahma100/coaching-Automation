from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import TeacherBatchMap
from app.services.auth_service import validate_session_token


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token
    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def require_auth_user(request: Request) -> dict:
    token = _resolve_token(request)
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=401, detail='Unauthorized')
    user_id = int(session.get('user_id') or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return {
        'user_id': user_id,
        'role': str(session.get('role') or '').strip().lower(),
        'center_id': int(session.get('center_id') or 0),
        'phone': str(session.get('phone') or ''),
    }


def require_role(user: dict, allowed_roles: set[str] | Iterable[str]) -> None:
    normalized = {str(role).strip().lower() for role in allowed_roles}
    if str(user.get('role') or '').strip().lower() not in normalized:
        raise HTTPException(status_code=403, detail='Forbidden')


def assert_center_match(user: dict, entity_center_id: int | None) -> None:
    user_center_id = int(user.get('center_id') or 0)
    target_center_id = int(entity_center_id or 0)
    if user_center_id <= 0 or target_center_id <= 0 or user_center_id != target_center_id:
        raise HTTPException(status_code=403, detail='Forbidden')


def assert_teacher_batch_scope(db: Session, user: dict, batch_id: int) -> None:
    if str(user.get('role') or '').lower() != 'teacher':
        return
    teacher_id = int(user.get('user_id') or 0)
    center_id = int(user.get('center_id') or 0)
    mapped = (
        db.query(TeacherBatchMap)
        .filter(
            TeacherBatchMap.teacher_id == teacher_id,
            TeacherBatchMap.batch_id == int(batch_id),
            TeacherBatchMap.center_id == center_id,
        )
        .first()
    )
    if not mapped:
        raise HTTPException(status_code=403, detail='Forbidden')


def assert_teacher_session_scope(db: Session, user: dict, session) -> None:
    assert_center_match(user, int(getattr(session, 'center_id', 0) or 0))
    if str(user.get('role') or '').lower() != 'teacher':
        return
    assert_teacher_batch_scope(db, user, int(getattr(session, 'batch_id', 0) or 0))
    teacher_id = int(user.get('user_id') or 0)
    session_teacher_id = int(getattr(session, 'teacher_id', 0) or 0)
    if session_teacher_id > 0 and session_teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail='Forbidden')
