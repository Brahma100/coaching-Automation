from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import validate_session_token
from app.services.student_risk_service import get_student_risk_detail, list_student_risk_profiles


router = APIRouter(prefix='/risk', tags=['Student Risk'])


def _require_teacher(request: Request):
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session or session['role'] not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return session


@router.get('/students')
def risk_students(
    request: Request,
    batch_id: int | None = Query(default=None),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    return list_student_risk_profiles(db, center_id=int(session.get('center_id') or 0), batch_id=batch_id)


@router.get('/student/{student_id}')
def risk_student_detail(
    student_id: int,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    data = get_student_risk_detail(db, student_id, center_id=int(session.get('center_id') or 0))
    if not data:
        raise HTTPException(status_code=404, detail='Student not found')
    return data
