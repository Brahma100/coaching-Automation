from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from datetime import datetime

from app.services.action_token_service import load_token_row, verify_token


router = APIRouter(prefix='/api/tokens', tags=['Tokens'])

ALLOWED_TOKEN_TYPES = {'attendance_open', 'attendance_review', 'class_start', 'session_summary'}


@router.get('/validate')
def validate_token(
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
    for candidate in candidates:
        try:
            payload = verify_token(db, token, expected_action_type=candidate)
            matched_type = candidate
            break
        except ValueError as exc:
            last_error = exc
            continue

    if not payload or not matched_type:
        if token_row and token_row.expires_at < datetime.utcnow():
            token_row.consumed = True
            db.commit()
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
