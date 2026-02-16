from urllib.parse import quote

from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.models import Role
from app.services.auth_service import validate_session_token


class SessionAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._public_prefixes = (
            '/ui/login',
            '/auth/request-otp',
            '/auth/verify-otp',
            '/auth/logout',
            '/ui/attendance/session/',
            '/ui-static/',
        )

    async def dispatch(self, request: Request, call_next):
        return await self._dispatch_with_scope(request, call_next)

    async def _dispatch_with_scope(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith('/ui'):
            return await call_next(request)

        if path.startswith(self._public_prefixes):
            return await call_next(request)

        token = request.cookies.get('auth_session')
        session = validate_session_token(token)
        if not session:
            next_url = quote(path, safe='/')
            return RedirectResponse(url=f'/ui/login?next={next_url}', status_code=303)

        request_center_id = int(getattr(request.state, 'center_id', 0) or 0)
        session_center_id = int(session.get('center_id') or 0)
        if request_center_id > 0 and session_center_id > 0 and request_center_id != session_center_id:
            return JSONResponse(status_code=403, content={'detail': 'Center mismatch'})

        return await self._dispatch_authorized(request, call_next, path, session)

    async def _dispatch_authorized(self, request: Request, call_next, path: str, session: dict):
        if path.startswith('/ui/student'):
            if session['role'] != Role.STUDENT.value:
                return RedirectResponse(url='/ui/login', status_code=303)
            request.state.auth_user = session
            return await call_next(request)

        if session['role'] not in (Role.TEACHER.value, Role.ADMIN.value):
            return RedirectResponse(url='/ui/login', status_code=303)

        request.state.auth_user = session
        return await call_next(request)
