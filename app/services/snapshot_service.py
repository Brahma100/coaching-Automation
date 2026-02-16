from __future__ import annotations

import json
import logging
from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import (
    AdminOpsSnapshot,
    ClassSession,
    Student,
    StudentBatchMap,
    StudentDashboardSnapshot,
    TeacherTodaySnapshot,
)
from app.services.admin_ops_dashboard_service import get_admin_ops_dashboard
from app.services.dashboard_today_service import get_today_view
from app.services.student_portal_service import get_student_dashboard
from app.metrics import timed_snapshot
from app.services.center_scope_service import get_current_center_id


logger = logging.getLogger(__name__)


def _utc_today() -> date:
    return default_time_provider.today()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, default=str)


def _json_loads(raw: str) -> Any:
    return json.loads(raw)


def get_teacher_today_snapshot(db: Session, *, teacher_id: int, day: date) -> dict | None:
    row = (
        db.query(TeacherTodaySnapshot)
        .filter(TeacherTodaySnapshot.teacher_id == teacher_id, TeacherTodaySnapshot.date == day)
        .first()
    )
    if not row:
        return None
    try:
        return _json_loads(row.data_json)
    except Exception:
        logger.exception('snapshot_load_failed teacher_today teacher_id=%s day=%s', teacher_id, day)
        return None


def upsert_teacher_today_snapshot(
    db: Session,
    *,
    teacher_id: int,
    day: date,
    payload: dict,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    row = (
        db.query(TeacherTodaySnapshot)
        .filter(TeacherTodaySnapshot.teacher_id == teacher_id, TeacherTodaySnapshot.date == day)
        .first()
    )
    if row:
        row.data_json = _json_dumps(payload)
        row.updated_at = time_provider.now().replace(tzinfo=None)
    else:
        db.add(
            TeacherTodaySnapshot(
                teacher_id=teacher_id,
                date=day,
                data_json=_json_dumps(payload),
                updated_at=time_provider.now().replace(tzinfo=None),
            )
        )
    db.commit()


def get_admin_ops_snapshot(db: Session, *, day: date, center_id: int | None = None) -> dict | None:
    resolved_center_id = int(center_id or get_current_center_id() or 1)
    row = (
        db.query(AdminOpsSnapshot)
        .filter(AdminOpsSnapshot.center_id == resolved_center_id, AdminOpsSnapshot.date == day)
        .first()
    )
    if not row:
        return None
    try:
        return _json_loads(row.data_json)
    except Exception:
        logger.exception('snapshot_load_failed admin_ops day=%s', day)
        return None


def upsert_admin_ops_snapshot(
    db: Session,
    *,
    day: date,
    payload: dict,
    center_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    resolved_center_id = int(center_id or get_current_center_id() or 1)
    row = (
        db.query(AdminOpsSnapshot)
        .filter(AdminOpsSnapshot.center_id == resolved_center_id, AdminOpsSnapshot.date == day)
        .first()
    )
    if row:
        row.data_json = _json_dumps(payload)
        row.updated_at = time_provider.now().replace(tzinfo=None)
    else:
        db.add(
            AdminOpsSnapshot(
                center_id=resolved_center_id,
                date=day,
                data_json=_json_dumps(payload),
                updated_at=time_provider.now().replace(tzinfo=None),
            )
        )
    db.commit()


def get_student_dashboard_snapshot(db: Session, *, student_id: int, day: date) -> dict | None:
    row = (
        db.query(StudentDashboardSnapshot)
        .filter(StudentDashboardSnapshot.student_id == student_id, StudentDashboardSnapshot.date == day)
        .first()
    )
    if not row:
        return None
    try:
        return _json_loads(row.data_json)
    except Exception:
        logger.exception('snapshot_load_failed student_dashboard student_id=%s day=%s', student_id, day)
        return None


def upsert_student_dashboard_snapshot(
    db: Session,
    *,
    student_id: int,
    day: date,
    payload: dict,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    row = (
        db.query(StudentDashboardSnapshot)
        .filter(StudentDashboardSnapshot.student_id == student_id, StudentDashboardSnapshot.date == day)
        .first()
    )
    if row:
        row.data_json = _json_dumps(payload)
        row.updated_at = time_provider.now().replace(tzinfo=None)
    else:
        db.add(
            StudentDashboardSnapshot(
                student_id=student_id,
                date=day,
                data_json=_json_dumps(payload),
                updated_at=time_provider.now().replace(tzinfo=None),
            )
        )
    db.commit()


@timed_snapshot('snapshot_teacher_today')
def refresh_teacher_today_snapshot(db: Session, *, teacher_id: int, day: date | None = None) -> None:
    if teacher_id is None:
        return
    teacher_id = int(teacher_id or 0)
    day = day or _utc_today()
    try:
        payload = get_today_view(
            db,
            actor={'user_id': teacher_id, 'role': 'teacher'},
            time_provider=default_time_provider,
        )
        upsert_teacher_today_snapshot(
            db,
            teacher_id=teacher_id,
            day=day,
            payload=payload,
            time_provider=default_time_provider,
        )
    except Exception:
        logger.exception('snapshot_refresh_failed teacher_today teacher_id=%s', teacher_id)


@timed_snapshot('snapshot_admin_ops')
def refresh_admin_ops_snapshot(db: Session, *, day: date | None = None) -> None:
    day = day or _utc_today()
    try:
        center_id = int(get_current_center_id() or 0)
        if center_id <= 0:
            logger.warning('center_filter_missing service=snapshot_service query=refresh_admin_ops_snapshot')
            return
        payload = get_admin_ops_dashboard(db, center_id=center_id, time_provider=default_time_provider)
        upsert_admin_ops_snapshot(db, day=day, payload=payload, center_id=center_id, time_provider=default_time_provider)
    except Exception:
        logger.exception('snapshot_refresh_failed admin_ops')


@timed_snapshot('snapshot_student_dashboard')
def refresh_student_dashboard_snapshot(db: Session, *, student_id: int, day: date | None = None) -> None:
    student_id = int(student_id or 0)
    if student_id <= 0:
        return
    day = day or _utc_today()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return
        payload = get_student_dashboard(db, student, time_provider=default_time_provider)
        upsert_student_dashboard_snapshot(
            db,
            student_id=student_id,
            day=day,
            payload=payload,
            time_provider=default_time_provider,
        )
    except Exception:
        logger.exception('snapshot_refresh_failed student_dashboard student_id=%s', student_id)


@timed_snapshot('snapshot_student_dashboard_bulk')
def refresh_student_dashboards_for_day(db: Session, *, day: date | None = None, only_existing: bool = True) -> None:
    day = day or _utc_today()
    try:
        if only_existing:
            ids = [row.student_id for row in db.query(StudentDashboardSnapshot.student_id).filter(StudentDashboardSnapshot.date == day).all()]
        else:
            ids = [row.id for row in db.query(Student.id).all()]
        for student_id in ids:
            refresh_student_dashboard_snapshot(db, student_id=student_id, day=day)
    except Exception:
        logger.exception('snapshot_refresh_failed student_dashboard_bulk')


def teacher_ids_for_student_today(db: Session, *, student_id: int, day: date | None = None) -> set[int]:
    day = day or _utc_today()
    student_id = int(student_id or 0)
    if student_id <= 0:
        return set()

    batch_ids = {
        batch_id
        for (batch_id,) in (
            db.query(StudentBatchMap.batch_id)
            .filter(StudentBatchMap.student_id == student_id, StudentBatchMap.active.is_(True))
            .all()
        )
        if batch_id
    }
    if not batch_ids:
        student = db.query(Student).filter(Student.id == student_id).first()
        if student and student.batch_id:
            batch_ids.add(student.batch_id)
    if not batch_ids:
        return set()

    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)
    rows = (
        db.query(ClassSession.teacher_id)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.teacher_id.is_not(None),
        )
        .distinct()
        .all()
    )
    return {int(teacher_id) for (teacher_id,) in rows if teacher_id}
