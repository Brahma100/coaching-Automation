from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.cache import cache_key, cached_view
from app.db import get_db
from app.services import snapshot_service
from app.services.admin_ops_dashboard_service import get_admin_ops_dashboard
from app.services.allowlist_admin_service import require_admin_session


router = APIRouter(prefix='/api/admin', tags=['Admin Ops'])


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token
    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_admin(request: Request, db: Session = Depends(get_db)) -> dict:
    token = _resolve_token(request)
    try:
        return require_admin_session(db, token)
    except PermissionError as exc:
        detail = str(exc) or 'Admin access required'
        status = 401 if 'Unauthorized' in detail else 403
        raise HTTPException(status_code=status, detail=detail) from exc


@router.get('/ops-dashboard')
@cached_view(ttl=None, key_builder=lambda **_: cache_key('admin_ops'))
def admin_ops_dashboard(
    bypass_cache: bool = Query(default=False),
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    today = datetime.utcnow().date()
    if not bypass_cache:
        snapshot = snapshot_service.get_admin_ops_snapshot(db, day=today)
        if snapshot is not None:
            return snapshot
    payload = get_admin_ops_dashboard(db)
    try:
        snapshot_service.upsert_admin_ops_snapshot(db, day=today, payload=payload)
    except Exception:
        pass
    return payload
