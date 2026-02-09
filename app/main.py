from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import actions, attendance, class_session, communications, dashboard, fee, homework, offers, parents, referral, rules, ui
from app.scheduler import start_scheduler, stop_scheduler
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


@app.get('/')
def health():
    return {'app': settings.app_name, 'status': 'ok'}
