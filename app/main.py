from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import actions, admin_allowlist, allowlist_admin, allowlist_admin_ui, attendance, attendance_manage_ui, attendance_session_api, attendance_session_ui, auth, batches_ui, class_session, communications, dashboard, fee, homework, offers, parents, referral, rules, student_api, student_risk, student_ui, students_ui, teacher_brief, ui
from app.scheduler import start_scheduler, stop_scheduler
from app.session_middleware import SessionAuthMiddleware
from app.services.bootstrap_service import run_bootstrap

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
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, version='0.1.0', lifespan=lifespan)
app.mount('/ui-static', StaticFiles(directory='app/ui/static'), name='ui-static')
app.add_middleware(SessionAuthMiddleware)

app.include_router(attendance.router)
app.include_router(fee.router)
app.include_router(dashboard.router)
app.include_router(referral.router)
app.include_router(homework.router)
app.include_router(communications.router)
app.include_router(class_session.router)
app.include_router(parents.router)
app.include_router(actions.router)
app.include_router(offers.router)
app.include_router(rules.router)
app.include_router(ui.router)
app.include_router(attendance_manage_ui.router)
app.include_router(attendance_session_api.router)
app.include_router(attendance_session_ui.router)
app.include_router(auth.router)
app.include_router(students_ui.router)
app.include_router(batches_ui.router)
app.include_router(student_risk.router)
app.include_router(admin_allowlist.router)
app.include_router(allowlist_admin.router)
app.include_router(allowlist_admin_ui.router)
app.include_router(student_api.router)
app.include_router(student_ui.router)
app.include_router(teacher_brief.router)


@app.get('/')
def health():
    return {'app': settings.app_name, 'status': 'ok'}
