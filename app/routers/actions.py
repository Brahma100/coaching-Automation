from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Parent, Student
from app.schemas import ActionTokenCreateRequest, ActionTokenExecuteRequest
from app.services.action_token_service import create_action_token, verify_and_consume_token
from app.services.comms_service import queue_telegram_by_chat_id, send_fee_reminder
from app.services.fee_service import build_upi_link
from app.services.pending_action_service import create_pending_action, resolve_action


router = APIRouter(prefix='/actions', tags=['Actions'])


@router.post('/token/create')
def create_token(payload: ActionTokenCreateRequest, db: Session = Depends(get_db)):
    return create_action_token(db, action_type=payload.action_type, payload=payload.payload, ttl_minutes=payload.ttl_minutes)


@router.post('/notify-parent')
def notify_parent(payload: ActionTokenExecuteRequest, db: Session = Depends(get_db)):
    try:
        token_payload = verify_and_consume_token(db, payload.token, expected_action_type='notify-parent')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parent_id = payload.parent_id or token_payload.get('parent_id')
    student_id = payload.student_id or token_payload.get('student_id')
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent or not parent.telegram_chat_id:
        raise HTTPException(status_code=404, detail='Parent not found or missing telegram chat id')

    queue_telegram_by_chat_id(db, parent.telegram_chat_id, payload.message or 'Reminder from coaching', student_id=student_id)
    return {'ok': True, 'action': 'notify-parent'}


@router.post('/send-fee-reminder')
def send_fee(payload: ActionTokenExecuteRequest, db: Session = Depends(get_db)):
    try:
        token_payload = verify_and_consume_token(db, payload.token, expected_action_type='send-fee-reminder')
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
    return {'ok': True, 'action': 'send-fee-reminder', 'student_id': student.id}


@router.get('/notify-parent')
def notify_parent_get(token: str = Query(...), parent_id: int | None = None, student_id: int | None = None, db: Session = Depends(get_db)):
    payload = ActionTokenExecuteRequest(token=token, parent_id=parent_id, student_id=student_id, message='Please check attendance and updates.')
    return notify_parent(payload, db)


@router.get('/send-fee-reminder')
def send_fee_get(token: str = Query(...), student_id: int | None = None, fee_record_id: int | None = None, db: Session = Depends(get_db)):
    payload = ActionTokenExecuteRequest(token=token, student_id=student_id, fee_record_id=fee_record_id)
    return send_fee(payload, db)


@router.post('/escalate-student')
def escalate_student(payload: ActionTokenExecuteRequest, db: Session = Depends(get_db)):
    try:
        token_payload = verify_and_consume_token(db, payload.token, expected_action_type='escalate-student')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    student_id = payload.student_id or token_payload.get('student_id')
    row = create_pending_action(db, action_type='manual', student_id=student_id, related_session_id=None, note='Escalated by teacher action')
    return {'ok': True, 'action': 'escalate-student', 'pending_action_id': row.id}


@router.get('/escalate-student')
def escalate_student_get(token: str = Query(...), student_id: int | None = None, db: Session = Depends(get_db)):
    payload = ActionTokenExecuteRequest(token=token, student_id=student_id)
    return escalate_student(payload, db)


@router.post('/mark-resolved')
def mark_resolved(payload: ActionTokenExecuteRequest, db: Session = Depends(get_db)):
    try:
        token_payload = verify_and_consume_token(db, payload.token, expected_action_type='mark-resolved')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    action_id = token_payload.get('pending_action_id')
    if not action_id:
        raise HTTPException(status_code=400, detail='Missing pending_action_id in token payload')
    row = resolve_action(db, action_id)
    return {'ok': True, 'action': 'mark-resolved', 'pending_action_id': row.id}


@router.get('/mark-resolved')
def mark_resolved_get(token: str = Query(...), db: Session = Depends(get_db)):
    payload = ActionTokenExecuteRequest(token=token)
    return mark_resolved(payload, db)
