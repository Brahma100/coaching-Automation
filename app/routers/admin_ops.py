from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.cache import cache_key, cached_view
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.domain.services.system_health_service import get_system_health
from app.services import snapshot_service
from app.services.admin_ops_dashboard_service import get_admin_ops_dashboard
from app.services.allowlist_admin_service import require_admin_session


router = APIRouter(prefix='/api/admin', tags=['Admin Ops'])
logger = logging.getLogger(__name__)


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
@cached_view(ttl=None, key_builder=lambda actor=None, **_: _admin_ops_key(actor))
def admin_ops_dashboard(
    bypass_cache: bool = Query(default=False),
    actor: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    today = default_time_provider.today()
    center_id = int((actor or {}).get('center_id') or 0) or None
    if not bypass_cache:
        snapshot = snapshot_service.get_admin_ops_snapshot(db, day=today, center_id=center_id)
        if snapshot is not None:
            return snapshot
    payload = get_admin_ops_dashboard(db, center_id=int((actor or {}).get('center_id') or 0))
    logger.warning('read_endpoint_side_effect_removed endpoint=/api/admin/ops-dashboard side_effect=admin_ops_snapshot_upsert')
    return payload


def _admin_ops_key(actor: dict | None) -> str:
    role = str((actor or {}).get('role') or 'admin').lower()
    user_id = int((actor or {}).get('user_id') or 0)
    center_id = int((actor or {}).get('center_id') or 0)
    return cache_key('admin_ops', f'{center_id}:{role}:{user_id}')


@router.post('/system-health')
def admin_system_health(
    actor: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    scoped_center_id = int((actor or {}).get('center_id') or 0) or None
    return get_system_health(db, center_id=scoped_center_id)
