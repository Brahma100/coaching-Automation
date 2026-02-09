from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Batch, Student, StudentBatchMap


def list_active_student_ids_for_batch(db: Session, batch_id: int) -> list[int]:
    mapped_ids = [
        student_id
        for (student_id,) in (
            db.query(StudentBatchMap.student_id)
            .filter(
                StudentBatchMap.batch_id == batch_id,
                StudentBatchMap.active.is_(True),
            )
            .distinct()
            .all()
        )
    ]
    if mapped_ids:
        return mapped_ids

    # Backward compatibility for legacy data before mapping table.
    legacy_ids = [student_id for (student_id,) in db.query(Student.id).filter(Student.batch_id == batch_id).all()]
    return legacy_ids


def ensure_active_student_batch_mapping(db: Session, student_id: int, batch_id: int) -> StudentBatchMap:
    row = (
        db.query(StudentBatchMap)
        .filter(
            StudentBatchMap.student_id == student_id,
            StudentBatchMap.batch_id == batch_id,
            StudentBatchMap.active.is_(True),
        )
        .first()
    )
    if row:
        return row

    row = (
        db.query(StudentBatchMap)
        .filter(
            StudentBatchMap.student_id == student_id,
            StudentBatchMap.batch_id == batch_id,
            StudentBatchMap.active.is_(False),
        )
        .order_by(StudentBatchMap.id.desc())
        .first()
    )
    if row:
        row.active = True
        db.commit()
        db.refresh(row)
        return row

    row = StudentBatchMap(student_id=student_id, batch_id=batch_id, active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def deactivate_student_batch_mapping(db: Session, student_id: int, batch_id: int) -> StudentBatchMap | None:
    row = (
        db.query(StudentBatchMap)
        .filter(
            StudentBatchMap.student_id == student_id,
            StudentBatchMap.batch_id == batch_id,
            StudentBatchMap.active.is_(True),
        )
        .first()
    )
    if not row:
        return None
    row.active = False
    db.commit()
    db.refresh(row)
    return row


def list_active_batches_for_student(db: Session, student_id: int) -> list[Batch]:
    mapped_batch_ids = [
        batch_id
        for (batch_id,) in (
            db.query(StudentBatchMap.batch_id)
            .filter(
                StudentBatchMap.student_id == student_id,
                StudentBatchMap.active.is_(True),
            )
            .distinct()
            .all()
        )
    ]
    if mapped_batch_ids:
        return db.query(Batch).filter(Batch.id.in_(mapped_batch_ids)).order_by(Batch.name.asc()).all()

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return []
    fallback = db.query(Batch).filter(Batch.id == student.batch_id).first()
    return [fallback] if fallback else []
