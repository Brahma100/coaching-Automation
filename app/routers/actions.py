import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.cache import cache
from app.db import get_db
from app.models import Batch, ClassSession, Parent, ParentStudentMap, PendingAction, Student
from app.schemas import ActionTokenCreateRequest, ActionTokenExecuteRequest
from app.services.action_token_service import consume_token, create_action_token, verify_token
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.auth_service import validate_session_token
from app.services.comms_service import queue_telegram_by_chat_id, send_fee_reminder
from app.services.fee_service import build_upi_link
from app.services.integration_service import require_integration
from app.services.operational_brain_service import clear_operational_brain_cache
from app.services.pending_action_service import create_pending_action, list_open_actions, resolve_action


router = APIRouter(prefix='/actions', tags=['Actions'])
logger = logging.getLogger(__name__)


class ActionResolvePayload(BaseModel):
    action_id: int


class RiskIgnorePayload(BaseModel):
    note: str = ''


def _require_teacher(request: Request):
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session or session['role'] not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return session


def _resolve_session_optional(request: Request) -> dict | None:
    token = request.cookies.get('auth_session')
    if not token:
        authz = request.headers.get('authorization', '')
        if authz.lower().startswith('bearer '):
            token = authz[7:].strip()
    if not token:
        return None
    return validate_session_token(token)


def _require_teacher_or_admin_session(request: Request) -> dict:
    session = _resolve_session_optional(request)
    role = ((session or {}).get('role') or '').strip().lower()
    if not session:
        raise HTTPException(status_code=401, detail='Unauthorized')
    if role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail='Forbidden')
    return session


def _require_int(value, name: str) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Invalid {name}') from exc
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f'Invalid {name}')
    return parsed


def _validate_token_create_scope(db: Session, *, actor: dict, payload: dict) -> tuple[int, str]:
    role = str(actor.get('role') or '').strip().lower()
    actor_user_id = _require_int(actor.get('user_id'), 'actor user')
    actor_center_id = _require_int(actor.get('center_id'), 'actor center')

    token_center_id_raw = payload.get('center_id')
    token_center_id = _require_int(token_center_id_raw, 'payload.center_id')
    if token_center_id != actor_center_id:
        raise HTTPException(status_code=403, detail='Unauthorized center scope')

    expected_role = str(payload.get('expected_role') or payload.get('role') or '').strip().lower()
    if expected_role not in ('teacher', 'admin', 'student'):
        raise HTTPException(status_code=400, detail='payload.expected_role is required')

    teacher_batch_ids: set[int] = set()
    if role == 'teacher':
        teacher_batch_ids = get_teacher_batch_ids(db, actor_user_id, center_id=actor_center_id)

    session_id_raw = payload.get('session_id')
    if session_id_raw is not None:
        session_id = _require_int(session_id_raw, 'payload.session_id')
        session_row = db.query(ClassSession).filter(ClassSession.id == session_id).first()
        if not session_row:
            raise HTTPException(status_code=404, detail='Class session not found')
        if int(session_row.center_id or 0) != actor_center_id:
            raise HTTPException(status_code=403, detail='Unauthorized center scope')
        if role == 'teacher':
            if int(session_row.teacher_id or 0) != actor_user_id and int(session_row.batch_id or 0) not in teacher_batch_ids:
                raise HTTPException(status_code=403, detail='Unauthorized session scope')

    batch_id_raw = payload.get('batch_id')
    if batch_id_raw is not None:
        batch_id = _require_int(batch_id_raw, 'payload.batch_id')
        batch_row = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch_row:
            raise HTTPException(status_code=404, detail='Batch not found')
        if int(batch_row.center_id or 0) != actor_center_id:
            raise HTTPException(status_code=403, detail='Unauthorized center scope')
        if role == 'teacher' and int(batch_row.id) not in teacher_batch_ids:
            raise HTTPException(status_code=403, detail='Unauthorized batch scope')

    student_id_raw = payload.get('student_id')
    if student_id_raw is not None:
        student_id = _require_int(student_id_raw, 'payload.student_id')
        student_row = db.query(Student).filter(Student.id == student_id).first()
        if not student_row:
            raise HTTPException(status_code=404, detail='Student not found')
        if int(student_row.center_id or 0) != actor_center_id:
            raise HTTPException(status_code=403, detail='Unauthorized center scope')
        if role == 'teacher' and int(student_row.batch_id or 0) not in teacher_batch_ids:
            raise HTTPException(status_code=403, detail='Unauthorized student scope')

    if role == 'teacher':
        payload_teacher_id = payload.get('teacher_id')
        if payload_teacher_id is not None and _require_int(payload_teacher_id, 'payload.teacher_id') != actor_user_id:
            raise HTTPException(status_code=403, detail='Unauthorized teacher scope')

    return actor_center_id, expected_role


@router.get('/list-open')
def list_open(request: Request, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    rows = list_open_actions(db)
    return [
        {
            'id': row.id,
            'type': row.type,
            'student_id': row.student_id,
            'related_session_id': row.related_session_id,
            'status': row.status,
            'note': row.note,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get('/open')
def open_alias(request: Request, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    return list_open(request=request, _=_, db=db)


@router.post('/resolve')
def resolve_action_by_id(
    payload: ActionResolvePayload,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = resolve_action(db, payload.action_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _invalidate_action_caches(request, teacher_id=row.teacher_id)
    return {'ok': True, 'action_id': row.id, 'status': row.status}


@router.post('/risk/{action_id}/review')
def review_risk_action(
    action_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Pending action not found')
    if row.type != 'student_risk':
        raise HTTPException(status_code=400, detail='Action is not a student_risk item')
    resolved = resolve_action(db, action_id)
    _invalidate_action_caches(request, teacher_id=row.teacher_id)
    return {'ok': True, 'action_id': resolved.id, 'status': resolved.status}


@router.post('/risk/{action_id}/ignore')
def ignore_risk_action(
    action_id: int,
    payload: RiskIgnorePayload,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Pending action not found')
    if row.type != 'student_risk':
        raise HTTPException(status_code=400, detail='Action is not a student_risk item')
    note_suffix = (payload.note or '').strip()
    if note_suffix:
        row.note = f'{row.note}\nIgnored note: {note_suffix}'.strip()
    row.status = 'resolved'
    db.commit()
    db.refresh(row)
    _invalidate_action_caches(request, teacher_id=row.teacher_id)
    return {'ok': True, 'action_id': row.id, 'status': row.status}


@router.post('/risk/{action_id}/notify-parent')
def notify_parent_for_risk_action(
    action_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Pending action not found')
    if row.type != 'student_risk':
        raise HTTPException(status_code=400, detail='Action is not a student_risk item')
    if not row.student_id:
        raise HTTPException(status_code=400, detail='Risk action is missing student_id')

    student = db.query(Student).filter(Student.id == row.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')

    parent_link = db.query(ParentStudentMap).filter(ParentStudentMap.student_id == student.id).first()
    if not parent_link:
        raise HTTPException(status_code=404, detail='No linked parent found for this student')

    parent = db.query(Parent).filter(Parent.id == parent_link.parent_id).first()
    if not parent or not parent.telegram_chat_id:
        raise HTTPException(status_code=404, detail='Parent not found or missing telegram chat id')

    integration_gate = require_integration(db, 'telegram', center_id=student.center_id)
    if integration_gate.get('integration_required'):
        return {
            'ok': False,
            'integration_required': True,
            'provider': 'telegram',
            'message': integration_gate.get('message') or 'Connect Telegram to enable notifications',
        }

    message = f'Follow-up needed for {student.name}. Teacher flagged risk indicators for review.'
    queue_telegram_by_chat_id(db, parent.telegram_chat_id, message, student_id=student.id)
    _invalidate_action_caches(request, teacher_id=row.teacher_id)
    return {'ok': True, 'action': 'notify-parent', 'student_id': student.id}


@router.post('/token/create')
def create_token(
    payload: ActionTokenCreateRequest,
    actor: dict = Depends(_require_teacher_or_admin_session),
    db: Session = Depends(get_db),
):
    token_payload = dict(payload.payload or {})
    center_id, expected_role = _validate_token_create_scope(db, actor=actor, payload=token_payload)
    return create_action_token(
        db,
        action_type=payload.action_type,
        payload=token_payload,
        ttl_minutes=payload.ttl_minutes,
        expected_role=expected_role,
        center_id=center_id,
    )


@router.post('/notify-parent')
def notify_parent(payload: ActionTokenExecuteRequest, request: Request, db: Session = Depends(get_db)):
    session = _resolve_session_optional(request)
    try:
        token_payload = verify_token(
            db,
            payload.token,
            expected_action_type='notify-parent',
            request_role=(session or {}).get('role'),
            request_center_id=(session or {}).get('center_id'),
            request_ip=(request.client.host if request.client else ''),
            request_user_agent=request.headers.get('user-agent', ''),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parent_id = payload.parent_id or token_payload.get('parent_id')
    student_id = payload.student_id or token_payload.get('student_id')
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent or not parent.telegram_chat_id:
        raise HTTPException(status_code=404, detail='Parent not found or missing telegram chat id')

    queue_telegram_by_chat_id(db, parent.telegram_chat_id, payload.message or 'Reminder from coaching', student_id=student_id)
    consume_token(db, payload.token)
    return {'ok': True, 'action': 'notify-parent'}


@router.post('/send-fee-reminder')
def send_fee(payload: ActionTokenExecuteRequest, request: Request, db: Session = Depends(get_db)):
    session = _resolve_session_optional(request)
    try:
        token_payload = verify_token(
            db,
            payload.token,
            expected_action_type='send-fee-reminder',
            request_role=(session or {}).get('role'),
            request_center_id=(session or {}).get('center_id'),
            request_ip=(request.client.host if request.client else ''),
            request_user_agent=request.headers.get('user-agent', ''),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    student_id = payload.student_id or token_payload.get('student_id')
    fee_record_id = payload.fee_record_id or token_payload.get('fee_record_id')
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')

    amount_due = 0.0
    if fee_record_id:
        from app.models import FeeRecord
        fee = db.query(FeeRecord).filter(FeeRecord.id == fee_record_id, FeeRecord.student_id == student.id).first()
        if fee:
            amount_due = max(0.0, fee.amount - fee.paid_amount)
            upi_link = fee.upi_link or build_upi_link(student, amount_due)
        else:
            upi_link = build_upi_link(student, amount_due)
    else:
        upi_link = build_upi_link(student, amount_due)

    send_fee_reminder(db, student, amount_due, upi_link)
    consume_token(db, payload.token)
    return {'ok': True, 'action': 'send-fee-reminder', 'student_id': student.id}


@router.get('/notify-parent')
def notify_parent_get(token: str = Query(...), parent_id: int | None = None, student_id: int | None = None, db: Session = Depends(get_db)):
    logger.warning('read_endpoint_side_effect_removed endpoint=/actions/notify-parent')
    return {
        'ok': False,
        'deprecated_get': True,
        'message': 'GET command endpoint is deprecated; use POST /actions/notify-parent',
        'next': {
            'method': 'POST',
            'path': '/actions/notify-parent',
            'body': {
                'token': token,
                'parent_id': parent_id,
                'student_id': student_id,
                'message': 'Please check attendance and updates.',
            },
        },
    }


@router.get('/send-fee-reminder')
def send_fee_get(token: str = Query(...), student_id: int | None = None, fee_record_id: int | None = None, db: Session = Depends(get_db)):
    logger.warning('read_endpoint_side_effect_removed endpoint=/actions/send-fee-reminder')
    return {
        'ok': False,
        'deprecated_get': True,
        'message': 'GET command endpoint is deprecated; use POST /actions/send-fee-reminder',
        'next': {
            'method': 'POST',
            'path': '/actions/send-fee-reminder',
            'body': {'token': token, 'student_id': student_id, 'fee_record_id': fee_record_id},
        },
    }


@router.post('/escalate-student')
def escalate_student(payload: ActionTokenExecuteRequest, request: Request, db: Session = Depends(get_db)):
    session = _resolve_session_optional(request)
    try:
        token_payload = verify_token(
            db,
            payload.token,
            expected_action_type='escalate-student',
            request_role=(session or {}).get('role'),
            request_center_id=(session or {}).get('center_id'),
            request_ip=(request.client.host if request.client else ''),
            request_user_agent=request.headers.get('user-agent', ''),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    student_id = payload.student_id or token_payload.get('student_id')
    row = create_pending_action(db, action_type='manual', student_id=student_id, related_session_id=None, note='Escalated by teacher action')
    consume_token(db, payload.token)
    return {'ok': True, 'action': 'escalate-student', 'pending_action_id': row.id}


@router.get('/escalate-student')
def escalate_student_get(token: str = Query(...), student_id: int | None = None, db: Session = Depends(get_db)):
    logger.warning('read_endpoint_side_effect_removed endpoint=/actions/escalate-student')
    return {
        'ok': False,
        'deprecated_get': True,
        'message': 'GET command endpoint is deprecated; use POST /actions/escalate-student',
        'next': {
            'method': 'POST',
            'path': '/actions/escalate-student',
            'body': {'token': token, 'student_id': student_id},
        },
    }


@router.post('/mark-resolved')
def mark_resolved(payload: ActionTokenExecuteRequest, request: Request, db: Session = Depends(get_db)):
    session = _resolve_session_optional(request)
    try:
        token_payload = verify_token(
            db,
            payload.token,
            expected_action_type='mark-resolved',
            request_role=(session or {}).get('role'),
            request_center_id=(session or {}).get('center_id'),
            request_ip=(request.client.host if request.client else ''),
            request_user_agent=request.headers.get('user-agent', ''),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    action_id = token_payload.get('pending_action_id')
    if not action_id:
        raise HTTPException(status_code=400, detail='Missing pending_action_id in token payload')
    row = resolve_action(db, action_id)
    cache.invalidate_prefix('today_view')
    cache.invalidate_prefix('inbox')
    cache.invalidate_prefix('admin_ops')
    clear_operational_brain_cache()
    consume_token(db, payload.token)
    return {'ok': True, 'action': 'mark-resolved', 'pending_action_id': row.id}


def _invalidate_action_caches(request: Request, *, teacher_id: int | None = None) -> None:
    try:
        session = validate_session_token(request.cookies.get('auth_session'))
    except Exception:
        session = None
    cache.invalidate_prefix('today_view')
    cache.invalidate_prefix('inbox')
    cache.invalidate_prefix('admin_ops')
    clear_operational_brain_cache()


@router.get('/mark-resolved')
def mark_resolved_get(token: str = Query(...), db: Session = Depends(get_db)):
    logger.warning('read_endpoint_side_effect_removed endpoint=/actions/mark-resolved')
    return {
        'ok': False,
        'deprecated_get': True,
        'message': 'GET command endpoint is deprecated; use POST /actions/mark-resolved',
        'next': {
            'method': 'POST',
            'path': '/actions/mark-resolved',
            'body': {'token': token},
        },
    }
