from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.operational_brain_service import get_operational_brain


router = APIRouter(prefix='/api', tags=['OperationalBrain'])


def _require_user(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('/brain')
def operational_brain(
    bypass_cache: bool = Query(default=False),
    session: dict = Depends(_require_user),
    db: Session = Depends(get_db),
):
    role = str(session.get('role') or '').strip().lower()
    if role == Role.STUDENT.value:
        raise HTTPException(status_code=403, detail='Unauthorized')
    return get_operational_brain(db, session, bypass_cache=bool(bypass_cache))
