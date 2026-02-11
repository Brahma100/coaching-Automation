from __future__ import annotations

import time
from datetime import datetime, time as day_time

from app.db import SessionLocal
from app.models import AttendanceRecord, Batch, ClassSession, PendingAction, Student


def time_query(label: str, fn, runs: int = 3) -> None:
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - started) * 1000.0)
    avg_ms = sum(timings) / len(timings) if timings else 0.0
    print(f"{label}: avg_ms={avg_ms:.2f} runs={runs} samples={[round(x, 2) for x in timings]}")


def main() -> None:
    db = SessionLocal()
    try:
        teacher_id = (
            db.query(PendingAction.teacher_id)
            .filter(PendingAction.teacher_id.is_not(None))
            .order_by(PendingAction.teacher_id.asc())
            .limit(1)
            .scalar()
        )
        batch_id = db.query(Batch.id).order_by(Batch.id.asc()).limit(1).scalar()
        student_id = db.query(Student.id).order_by(Student.id.asc()).limit(1).scalar()
        attendance_sample = (
            db.query(AttendanceRecord.student_id, AttendanceRecord.attendance_date)
            .order_by(AttendanceRecord.attendance_date.desc())
            .limit(1)
            .first()
        )

        if teacher_id is not None:
            time_query(
                "pending_actions_status_teacher_due",
                lambda: db.query(PendingAction)
                .filter(
                    PendingAction.status == 'open',
                    PendingAction.teacher_id == teacher_id,
                    PendingAction.due_at.is_not(None),
                )
                .order_by(PendingAction.due_at.asc())
                .all(),
            )

            time_query(
                "pending_actions_teacher_status",
                lambda: db.query(PendingAction)
                .filter(PendingAction.teacher_id == teacher_id, PendingAction.status == 'open')
                .order_by(PendingAction.created_at.desc())
                .all(),
            )

        if batch_id is not None:
            time_query(
                "students_by_batch",
                lambda: db.query(Student).filter(Student.batch_id == batch_id).all(),
            )

            today = datetime.utcnow().date()
            day_start = datetime.combine(today, day_time.min)
            day_end = datetime.combine(today, day_time.max)
            time_query(
                "class_sessions_by_batch_date",
                lambda: db.query(ClassSession)
                .filter(
                    ClassSession.batch_id == batch_id,
                    ClassSession.scheduled_start >= day_start,
                    ClassSession.scheduled_start <= day_end,
                )
                .all(),
            )

        if attendance_sample:
            sid, attendance_date = attendance_sample
            time_query(
                "attendance_by_student_date",
                lambda: db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == sid,
                    AttendanceRecord.attendance_date == attendance_date,
                )
                .all(),
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
