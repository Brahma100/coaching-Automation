from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import FeeRecord, ParentStudentMap, StudentRiskProfile
from app.services.action_token_service import verify_token
from app.services.attendance_session_service import load_attendance_session_sheet


router = APIRouter(prefix='/api/session', tags=['Session Summary API'])


@router.get('/summary/{session_id}')
def session_summary_api(
    session_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=401, detail='Missing token')
    try:
        payload = verify_token(db, token, expected_action_type='session_summary')
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if int(payload.get('session_id') or 0) != session_id:
        raise HTTPException(status_code=401, detail='Token does not match session')

    sheet = load_attendance_session_sheet(db, session_id)
    rows = sheet['rows']
    student_ids = [row['student_id'] for row in rows]

    fee_rows = (
        db.query(FeeRecord)
        .filter(FeeRecord.student_id.in_(student_ids), FeeRecord.is_paid.is_(False))
        .all()
    )
    fee_by_student: dict[int, list[FeeRecord]] = {}
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
        enriched.append(
            {
                **row,
                'fee_due': fee_due,
                'risk_level': risk.risk_level if risk else 'LOW',
                'risk_score': round(risk.final_risk_score, 2) if risk else None,
                'parent_id': parent_by_student.get(student_id),
            }
        )

    return {
        'session': {
            'id': sheet['session'].id,
            'batch_id': sheet['session'].batch_id,
            'subject': sheet['session'].subject,
            'scheduled_start': sheet['session'].scheduled_start.isoformat(),
            'status': sheet['session'].status,
        },
        'attendance_date': sheet['attendance_date'].isoformat(),
        'rows': enriched,
    }
