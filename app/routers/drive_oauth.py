from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.cache import cache, cache_key
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.models import AuthUser, DriveOAuthToken, Role
from app.services.auth_service import validate_session_token
from app.services.drive_oauth_service import (
    DriveOAuthError,
    build_oauth_start_url,
    decode_oauth_state,
    drive_connected,
    exchange_code_for_refresh_token,
    resolve_refresh_token,
    store_refresh_token,
)


router = APIRouter(prefix='/api/drive', tags=['Drive OAuth'])
logger = logging.getLogger(__name__)
_OAUTH_STATE_TTL_SECONDS = 600


def _request_center_id(request: Request, session: dict) -> int:
    request_center_id = int(getattr(request.state, 'center_id', 0) or 0)
    session_center_id = int(session.get('center_id') or 0)
    return request_center_id if request_center_id > 0 else session_center_id


def _oauth_nonce_cache_key(center_id: int, nonce: str) -> str:
    return cache_key('drive_oauth_nonce', f'{int(center_id)}:{str(nonce or "")}')


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
    user_id = int(session.get('user_id') or 0)
    center_id = _request_center_id(request, session)
    if user_id <= 0 or center_id <= 0:
        raise HTTPException(status_code=403, detail='Invalid admin center scope')
    try:
        url = build_oauth_start_url(user_id, center_id=center_id)
    except DriveOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = (url.split('state=', 1)[1].split('&', 1)[0]) if 'state=' in url else ''
    payload = decode_oauth_state(state)
    nonce = str((payload or {}).get('nonce') or '')
    if not nonce:
        raise HTTPException(status_code=400, detail='Invalid OAuth state')

    cache.set_cached(
        _oauth_nonce_cache_key(center_id, nonce),
        {'uid': user_id, 'center_id': center_id},
        ttl=_OAUTH_STATE_TTL_SECONDS,
    )
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
    if not state:
        logger.warning('oauth_callback_rejected_state reason=missing_state')
        raise HTTPException(status_code=400, detail='Missing OAuth state')

    user_id = int(session.get('user_id') or 0)
    center_id = _request_center_id(request, session)
    if user_id <= 0 or center_id <= 0:
        raise HTTPException(status_code=403, detail='Invalid admin center scope')

    admin = db.query(AuthUser).filter(AuthUser.id == user_id, AuthUser.center_id == center_id).first()
    if not admin:
        logger.warning('oauth_callback_rejected_state reason=admin_center_mismatch center_id=%s', center_id)
        raise HTTPException(status_code=403, detail='Center mismatch')

    payload = decode_oauth_state(state)
    if not payload:
        logger.warning('oauth_callback_rejected_state reason=invalid_state center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='Invalid OAuth state')

    state_user_id = int(payload.get('uid') or 0)
    state_center_id = int(payload.get('center_id') or 0)
    nonce = str(payload.get('nonce') or '').strip()
    issued_at = int(payload.get('issued_at') or 0)
    now_ts = int(default_time_provider.now().timestamp())

    if state_user_id != user_id:
        logger.warning('oauth_callback_rejected_state reason=user_mismatch center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='Invalid OAuth state')
    if state_center_id <= 0 or nonce == '' or issued_at <= 0:
        logger.warning('oauth_callback_rejected_state reason=missing_fields center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='Invalid OAuth state')
    if state_center_id != center_id:
        logger.warning(
            'oauth_callback_rejected_state reason=center_mismatch request_center_id=%s state_center_id=%s',
            center_id,
            state_center_id,
        )
        raise HTTPException(status_code=403, detail='Center mismatch')
    if issued_at > now_ts or (now_ts - issued_at) > _OAUTH_STATE_TTL_SECONDS:
        logger.warning('oauth_callback_rejected_state reason=expired_state center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='Expired OAuth state')

    nonce_key = _oauth_nonce_cache_key(center_id, nonce)
    nonce_payload = cache.get_cached(nonce_key)
    if not isinstance(nonce_payload, dict):
        logger.warning('oauth_callback_replay_detected center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='OAuth state replay detected')
    if int(nonce_payload.get('uid') or 0) != user_id or int(nonce_payload.get('center_id') or 0) != center_id:
        logger.warning('oauth_callback_rejected_state reason=nonce_payload_mismatch center_id=%s', center_id)
        raise HTTPException(status_code=400, detail='Invalid OAuth state')

    cache.invalidate(nonce_key)

    try:
        refresh_token, _ = exchange_code_for_refresh_token(code)
    except DriveOAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing_row = db.query(DriveOAuthToken).filter(DriveOAuthToken.user_id == user_id).first()
    if not refresh_token and existing_row:
        logger.info('oauth_already_connected center_id=%s', center_id)
        logger.info('oauth_callback_success center_id=%s', center_id)
        return {'ok': True, 'message': 'Google Drive already connected', 'idempotent': True}

    if not refresh_token:
        try:
            _, refresh_token = resolve_refresh_token(db, user_id=user_id)
        except Exception:
            raise HTTPException(status_code=400, detail='Google did not return refresh token. Retry consent flow.')

    if existing_row:
        logger.info('oauth_already_connected center_id=%s', center_id)
        logger.info('oauth_callback_success center_id=%s', center_id)
        return {'ok': True, 'message': 'Google Drive already connected', 'idempotent': True}

    store_refresh_token(db, user_id=user_id, refresh_token=refresh_token)
    logger.info('oauth_callback_success center_id=%s', center_id)
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
