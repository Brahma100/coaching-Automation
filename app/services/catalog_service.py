from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Board, ClassLevel, Program, Subject


def _normalize_name(value: str) -> str:
    return (value or '').strip()


def create_program(db: Session, *, name: str, description: str = '') -> Program:
    clean_name = _normalize_name(name)
    if not clean_name:
        raise ValueError('Program name is required')
    exists = db.query(Program).filter(func.lower(Program.name) == clean_name.lower()).first()
    if exists:
        raise ValueError('Program name already exists')
    row = Program(name=clean_name, description=description or '')
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).order_by(Program.name.asc()).all()


def create_board(db: Session, *, name: str, shortcode: str) -> Board:
    clean_name = _normalize_name(name)
    clean_shortcode = (shortcode or '').strip()
    if not clean_name or not clean_shortcode:
        raise ValueError('Board name and shortcode are required')
    exists = (
        db.query(Board)
        .filter(
            (func.lower(Board.name) == clean_name.lower()) | (func.lower(Board.shortcode) == clean_shortcode.lower())
        )
        .first()
    )
    if exists:
        raise ValueError('Board already exists')
    row = Board(name=clean_name, shortcode=clean_shortcode)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_boards(db: Session) -> list[Board]:
    return db.query(Board).order_by(Board.name.asc()).all()


def create_class_level(db: Session, *, name: str, min_grade: int | None = None, max_grade: int | None = None) -> ClassLevel:
    clean_name = _normalize_name(name)
    if not clean_name:
        raise ValueError('Class level name is required')
    exists = db.query(ClassLevel).filter(func.lower(ClassLevel.name) == clean_name.lower()).first()
    if exists:
        raise ValueError('Class level already exists')
    row = ClassLevel(name=clean_name, min_grade=min_grade, max_grade=max_grade)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_class_levels(db: Session) -> list[ClassLevel]:
    return db.query(ClassLevel).order_by(ClassLevel.min_grade.asc().nulls_last(), ClassLevel.name.asc()).all()


def create_subject(db: Session, *, name: str, code: str | None = '') -> Subject:
    clean_name = _normalize_name(name)
    clean_code = (code or '').strip()
    if not clean_name:
        raise ValueError('Subject name is required')
    exists = db.query(Subject).filter(func.lower(Subject.name) == clean_name.lower()).first()
    if exists:
        raise ValueError('Subject name already exists')
    row = Subject(name=clean_name, code=clean_code)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_subjects(db: Session) -> list[Subject]:
    return db.query(Subject).order_by(Subject.name.asc()).all()
