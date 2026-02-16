from datetime import date

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, Parent, ParentStudentMap, Student
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.comms_service import queue_telegram_by_chat_id


def create_parent(
    db: Session,
    name: str,
    phone: str = '',
    telegram_chat_id: str = '',
    *,
    center_id: int | None,
):
    if center_id is None:
        raise ValueError('center_id is required')
    row = Parent(name=name, phone=phone, telegram_chat_id=telegram_chat_id, center_id=int(center_id))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def link_parent_student(db: Session, parent_id: int, student_id: int, relation: str = 'guardian'):
    parent = db.query(Parent).filter(Parent.id == parent_id).first()
    if not parent:
        raise ValueError('Parent not found')
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError('Student not found')
    if int(parent.center_id or 0) != int(student.center_id or 0):
        raise ValueError('Parent and student must belong to the same center')

    existing = db.query(ParentStudentMap).filter(
        ParentStudentMap.parent_id == parent_id,
        ParentStudentMap.student_id == student_id,
    ).first()
    if existing:
        return existing

    row = ParentStudentMap(parent_id=parent_id, student_id=student_id, relation=relation)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_parents_for_student(db: Session, student_id: int):
    links = db.query(ParentStudentMap).filter(ParentStudentMap.student_id == student_id).all()
    parent_ids = [l.parent_id for l in links]
    if not parent_ids:
        return []
    return db.query(Parent).filter(Parent.id.in_(parent_ids)).all()


def notify_parents_for_absence(db: Session, absent_student_ids: list[int], attendance_date: date):
    for student_id in absent_student_ids:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            continue
        for parent in get_parents_for_student(db, student_id):
            if not parent.telegram_chat_id:
                continue
            message = f"Absence alert: {student.name} was marked absent on {attendance_date}."
            queue_telegram_by_chat_id(db, parent.telegram_chat_id, message, student_id=student.id)


def notify_parents_for_unpaid_fees(db: Session, student_ids: list[int]):
    for student_id in student_ids:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            continue
        for parent in get_parents_for_student(db, student_id):
            if not parent.telegram_chat_id:
                continue
            message = f"Fee alert: Pending fees found for {student.name}. Please clear dues."
            queue_telegram_by_chat_id(db, parent.telegram_chat_id, message, student_id=student.id)


def notify_parents_for_low_attendance_streak(db: Session, batch_id: int, streak_threshold: int = 3):
    student_ids = list_active_student_ids_for_batch(db, batch_id)
    students = db.query(Student).filter(Student.id.in_(student_ids)).all() if student_ids else []
    for student in students:
        latest = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student.id).order_by(AttendanceRecord.attendance_date.desc()).limit(streak_threshold).all()
        if len(latest) < streak_threshold:
            continue
        if all(x.status in ('Absent', 'Late') for x in latest):
            for parent in get_parents_for_student(db, student.id):
                if not parent.telegram_chat_id:
                    continue
                message = f"Low attendance streak: {student.name} has {streak_threshold} consecutive weak attendance records."
                queue_telegram_by_chat_id(db, parent.telegram_chat_id, message, student_id=student.id)


def parent_notifications_from_rules(
    db: Session,
    batch_id: int,
    attendance_date: date,
    absent_ids: list[int],
    unpaid_present_ids: list[int],
    rules: dict | None = None,
):
    # Explicit automation rules only, centralized here.
    cfg = rules or {}
    if absent_ids and cfg.get('notify_parent_on_absence', True):
        notify_parents_for_absence(db, absent_ids, attendance_date)
    if unpaid_present_ids and cfg.get('notify_parent_on_fee_due', True):
        notify_parents_for_unpaid_fees(db, unpaid_present_ids)
    notify_parents_for_low_attendance_streak(
        db,
        batch_id=batch_id,
        streak_threshold=cfg.get('absence_streak_threshold', 3),
    )
