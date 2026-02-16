from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ClassSession, Role, Student
from app.services.auth_service import validate_session_token
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.rate_limit_service import SafeRateLimitError, check_rate_limit
from app.domain.commands import ensure_session_actions, generate_dashboard_tokens, prepare_notification_side_effects

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/commands', tags=['Commands'])


class GenerateTokenPayload(BaseModel):
    token_type: str = Field(alias='action_type')
    payload: dict
    ttl_minutes: int = 60


class NotificationSideEffectPayload(BaseModel):
    mode: str
    payload: dict


class EnsureSessionActionsPayload(BaseModel):
    teacher_id: int
    session_id: int


def _require_teacher_or_admin(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    if not token:
        authorization = request.headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            token = authorization[7:].strip()
    session = validate_session_token(token)
    role = (session or {}).get('role')
    if not session or role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.post('/generate-token')
def generate_token(
    body: GenerateTokenPayload,
    actor: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (actor.get('role') or '').lower()
    actor_user_id = int(actor.get('user_id') or 0)
    actor_center_id = int(actor.get('center_id') or 0)
    try:
        check_rate_limit(
            db,
            center_id=actor_center_id or 1,
            scope_type='user',
            scope_key=str(actor_user_id or 0),
            action_name='commands_generate_token',
            max_requests=20,
            window_seconds=60,
        )
    except SafeRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    session_id = int((body.payload or {}).get('session_id') or 0)
    if session_id > 0:
        session_row = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session_row:
            raise HTTPException(status_code=404, detail='Class session not found')
        if actor_center_id > 0 and int(session_row.center_id or 0) != actor_center_id:
            raise HTTPException(status_code=403, detail='Unauthorized center scope')
        if role == Role.TEACHER.value:
            teacher_batch_ids = get_teacher_batch_ids(db, actor_user_id, center_id=actor_center_id)
            teacher_payload_id = int((body.payload or {}).get('teacher_id') or actor_user_id)
            if teacher_payload_id != actor_user_id:
                raise HTTPException(status_code=403, detail='Unauthorized teacher scope')
            if int(session_row.teacher_id or 0) != actor_user_id and int(session_row.batch_id or 0) not in teacher_batch_ids:
                raise HTTPException(status_code=403, detail='Unauthorized session scope')
    return generate_dashboard_tokens(
        db,
        action_type=body.token_type,
        payload=body.payload,
        ttl_minutes=int(body.ttl_minutes or 60),
    )


@router.post('/prepare-notification-side-effects')
def prepare_side_effects(
    body: NotificationSideEffectPayload,
    actor: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (actor.get('role') or '').lower()
    actor_user_id = int(actor.get('user_id') or 0)
    actor_center_id = int(actor.get('center_id') or 0)
    if body.mode == 'session_student_actions':
        student_id = int((body.payload or {}).get('student_id') or 0)
        if student_id <= 0:
            raise HTTPException(status_code=400, detail='student_id required')
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail='Student not found')
        if actor_center_id > 0 and int(student.center_id or 0) != actor_center_id:
            raise HTTPException(status_code=403, detail='Unauthorized center scope')
        if role == Role.TEACHER.value:
            teacher_batch_ids = get_teacher_batch_ids(db, actor_user_id, center_id=actor_center_id)
            if int(student.batch_id or 0) not in teacher_batch_ids:
                raise HTTPException(status_code=403, detail='Unauthorized student scope')
    logger.warning('legacy_prepare_notification_side_effects_endpoint_used mode=%s', body.mode)
    try:
        return prepare_notification_side_effects(db, mode=body.mode, payload=body.payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/ensure-session-actions')
def ensure_actions(
    body: EnsureSessionActionsPayload,
    actor: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (actor.get('role') or '').lower()
    actor_user_id = int(actor.get('user_id') or 0)
    actor_center_id = int(actor.get('center_id') or 0)
    session_row = db.query(ClassSession).filter(ClassSession.id == int(body.session_id)).first()
    if not session_row:
        raise HTTPException(status_code=404, detail='Class session not found')
    if actor_center_id > 0 and int(session_row.center_id or 0) != actor_center_id:
        raise HTTPException(status_code=403, detail='Unauthorized center scope')
    if role == Role.TEACHER.value and int(body.teacher_id) != actor_user_id:
        raise HTTPException(status_code=403, detail='Unauthorized teacher scope')
    if role == Role.TEACHER.value:
        teacher_batch_ids = get_teacher_batch_ids(db, actor_user_id, center_id=actor_center_id)
        if int(session_row.teacher_id or 0) != actor_user_id and int(session_row.batch_id or 0) not in teacher_batch_ids:
            raise HTTPException(status_code=403, detail='Unauthorized session scope')
    ensure_session_actions(db, teacher_id=int(body.teacher_id), session_id=int(body.session_id))
    return {'ok': True, 'teacher_id': int(body.teacher_id), 'session_id': int(body.session_id)}
