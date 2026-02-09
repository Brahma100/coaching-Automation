from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.daily_teacher_brief_service import build_daily_teacher_brief


router = APIRouter(prefix='/api/teacher/brief', tags=['Teacher Brief'])


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token
    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_teacher_or_admin(request: Request) -> dict:
    token = _resolve_token(request)
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=401, detail='Unauthorized')
    if session.get('role') not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Teacher/admin access required')
    return session


@router.get('/today')
def teacher_brief_today(
    request: Request,
    teacher_id: int | None = Query(default=None, ge=1),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = session.get('role')
    resolved_teacher_id = teacher_id
    if role == Role.TEACHER.value:
        resolved_teacher_id = int(session.get('user_id') or 0)
    elif resolved_teacher_id is None:
        resolved_teacher_id = int(session.get('user_id') or 0)

    if resolved_teacher_id <= 0:
        raise HTTPException(status_code=400, detail='No teacher id available for summary')

    summary = build_daily_teacher_brief(db, teacher_id=resolved_teacher_id, day=date.today())
    return summary
