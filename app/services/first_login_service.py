from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, AuthUser, Batch, Center, Student


def _checklist(batch_count: int, student_count: int, attendance_count: int) -> list[dict]:
    return [
        {
            'key': 'create_batch',
            'label': 'Create your first batch',
            'completed': batch_count > 0,
        },
        {
            'key': 'import_students',
            'label': 'Add or import students',
            'completed': student_count > 0,
        },
        {
            'key': 'take_attendance',
            'label': 'Take first attendance',
            'completed': attendance_count > 0,
        },
    ]


def _next_action(batch_count: int, student_count: int, attendance_count: int) -> str:
    if batch_count <= 0:
        return 'create_batch'
    if student_count <= 0:
        return 'import_students'
    if attendance_count <= 0:
        return 'take_attendance'
    return 'dashboard_ready'


def _progress_percent(items: list[dict]) -> int:
    if not items:
        return 0
    completed = sum(1 for item in items if bool(item.get('completed')))
    return int(round((completed / len(items)) * 100))


def mark_first_login_completed(db: Session, user: AuthUser) -> None:
    if user.first_login_completed:
        return
    user.first_login_completed = True
    db.commit()
    db.refresh(user)


def get_activation_state(db: Session, user: AuthUser) -> dict:
    center_id = int(user.center_id or 0)
    center_name = ''
    if center_id > 0:
        center = db.query(Center).filter(Center.id == center_id).first()
        center_name = str(center.name or '') if center else ''

    batch_count = (
        db.query(func.count(Batch.id))
        .filter(Batch.center_id == center_id, Batch.active.is_(True))
        .scalar()
        or 0
    )
    student_count = db.query(func.count(Student.id)).filter(Student.center_id == center_id).scalar() or 0
    attendance_count = (
        db.query(func.count(AttendanceRecord.id))
        .join(Student, Student.id == AttendanceRecord.student_id)
        .filter(Student.center_id == center_id)
        .scalar()
        or 0
    )

    checklist_items = _checklist(int(batch_count), int(student_count), int(attendance_count))
    next_action = _next_action(int(batch_count), int(student_count), int(attendance_count))
    progress_percent = _progress_percent(checklist_items)

    if not bool(user.first_login_completed) and next_action != 'create_batch':
        # First meaningful action happened once any initial setup item is completed.
        mark_first_login_completed(db, user)

    return {
        'center_name': center_name,
        'first_login_completed': bool(user.first_login_completed),
        'progress_percent': progress_percent,
        'next_action': next_action,
        'checklist_items': checklist_items,
    }
