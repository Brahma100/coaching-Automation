from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthUser
from app.services.auth_service import validate_session_token
from app.services.first_login_service import get_activation_state, mark_first_login_completed

router = APIRouter(prefix='/api/activation', tags=['Activation'])


def _session_user(request: Request, db: Session) -> AuthUser:
    token = request.cookies.get('auth_session')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=401, detail='Unauthorized')

    user_id = int(session.get('user_id') or 0)
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail='Unauthorized')
    return user


@router.get('/status')
def activation_status(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    if str(user.role or '') not in ('admin', 'teacher'):
        return {
            'center_name': '',
            'first_login_completed': True,
            'progress_percent': 100,
            'next_action': 'dashboard_ready',
            'checklist_items': [],
        }
    return get_activation_state(db, user)


@router.post('/complete')
def activation_complete(request: Request, db: Session = Depends(get_db)):
    user = _session_user(request, db)
    mark_first_login_completed(db, user)
    return {'ok': True, 'first_login_completed': True}
