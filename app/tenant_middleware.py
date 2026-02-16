from __future__ import annotations

import ipaddress
import logging
from collections.abc import Callable

from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings
from app.db import SessionLocal
from app.models import Center
from app.services.auth_service import validate_session_token
from app.services.center_scope_service import center_context

logger = logging.getLogger(__name__)


def get_request_center_id(request: Request) -> int | None:
    value = int(getattr(request.state, 'center_id', 0) or 0)
    return value if value > 0 else None


def _extract_subdomain(host_header: str) -> str:
    host = (host_header or '').strip().lower()
    if not host:
        return ''
    host_without_port = host
    if host_without_port.startswith('['):
        bracket_end = host_without_port.find(']')
        if bracket_end != -1:
            host_without_port = host_without_port[1:bracket_end]
    else:
        host_without_port = host_without_port.split(':', 1)[0]
    try:
        ipaddress.ip_address(host_without_port.strip('[]'))
        return ''
    except ValueError:
        pass
    labels = [label for label in host_without_port.split('.') if label]
    if not labels:
        return ''
    if labels[-1] == 'localhost':
        return labels[0] if len(labels) >= 2 else ''
    tenant_base_domain = (settings.tenant_base_domain or '').strip().lower().lstrip('.')
    if tenant_base_domain and host_without_port.endswith(f'.{tenant_base_domain}'):
        return labels[0]
    if settings.app_env.lower() in {'local', 'dev', 'development', 'test'}:
        return ''
    if len(labels) < 3:
        return ''
    return labels[0]


def _get_or_create_default_center(db: Session) -> Center:
    row = db.query(Center).filter(Center.slug == settings.dev_default_center_slug).first()
    if row:
        return row
    row = Center(
        name=settings.dev_default_center_slug,
        slug=settings.dev_default_center_slug,
        timezone=settings.app_timezone or 'Asia/Kolkata',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, session_factory: sessionmaker | Callable[[], Session] | None = None):
        super().__init__(app)
        self._session_factory = session_factory or SessionLocal

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get('host', '')
        slug = _extract_subdomain(host)

        db: Session = self._session_factory()
        try:
            center = None
            if slug:
                center = db.query(Center).filter(Center.slug == slug).first()
                if not center:
                    return JSONResponse(status_code=404, content={'detail': 'Center not found'})
            else:
                center = _get_or_create_default_center(db)
                logger.info(
                    'tenant_resolution_fallback_default_center host=%s slug=%s center_id=%s',
                    host,
                    settings.dev_default_center_slug,
                    center.id,
                )
            request.state.center_id = int(center.id)
            request.state.center_slug = str(center.slug)
        finally:
            db.close()

        token = request.cookies.get('auth_session')
        if not token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.lower().startswith('bearer '):
                token = auth_header.split(' ', 1)[1].strip()
        session = validate_session_token(token)
        if session:
            session_center_id = int(session.get('center_id') or 0)
            if session_center_id > 0 and session_center_id != int(request.state.center_id):
                return JSONResponse(status_code=403, content={'detail': 'Center mismatch'})

        with center_context(int(request.state.center_id)):
            return await call_next(request)
