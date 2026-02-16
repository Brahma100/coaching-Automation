from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FeeRecord, ParentStudentMap, Student, StudentRiskProfile
from app.services.action_token_service import verify_token
from app.services.attendance_session_service import load_attendance_session_sheet
from app.services.auth_service import validate_session_token

templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui', tags=['Session Summary UI'])
logger = logging.getLogger(__name__)


def _authorize_summary(db: Session, request: Request, session_id: int, token: str | None) -> dict:
    if not token:
        raise HTTPException(status_code=403, detail='Unauthorized')
    session_token = request.cookies.get('auth_session')
    if not session_token:
        authorization = request.headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            session_token = authorization[7:].strip()
    request_user = validate_session_token(session_token)
    last_error = None
    payload = None
    for action_type in ('session_summary', 'notification_summary'):
        try:
            payload = verify_token(
                db,
                token,
                expected_action_type=action_type,
                request_role=(request_user or {}).get('role'),
                request_center_id=(request_user or {}).get('center_id'),
                request_ip=(request.client.host if request.client else ''),
                request_user_agent=request.headers.get('user-agent', ''),
            )
            break
        except ValueError as exc:
            last_error = exc
    if not payload:
        raise HTTPException(status_code=400, detail=str(last_error) if last_error else 'Invalid token')
    if int(payload.get('session_id') or 0) != session_id:
        raise HTTPException(status_code=403, detail='Token does not match session')
    return payload


def _build_action_links(db: Session, student_id: int, parent_id: int | None, fee_record_id: int | None, pending_action_id: int | None) -> dict:
    # DEPRECATED: read endpoints should not mint action tokens.
    return {
        'notify_parent_url': None,
        'fee_reminder_url': None,
        'needs_notify_parent_token': True,
        'needs_fee_reminder_token': True,
        'token_prepare_endpoint': '/api/commands/prepare-notification-side-effects',
        'token_prepare_payload': {
            'mode': 'session_student_actions',
            'payload': {
                'student_id': student_id,
                'parent_id': parent_id,
                'fee_record_id': fee_record_id,
                'pending_action_id': pending_action_id,
            },
        },
    }


@router.get('/session/summary/{session_id}')
def session_summary_page(
    session_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    payload = _authorize_summary(db, request, session_id, token)
    teacher_id = int(payload.get('teacher_id') or 0)
    session_action_command = None
    if teacher_id:
        logger.warning(
            'read_endpoint_side_effect_removed endpoint=/ui/session/summary/%s side_effect=resolve_review_action_on_open teacher_id=%s',
            session_id,
            teacher_id,
        )
        session_action_command = {
            'needs_command': True,
            'endpoint': '/api/commands/ensure-session-actions',
            'payload': {'teacher_id': teacher_id, 'session_id': session_id},
        }
    sheet = load_attendance_session_sheet(db, session_id)
    rows = sheet['rows']
    student_ids = [row['student_id'] for row in rows]

    fee_rows = (
        db.query(FeeRecord)
        .filter(FeeRecord.student_id.in_(student_ids), FeeRecord.is_paid.is_(False))
        .all()
    )
    fee_by_student = {}
    for fee in fee_rows:
        fee_by_student.setdefault(fee.student_id, []).append(fee)

    risk_rows = (
        db.query(StudentRiskProfile)
        .filter(StudentRiskProfile.student_id.in_(student_ids))
        .all()
    )
    risk_by_student = {row.student_id: row for row in risk_rows}

    parents = db.query(ParentStudentMap).filter(ParentStudentMap.student_id.in_(student_ids)).all()
    parent_by_student = {row.student_id: row.parent_id for row in parents}

    enriched = []
    for row in rows:
        student_id = row['student_id']
        fee_list = fee_by_student.get(student_id, [])
        fee_due = sum(max(0.0, f.amount - f.paid_amount) for f in fee_list)
        risk = risk_by_student.get(student_id)
        actions = _build_action_links(db, student_id, parent_by_student.get(student_id), fee_list[0].id if fee_list else None, None)
        enriched.append(
            {
                **row,
                'fee_due': fee_due,
                'risk_level': risk.risk_level if risk else 'LOW',
                'risk_score': round(risk.final_risk_score, 2) if risk else None,
                'parent_id': parent_by_student.get(student_id),
                **actions,
            }
        )

    return templates.TemplateResponse(
        'session_summary.html',
        {
            'request': request,
            'sheet': sheet,
            'rows': enriched,
            'session_row': sheet['session'],
            'attendance_date': sheet['attendance_date'],
            'session_action_command': session_action_command,
        },
    )


@router.get('/class/start/{session_id}')
def class_start_page(
    session_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _authorize_summary(db, request, session_id, token)
    sheet = load_attendance_session_sheet(db, session_id)
    return templates.TemplateResponse(
        'class_start.html',
        {
            'request': request,
            'session_row': sheet['session'],
            'attendance_date': sheet['attendance_date'],
        },
    )
