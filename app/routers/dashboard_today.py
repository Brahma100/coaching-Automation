from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.cache import cache_key, cached_view
from app.db import get_db
from app.models import Role
from app.services import snapshot_service
from app.services.auth_service import validate_session_token
from app.services.dashboard_today_service import get_today_view


router = APIRouter(prefix='/api/dashboard', tags=['Dashboard'])


def _require_user(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('/today')
@cached_view(ttl=None, key_builder=lambda request, teacher_id=None, session=None, **_: _today_key(session, teacher_id))
def today_view(
    request: Request,
    teacher_id: int | None = Query(default=None),
    bypass_cache: bool = Query(default=False),
    session: dict = Depends(_require_user),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if teacher_id is not None and role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail='Unauthorized')
    today = datetime.utcnow().date()
    effective_teacher_id = int(teacher_id or 0) if role == Role.ADMIN.value else int(session.get('user_id') or 0)
    if role == Role.ADMIN.value and teacher_id is None:
        effective_teacher_id = 0

    if not bypass_cache:
        snapshot = snapshot_service.get_teacher_today_snapshot(db, teacher_id=effective_teacher_id, day=today)
        if snapshot is not None:
            return snapshot
    try:
        payload = get_today_view(db, actor=session, teacher_filter_id=teacher_id)
        try:
            snapshot_service.upsert_teacher_today_snapshot(db, teacher_id=effective_teacher_id, day=today, payload=payload)
        except Exception:
            pass
        return payload
    except Exception:
        return {
            'overdue_actions': [],
            'due_today_actions': [],
            'today_classes': [],
            'flags': {'fee_due_present': [], 'high_risk_students': [], 'repeat_absentees': []},
            'completed_today': [],
        }


def _today_key(session: dict | None, teacher_id: int | None) -> str:
    today = datetime.utcnow().date().isoformat()
    role = (session.get('role') or '').lower() if session else 'unknown'
    if role == Role.ADMIN.value:
        scope = teacher_id or 'all'
    else:
        scope = session.get('user_id') if session else 'unknown'
    return cache_key('today_view', f"{role}:{scope}:{today}")
