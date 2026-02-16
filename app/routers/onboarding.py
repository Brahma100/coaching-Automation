from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import validate_session_token
from app.services.onboarding_service import (
    check_slug_availability,
    create_admin_user,
    create_center_setup,
    finish_onboarding,
    get_onboarding_state,
    invite_teachers,
    parse_students_csv,
    reserve_slug,
    serialize_state,
    setup_academic_defaults,
    store_imported_students,
)

router = APIRouter(prefix='/api/onboard', tags=['Onboarding'])


class CenterSetupPayload(BaseModel):
    name: str
    city: str = ''
    timezone: str = 'Asia/Kolkata'
    academic_type: str = ''


class ReserveSlugPayload(BaseModel):
    setup_token: str
    slug: str


class AdminSetupPayload(BaseModel):
    setup_token: str
    name: str = ''
    phone: str
    password: str = Field(min_length=8)


class AcademicSetupPayload(BaseModel):
    setup_token: str
    classes: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)


class TeacherInviteItem(BaseModel):
    name: str = ''
    phone: str
    subject: str = ''


class TeacherInvitePayload(BaseModel):
    setup_token: str
    teachers: list[TeacherInviteItem] = Field(default_factory=list)


class FinishPayload(BaseModel):
    setup_token: str


def _session_center_id(request: Request) -> int:
    token = request.cookies.get('auth_session')
    if not token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.lower().startswith('bearer '):
            token = auth_header.split(' ', 1)[1].strip()
    session = validate_session_token(token)
    return int(session.get('center_id') or 0) if session else 0


@router.post('/center')
def onboard_center(payload: CenterSetupPayload, db: Session = Depends(get_db)):
    try:
        row, suggestions = create_center_setup(
            db,
            name=payload.name,
            city=payload.city,
            timezone=payload.timezone,
            academic_type=payload.academic_type,
        )
        return {
            'ok': True,
            'onboarding_id': int(row.id),
            'slug_suggestion': row.temp_slug,
            'suggestions': suggestions,
            'state': serialize_state(row),
            'dev_domain': f"http://{row.temp_slug}.localhost:8000",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/check-slug')
def onboard_check_slug(slug: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    available, reason = check_slug_availability(db, slug)
    base = slug.strip().lower().replace(' ', '-')
    suggestions = [f'{base}-{idx}' for idx in range(2, 5)] if not available else []
    return {'available': bool(available), 'suggestions': suggestions, 'reason': reason}


@router.post('/reserve-slug')
def onboard_reserve_slug(payload: ReserveSlugPayload, request: Request, db: Session = Depends(get_db)):
    try:
        row = reserve_slug(
            db,
            setup_token=payload.setup_token,
            slug=payload.slug,
            actor_center_id=_session_center_id(request),
        )
        return {'ok': True, 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/state')
def onboard_state(request: Request, setup_token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    try:
        row = get_onboarding_state(db, setup_token, actor_center_id=_session_center_id(request))
        return {'ok': True, 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/admin')
def onboard_admin(payload: AdminSetupPayload, request: Request, db: Session = Depends(get_db)):
    try:
        row, token = create_admin_user(
            db,
            setup_token=payload.setup_token,
            name=payload.name,
            phone=payload.phone,
            password=payload.password,
            actor_center_id=_session_center_id(request),
        )
        return {'ok': True, 'session_token': token, 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/academic-setup')
def onboard_academic_setup(payload: AcademicSetupPayload, request: Request, db: Session = Depends(get_db)):
    try:
        row, summary = setup_academic_defaults(
            db,
            setup_token=payload.setup_token,
            classes=payload.classes,
            subjects=payload.subjects,
            actor_center_id=_session_center_id(request),
        )
        return {'ok': True, 'summary': summary, 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/teachers')
def onboard_teachers(payload: TeacherInvitePayload, request: Request, db: Session = Depends(get_db)):
    try:
        row, summary = invite_teachers(
            db,
            setup_token=payload.setup_token,
            teachers=[item.model_dump() for item in payload.teachers],
            actor_center_id=_session_center_id(request),
        )
        return {'ok': True, 'summary': summary, 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/students/import')
async def onboard_students_import(
    request: Request,
    setup_token: str = Form(...),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    try:
        parsed_rows: list[dict] = []
        validation_report: dict = {}
        if file is not None:
            content = await file.read()
            validation_report = parse_students_csv(content)
            parsed_rows = list(validation_report.get('rows') or [])
        row, summary = store_imported_students(
            db,
            setup_token=setup_token,
            parsed_rows=parsed_rows,
            validation_report=validation_report,
            actor_center_id=_session_center_id(request),
        )
        return {
            'ok': True,
            'summary': summary,
            'validation': validation_report,
            'parsed_rows': parsed_rows,
            'state': serialize_state(row),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/finish')
def onboard_finish(payload: FinishPayload, request: Request, db: Session = Depends(get_db)):
    try:
        row = finish_onboarding(db, setup_token=payload.setup_token, actor_center_id=_session_center_id(request))
        return {'ok': True, 'redirect': '/login', 'state': serialize_state(row)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
