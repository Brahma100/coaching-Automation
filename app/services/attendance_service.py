from datetime import date, datetime
import logging
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import AttendanceRecord, Batch, ClassSession, Student, TeacherBatchMap
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.center_scope_service import get_current_center_id
from app.services.automation_failure_service import log_automation_failure
from app.services.post_class_pipeline import run_post_class_pipeline
from app.services.post_class_automation_engine import run_post_class_automation

logger = logging.getLogger(__name__)


class SafeConflictError(ValueError):
    pass


def _idempotent_submit_response(
    db: Session,
    *,
    session_row: ClassSession,
    batch_id: int,
    attendance_date: date,
) -> dict:
    student_ids = list_active_student_ids_for_batch(db, batch_id)
    existing_records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.student_id.in_(student_ids), AttendanceRecord.attendance_date == attendance_date)
        .all()
        if student_ids
        else []
    )
    return {
        'updated_records': len(existing_records),
        'class_summary': {
            'class_session_id': session_row.id,
            'present_count': sum(1 for rec in existing_records if rec.status == 'Present'),
            'absent_count': sum(1 for rec in existing_records if rec.status == 'Absent'),
            'late_count': sum(1 for rec in existing_records if rec.status == 'Late'),
            'topic_completed': session_row.topic_completed or '',
            'homework_status_summary': {'present_students_count': 0, 'note': 'idempotent_skip'},
            'unpaid_students_present': [],
        },
        'teacher_notifications': [],
        'student_notifications': len(existing_records),
        'parent_notifications_rules_applied': True,
        'pending_action_ids': [],
        'rules': {},
        'idempotent': True,
    }


def _teacher_can_access_batch(db: Session, *, batch_id: int, actor_role: str, actor_user_id: int) -> bool:
    center_id = int(get_current_center_id() or 0)
    if center_id > 0:
        batch_row = db.query(Batch).filter(Batch.id == int(batch_id), Batch.center_id == center_id).first()
        if not batch_row:
            return False
    if (actor_role or '').strip().lower() != 'teacher':
        return True
    batch_ids = get_teacher_batch_ids(db, int(actor_user_id or 0), center_id=center_id)
    if not batch_ids:
        # Backward compatibility: when teacher-batch mappings are not configured yet,
        # allow submit for sessions explicitly owned by this teacher.
        has_mappings = (
            db.query(TeacherBatchMap.id)
            .filter(
                TeacherBatchMap.teacher_id == int(actor_user_id or 0),
                TeacherBatchMap.center_id == center_id if center_id > 0 else True,
            )
            .first()
            is not None
        )
        if not has_mappings:
            legacy_session = (
                db.query(ClassSession.id)
                .filter(
                    ClassSession.batch_id == int(batch_id),
                    ClassSession.teacher_id == int(actor_user_id or 0),
                    ClassSession.center_id == center_id if center_id > 0 else True,
                )
                .first()
            )
            return legacy_session is not None
        return False
    return int(batch_id) in batch_ids


def get_attendance_for_batch_today(
    db: Session,
    batch_id: int,
    target_date: date,
    *,
    actor_role: str = 'admin',
    actor_user_id: int = 0,
):
    if not _teacher_can_access_batch(db, batch_id=batch_id, actor_role=actor_role, actor_user_id=actor_user_id):
        return []
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
    actor_role: str = 'admin',
    actor_user_id: int = 0,
):
    if not _teacher_can_access_batch(db, batch_id=batch_id, actor_role=actor_role, actor_user_id=actor_user_id):
        raise PermissionError('Unauthorized batch access')
    session_row: ClassSession | None = None
    if class_session_id:
        session_row = (
            db.query(ClassSession)
            .filter(ClassSession.id == class_session_id)
            .with_for_update()
            .first()
        )
        logger.info('attendance_locked', extra={'session_id': int(class_session_id)})
        if not session_row:
            raise ValueError('Class session not found')
        if session_row.status == 'submitted':
            logger.info('attendance_idempotent_skip', extra={'session_id': int(class_session_id)})
            return _idempotent_submit_response(
                db,
                session_row=session_row,
                batch_id=batch_id,
                attendance_date=attendance_date,
            )
        if session_row.status != 'open':
            logger.warning(
                'attendance_conflict_detected',
                extra={'session_id': int(class_session_id), 'status': str(session_row.status)},
            )
            raise SafeConflictError('Attendance window closed for this class.')

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
    db.flush()

    should_run_post_class = True
    if session_row is not None:
        should_run_post_class = session_row.post_class_processed_at is None
        session_row.status = 'submitted'
        session_row.actual_start = session_row.actual_start or datetime.utcnow()
        db.flush()

    pipeline_result = {
        'class_summary': {'class_session_id': int(class_session_id or 0)},
        'teacher_notifications': [],
        'student_notifications': len(created),
        'parent_notifications_rules_applied': False,
        'pending_action_ids': [],
        'rules': {},
    }
    post_class_error = False
    if should_run_post_class:
        try:
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
            session_id = pipeline_result.get('class_summary', {}).get('class_session_id')
            if session_id:
                run_post_class_automation(db, session_id=session_id, trigger_source='manual_submit')
        except Exception as exc:
            post_class_error = True
            logger.error(
                'automation_failure',
                extra={
                    'job': 'post_class_pipeline',
                    'center_id': int(get_current_center_id() or 1),
                    'entity_id': int(class_session_id or 0),
                    'error': str(exc),
                },
            )
            log_automation_failure(
                db,
                job_name='post_class_pipeline',
                entity_type='class_session',
                entity_id=int(class_session_id or 0) or None,
                error_message=str(exc),
            )
    if session_row is not None:
        if should_run_post_class and not post_class_error:
            session_row.post_class_processed_at = datetime.utcnow()
        if post_class_error:
            session_row.post_class_error = True
    elif should_run_post_class:
        processed_session_id = int(pipeline_result.get('class_summary', {}).get('class_session_id') or 0)
        if processed_session_id > 0:
            processed_session = (
                db.query(ClassSession)
                .filter(ClassSession.id == processed_session_id)
                .with_for_update()
                .first()
            )
            if processed_session:
                if processed_session.post_class_processed_at is None and not post_class_error:
                    processed_session.post_class_processed_at = datetime.utcnow()
                if post_class_error:
                    processed_session.post_class_error = True
    db.commit()

    return {'updated_records': len(created), **pipeline_result}
