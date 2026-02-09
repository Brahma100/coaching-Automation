from datetime import date
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, Batch, ClassSession, Student
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.post_class_pipeline import run_post_class_pipeline


def get_attendance_for_batch_today(db: Session, batch_id: int, target_date: date):
    student_ids = list_active_student_ids_for_batch(db, batch_id)
    students = db.query(Student).filter(Student.id.in_(student_ids)).all() if student_ids else []
    records = db.query(AttendanceRecord).join(Student).filter(
        and_(AttendanceRecord.student_id.in_(student_ids), AttendanceRecord.attendance_date == target_date)
    ).all()
    by_student = {r.student_id: r for r in records}

    result = []
    for student in students:
        rec = by_student.get(student.id)
        result.append({
            'student_id': student.id,
            'student_name': student.name,
            'status': rec.status if rec else 'Unmarked',
            'comment': rec.comment if rec else '',
        })
    return result


def submit_attendance(
    db: Session,
    batch_id: int,
    attendance_date: date,
    records: list[dict],
    subject: str = 'General',
    teacher_id: int = 0,
    scheduled_start=None,
    topic_planned: str = '',
    topic_completed: str = '',
    class_session_id: int | None = None,
):
    if class_session_id:
        session_row = db.query(ClassSession).filter(ClassSession.id == class_session_id).first()
        if not session_row:
            raise ValueError('Class session not found')
        if session_row.status in ('closed', 'missed'):
            raise ValueError('Attendance window closed for this class.')

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    created = []
    for item in records:
        existing = db.query(AttendanceRecord).filter(
            AttendanceRecord.student_id == item['student_id'],
            AttendanceRecord.attendance_date == attendance_date,
        ).first()
        if existing:
            existing.status = item['status']
            existing.comment = item.get('comment', '')
            rec = existing
        else:
            rec = AttendanceRecord(
                student_id=item['student_id'],
                attendance_date=attendance_date,
                status=item['status'],
                comment=item.get('comment', ''),
            )
            db.add(rec)
        created.append(rec)
    db.commit()

    pipeline_result = run_post_class_pipeline(
        db=db,
        batch_id=batch_id,
        attendance_date=attendance_date,
        records=created,
        subject=subject,
        teacher_id=teacher_id,
        scheduled_start=scheduled_start,
        topic_planned=topic_planned,
        topic_completed=topic_completed,
    )

    return {'updated_records': len(created), **pipeline_result}
