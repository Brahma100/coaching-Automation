from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.time_provider import default_time_provider
from app.db import get_db

from app.services.action_token_service import load_token_row, verify_token
from app.services.auth_service import validate_session_token


router = APIRouter(prefix='/api/tokens', tags=['Tokens'])
logger = logging.getLogger(__name__)

ALLOWED_TOKEN_TYPES = {'attendance_open', 'attendance_review', 'class_start', 'session_summary'}


@router.get('/validate')
def validate_token(
    request: Request,
    token: str = Query(...),
    session_id: int = Query(...),
    expected_type: str | None = Query(default=None, alias='expected'),
    db: Session = Depends(get_db),
):
    if expected_type and expected_type not in ALLOWED_TOKEN_TYPES:
        raise HTTPException(status_code=400, detail='Invalid token type')

    candidates = [expected_type] if expected_type else list(ALLOWED_TOKEN_TYPES)
    last_error = None
    payload = None
    matched_type = None
    token_row = load_token_row(db, token)
    session_token = request.cookies.get('auth_session')
    if not session_token:
        authorization = request.headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            session_token = authorization[7:].strip()
    request_user = validate_session_token(session_token)
    for candidate in candidates:
        try:
            payload = verify_token(
                db,
                token,
                expected_action_type=candidate,
                request_role=(request_user or {}).get('role'),
                request_center_id=(request_user or {}).get('center_id'),
                request_ip=(request.client.host if request.client else ''),
                request_user_agent=request.headers.get('user-agent', ''),
            )
            matched_type = candidate
            break
        except ValueError as exc:
            last_error = exc
            continue

    if not payload or not matched_type:
        if token_row and token_row.expires_at < default_time_provider.now().replace(tzinfo=None):
            logger.warning('read_endpoint_side_effect_removed endpoint=/api/tokens/validate side_effect=mark_expired_token_consumed')
        raise HTTPException(status_code=401, detail=str(last_error) if last_error else 'Invalid token')

    token_session_id = int(payload.get('session_id') or 0)
    if token_session_id != session_id:
        raise HTTPException(status_code=401, detail='Token does not match session')

    return {
        'valid': True,
        'sessionId': session_id,
        'role': payload.get('role') or 'teacher',
        'action_type': matched_type,
        'expires_at': token_row.expires_at.isoformat() if token_row else None,
    }
