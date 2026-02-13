from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DriveOAuthToken, Role
from app.services.auth_service import validate_session_token
from app.services.drive_oauth_service import (
    DriveOAuthError,
    build_oauth_start_url,
    drive_connected,
    exchange_code_for_refresh_token,
    resolve_refresh_token,
    store_refresh_token,
    validate_oauth_state,
)


router = APIRouter(prefix='/api/drive', tags=['Drive OAuth'])


def _require_admin(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    if not token:
        authorization = request.headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            token = authorization[7:].strip()
    session = validate_session_token(token)
    if not session or (session.get('role') or '').lower() != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail='Admin access required')
    return session


@router.get('/oauth/start')
def drive_oauth_start(request: Request, session: dict = Depends(_require_admin)):
    try:
        url = build_oauth_start_url(int(session.get('user_id') or 0))
    except DriveOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)


@router.get('/oauth/callback')
def drive_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    session: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    if not code:
        raise HTTPException(status_code=400, detail='Missing authorization code')

    user_id = int(session.get('user_id') or 0)
    if state and not validate_oauth_state(state, user_id):
        raise HTTPException(status_code=400, detail='Invalid OAuth state')

    try:
        refresh_token, _ = exchange_code_for_refresh_token(code)
    except DriveOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not refresh_token:
        try:
            _, refresh_token = resolve_refresh_token(db, user_id=user_id)
        except Exception:
            raise HTTPException(status_code=400, detail='Google did not return refresh token. Retry consent flow.')

    store_refresh_token(db, user_id=user_id, refresh_token=refresh_token)
    return {'ok': True, 'message': 'Google Drive connected successfully'}


@router.get('/status')
def drive_status(request: Request, _: dict = Depends(_require_admin), db: Session = Depends(get_db)):
    return {'connected': drive_connected(db)}


@router.post('/disconnect')
def drive_disconnect(
    request: Request,
    session: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    user_id = int(session.get('user_id') or 0)
    row = db.query(DriveOAuthToken).filter(DriveOAuthToken.user_id == user_id).first()
    if row:
        db.delete(row)
        db.commit()
    return {'ok': True, 'connected': False}
