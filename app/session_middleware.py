from urllib.parse import quote

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

        if path.startswith('/ui/student'):
            if session['role'] != Role.STUDENT.value:
                return RedirectResponse(url='/ui/login', status_code=303)
            request.state.auth_user = session
            return await call_next(request)

        if session['role'] not in (Role.TEACHER.value, Role.ADMIN.value):
            return RedirectResponse(url='/ui/login', status_code=303)

        request.state.auth_user = session
        return await call_next(request)
