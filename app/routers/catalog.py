from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    BoardCreate,
    BoardRead,
    ClassLevelCreate,
    ClassLevelRead,
    ProgramCreate,
    ProgramRead,
    SubjectCreate,
    SubjectRead,
)
from app.services.auth_service import validate_session_token
from app.services.catalog_service import (
    create_board,
    create_class_level,
    create_program,
    create_subject,
    list_boards,
    list_class_levels,
    list_programs,
    list_subjects,
)

router = APIRouter(prefix='/api', tags=['Catalog'])


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get('auth_session') or request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    session = validate_session_token(token)
    if not session or session.get('role') not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return session


@router.get('/programs', response_model=list[ProgramRead])
def list_programs_api(_: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    return list_programs(db)


@router.post('/programs', response_model=ProgramRead)
def create_program_api(payload: ProgramCreate, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    try:
        return create_program(db, name=payload.name, description=payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/boards', response_model=list[BoardRead])
def list_boards_api(_: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    return list_boards(db)


@router.post('/boards', response_model=BoardRead)
def create_board_api(payload: BoardCreate, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    try:
        return create_board(db, name=payload.name, shortcode=payload.shortcode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/class-levels', response_model=list[ClassLevelRead])
def list_class_levels_api(_: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    return list_class_levels(db)


@router.post('/class-levels', response_model=ClassLevelRead)
def create_class_level_api(payload: ClassLevelCreate, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    try:
        return create_class_level(db, name=payload.name, min_grade=payload.min_grade, max_grade=payload.max_grade)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/subjects', response_model=list[SubjectRead])
def list_subjects_api(_: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    return list_subjects(db)


@router.post('/subjects', response_model=SubjectRead)
def create_subject_api(payload: SubjectCreate, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    try:
        return create_subject(db, name=payload.name, code=payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
