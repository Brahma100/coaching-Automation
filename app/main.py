from contextlib import asynccontextmanager
import logging
import time
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.communication.bootstrap import shutdown_embedded_communication, startup_embedded_communication
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import actions, activation, admin_allowlist, admin_ops, allowlist_admin, allowlist_admin_ui, attendance, attendance_manage_ui, attendance_session_api, attendance_session_ui, auth, batches_ui, brain, catalog, class_session, commands, communications, dashboard, dashboard_today, drive_oauth, fee, homework, inbox, integrations, notes, offers, onboarding, parents, referral, rules, session_summary_api, session_summary_ui, student_api, student_risk, student_ui, students_ui, teacher_automation_rules, teacher_brief, teacher_calendar, teacher_communication_settings, teacher_profile, telegram_linking, time_capacity, tokens, ui
from app.scheduler import start_scheduler, stop_scheduler
from app.session_middleware import SessionAuthMiddleware
from app.tenant_middleware import TenantResolutionMiddleware, get_request_center_id
from app.route_logging import EndpointNameRoute
from app.services.center_scope_service import center_context
from app.services.auth_service import validate_session_token
from app.services.bootstrap_service import run_bootstrap
from app.services.onboarding_service import is_center_onboarding_incomplete
from app.metrics import flush_cache_metrics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_bootstrap(db)
    finally:
        db.close()
    await startup_embedded_communication()
    start_scheduler()
    yield
    await shutdown_embedded_communication()
    stop_scheduler()
    flush_cache_metrics()


app = FastAPI(title=settings.app_name, version='0.1.0', lifespan=lifespan)
app.router.route_class = EndpointNameRoute
app.mount('/ui-static', StaticFiles(directory='app/ui/static'), name='ui-static')
app.add_middleware(TenantResolutionMiddleware)
app.add_middleware(SessionAuthMiddleware)

if (settings.communication_mode or '').strip().lower() == 'embedded':
    service_repo = Path(__file__).resolve().parents[1] / 'coach-communication-service'
    if service_repo.exists() and str(service_repo) not in sys.path:
        sys.path.append(str(service_repo))
    try:
        from communication.api import router as embedded_communication_router  # type: ignore

        app.include_router(embedded_communication_router, prefix='/internal/communication')
    except Exception:
        logging.getLogger(__name__).exception('embedded_communication_mount_failed')


@app.middleware('http')
async def slow_request_logger(request: Request, call_next):
    started = time.perf_counter()
    scoped_center_id = get_request_center_id(request)
    if scoped_center_id is None:
        token = request.cookies.get('auth_session')
        session = validate_session_token(token)
        scoped_center_id = session.get('center_id') if session else None
    path = request.url.path
    if path.startswith('/api') and not path.startswith('/api/onboard'):
        if not path.startswith('/api/tokens') and not path.startswith('/api/telegram/link'):
            token = request.cookies.get('auth_session')
            if not token:
                auth_header = request.headers.get('Authorization', '')
                if auth_header.lower().startswith('bearer '):
                    token = auth_header.split(' ', 1)[1].strip()
            session = validate_session_token(token)
            center_id = int((session or {}).get('center_id') or 0)
            if center_id > 0:
                db = SessionLocal()
                try:
                    if is_center_onboarding_incomplete(db, center_id):
                        from fastapi.responses import JSONResponse

                        return JSONResponse(status_code=403, content={'detail': 'Onboarding incomplete'})
                finally:
                    db.close()
    with center_context(scoped_center_id):
        response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000.0
    if duration_ms >= settings.metrics_slow_ms:
        logging.getLogger('app.request').info(
            'request_slow path=%s method=%s status_code=%s duration_ms=%.2f',
            request.url.path,
            request.method,
            response.status_code,
            duration_ms,
        )
    return response

app.include_router(attendance.router)
app.include_router(fee.router)
app.include_router(dashboard.router)
app.include_router(dashboard_today.router)
app.include_router(referral.router)
app.include_router(homework.router)
app.include_router(notes.router)
app.include_router(activation.router)
app.include_router(brain.router)
app.include_router(drive_oauth.router)
app.include_router(inbox.router)
app.include_router(integrations.router)
app.include_router(communications.router)
app.include_router(class_session.router)
app.include_router(parents.router)
app.include_router(actions.router)
app.include_router(commands.router)
app.include_router(offers.router)
app.include_router(onboarding.router)
app.include_router(rules.router)
app.include_router(ui.router)
app.include_router(attendance_manage_ui.router)
app.include_router(attendance_session_api.router)
app.include_router(attendance_session_ui.router)
app.include_router(auth.router)
app.include_router(students_ui.router)
app.include_router(batches_ui.router)
app.include_router(catalog.router)
app.include_router(student_risk.router)
app.include_router(admin_allowlist.router)
app.include_router(admin_ops.router)
app.include_router(allowlist_admin.router)
app.include_router(allowlist_admin_ui.router)
app.include_router(student_api.router)
app.include_router(student_ui.router)
app.include_router(teacher_brief.router)
app.include_router(teacher_calendar.router)
app.include_router(time_capacity.router)
app.include_router(teacher_profile.router)
app.include_router(telegram_linking.router)
app.include_router(teacher_communication_settings.router)
app.include_router(teacher_automation_rules.router)
app.include_router(session_summary_ui.router)
app.include_router(session_summary_api.router)
app.include_router(tokens.router)


@app.get('/')
def health():
    return {'app': settings.app_name, 'status': 'ok'}


@app.get('/health')
def healthcheck():
    return {'status': 'ok'}


_frontend_dist = Path('frontend') / 'dist'
if _frontend_dist.exists():
    app.mount('/', StaticFiles(directory=str(_frontend_dist), html=True), name='frontend')
