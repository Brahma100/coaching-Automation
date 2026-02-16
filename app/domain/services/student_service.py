from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import default_time_provider
from app.models import AttendanceRecord, Batch, FeeRecord, Parent, Student
from app.services.batch_membership_service import ensure_active_student_batch_mapping
from app.services.fee_service import build_upi_link
from app.services.parent_service import create_parent, link_parent_student


def create_student(
    db: Session,
    *,
    name: str,
    phone: str,
    batch_id: int,
    parent_phone: str = '',
    default_initial_fee_amount: float = 2500.0,
) -> tuple[Student, Batch | None]:
    student = Student(
        name=name.strip(),
        guardian_phone=phone.strip(),
        batch_id=batch_id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    ensure_active_student_batch_mapping(db, student_id=student.id, batch_id=batch_id)

    if parent_phone.strip():
        parent = (
            db.query(Parent)
            .filter(
                Parent.phone == parent_phone.strip(),
                Parent.center_id == int(student.center_id or 1),
            )
            .first()
        )
        if not parent:
            parent = create_parent(
                db,
                name=f'{student.name} Guardian',
                phone=parent_phone.strip(),
                center_id=int(student.center_id or 1),
            )
        link_parent_student(db, parent_id=parent.id, student_id=student.id, relation='guardian')

    due_date = default_time_provider.today() + timedelta(days=30)
    fee = FeeRecord(
        student_id=student.id,
        due_date=due_date,
        amount=default_initial_fee_amount,
        paid_amount=0,
        is_paid=False,
    )
    fee.upi_link = build_upi_link(student, fee.amount)
    db.add(fee)

    attendance = AttendanceRecord(
        student_id=student.id,
        attendance_date=default_time_provider.today(),
        status='Present',
        comment='Auto-created during onboarding',
    )
    db.add(attendance)
    db.commit()
    db.refresh(student)
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    return student, batch


def update_student(
    db: Session,
    *,
    student_id: int,
    name: str,
    phone: str,
    batch_id: int,
    parent_phone: str = '',
) -> tuple[Student, Batch, str, str, str]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError('Student not found')

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    old_name = str(student.name or '')
    old_phone = str(student.guardian_phone or '')
    old_batch_name = student.batch.name if student.batch else ''

    student.name = name.strip()
    student.guardian_phone = phone.strip()
    student.batch_id = batch_id
    db.commit()
    db.refresh(student)
    ensure_active_student_batch_mapping(db, student_id=student.id, batch_id=batch_id)

    if parent_phone.strip():
        parent = (
            db.query(Parent)
            .filter(
                Parent.phone == parent_phone.strip(),
                Parent.center_id == int(student.center_id or 1),
            )
            .first()
        )
        if not parent:
            parent = create_parent(
                db,
                name=f'{student.name} Guardian',
                phone=parent_phone.strip(),
                center_id=int(student.center_id or 1),
            )
        link_parent_student(db, parent_id=parent.id, student_id=student.id, relation='guardian')

    return student, batch, old_name, old_phone, old_batch_name
