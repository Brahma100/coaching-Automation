from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.cache import cache, cache_key, cached_view
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.models import PendingAction, Role
from app.services.auth_service import validate_session_token
from app.services.inbox_automation import list_inbox_actions
from app.services.pending_action_service import resolve_action


router = APIRouter(prefix='/api/inbox', tags=['Inbox'])
logger = logging.getLogger(__name__)


class ResolvePayload(BaseModel):
    resolution_note: str | None = None


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('/actions')
@cached_view(ttl=30, key_builder=lambda request, session=None, **_: _inbox_key(session))
def list_actions(
    request: Request,
    bypass_cache: bool = Query(default=False),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    teacher_id = int(session.get('user_id') or 0)
    rows = list_inbox_actions(db, teacher_id=teacher_id)
    now = default_time_provider.now().replace(tzinfo=None)
    payload = []
    for row in rows:
        payload.append(
            {
                'id': row.id,
                'action_type': row.action_type or row.type,
                'status': row.status,
                'student_id': row.student_id,
                'session_id': row.session_id or row.related_session_id,
                'teacher_id': row.teacher_id,
                'due_at': row.due_at.isoformat() if row.due_at else None,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'overdue': bool(row.due_at and row.due_at < now),
                'summary_url': None,
                'needs_token': bool(row.action_type == 'review_session_summary' and row.session_id),
                'token_type': 'session_summary' if row.action_type == 'review_session_summary' and row.session_id else None,
                'token_entity_id': int(row.session_id or 0) if row.action_type == 'review_session_summary' and row.session_id else None,
                'token_command_endpoint': '/api/commands/generate-token' if row.action_type == 'review_session_summary' and row.session_id else None,
                'token_payload': (
                    {
                        'session_id': int(row.session_id or 0),
                        'teacher_id': teacher_id,
                        'role': 'teacher',
                    }
                    if row.action_type == 'review_session_summary' and row.session_id
                    else None
                ),
                'token_ttl_minutes': 24 * 60 if row.action_type == 'review_session_summary' and row.session_id else None,
                'note': row.note,
            }
        )
    logger.warning('read_endpoint_side_effect_removed endpoint=/api/inbox/actions side_effect=summary_token_creation')
    return payload


@router.post('/actions/{action_id}/resolve')
def resolve_action_api(
    action_id: int,
    payload: ResolvePayload,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    teacher_id = int(session.get('user_id') or 0)
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Pending action not found')
    if row.teacher_id and row.teacher_id != teacher_id and session.get('role') != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail='Unauthorized')
    resolved = resolve_action(db, action_id, resolution_note=payload.resolution_note)
    actor_teacher_id = int(session.get('user_id') or 0)
    affected_teacher_id = int(row.teacher_id or actor_teacher_id or 0)
    cache.invalidate_prefix('inbox')
    cache.invalidate_prefix('today_view')
    cache.invalidate_prefix('admin_ops')
    return {'ok': True, 'action_id': resolved.id, 'status': resolved.status}


def _inbox_key(session: dict | None) -> str:
    role = (session.get('role') or '').lower() if session else 'unknown'
    teacher_id = int(session.get('user_id') or 0) if session else 0
    return cache_key('inbox', f'{role}:{teacher_id}')
