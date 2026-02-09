import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import FeeRecord, Student
from app.services.pending_action_service import create_pending_action
from app.services.class_session_service import get_or_create_session_for_attendance
from app.services.comms_service import notify_attendance_status
from app.services.parent_service import parent_notifications_from_rules
from app.services.rule_config_service import get_effective_rule_config


logger = logging.getLogger(__name__)


def _build_homework_status_summary(db: Session, student_ids: list[int]) -> dict:
    # Lightweight summary for automation decisions.
    return {
        'present_students_count': len(student_ids),
        'note': 'Hook detailed homework analytics here based on assignment policy.',
    }


def run_post_class_pipeline(
    db: Session,
    batch_id: int,
    attendance_date: date,
    records: list,
    subject: str,
    teacher_id: int,
    scheduled_start,
    topic_planned: str,
    topic_completed: str,
):
    rules = get_effective_rule_config(db, batch_id=batch_id)
    logger.info('post_class_pipeline_start', extra={'batch_id': batch_id, 'attendance_date': str(attendance_date), 'rules_scope': rules['scope']})

    session = get_or_create_session_for_attendance(
        db=db,
        batch_id=batch_id,
        attendance_date=attendance_date,
        subject=subject,
        teacher_id=teacher_id,
        scheduled_start=scheduled_start,
        topic_planned=topic_planned,
        topic_completed=topic_completed,
    )

    present_ids, absent_ids, late_ids = [], [], []
    for rec in records:
        if rec.status == 'Present':
            present_ids.append(rec.student_id)
        elif rec.status == 'Absent':
            absent_ids.append(rec.student_id)
        elif rec.status == 'Late':
            late_ids.append(rec.student_id)

    unpaid_present_ids = []
    if present_ids:
        pending_fees = db.query(FeeRecord).filter(
            FeeRecord.student_id.in_(present_ids),
            FeeRecord.is_paid.is_(False),
        ).all()
        unpaid_present_ids = sorted({f.student_id for f in pending_fees})

    summary = {
        'class_session_id': session.id,
        'present_count': len(present_ids),
        'absent_count': len(absent_ids),
        'late_count': len(late_ids),
        'topic_completed': topic_completed,
        'homework_status_summary': _build_homework_status_summary(db, present_ids + late_ids),
        'unpaid_students_present': unpaid_present_ids,
    }

    teacher_flags = []
    if summary['absent_count'] > 0:
        teacher_flags.append('absences_detected')
    if summary['late_count'] > 0:
        teacher_flags.append('late_students_detected')
    if summary['unpaid_students_present']:
        teacher_flags.append('unpaid_students_present')
    if summary['absent_count'] >= rules['absence_streak_threshold']:
        teacher_flags.append('high_absence_threshold_reached')

    for rec in records:
        student = db.query(Student).filter(Student.id == rec.student_id).first()
        if student:
            notify_attendance_status(db, student, rec.status, str(attendance_date), rec.comment)

    created_action_ids = []
    for student_id in absent_ids:
        row = create_pending_action(
            db,
            action_type='absence',
            student_id=student_id,
            related_session_id=session.id,
            note=f'Absent on {attendance_date}',
        )
        created_action_ids.append(row.id)

    for student_id in unpaid_present_ids:
        row = create_pending_action(
            db,
            action_type='fee_followup',
            student_id=student_id,
            related_session_id=session.id,
            note='Present with unpaid fees',
        )
        created_action_ids.append(row.id)

    for student_id in late_ids:
        row = create_pending_action(
            db,
            action_type='homework',
            student_id=student_id,
            related_session_id=session.id,
            note='Late attendance; verify homework completion',
        )
        created_action_ids.append(row.id)

    parent_notifications_from_rules(
        db,
        batch_id=batch_id,
        attendance_date=attendance_date,
        absent_ids=absent_ids,
        unpaid_present_ids=unpaid_present_ids,
        rules=rules,
    )

    logger.info(
        'post_class_pipeline_complete',
        extra={
            'class_session_id': session.id,
            'present_count': len(present_ids),
            'absent_count': len(absent_ids),
            'late_count': len(late_ids),
            'pending_actions_created': len(set(created_action_ids)),
        },
    )

    return {
        'class_summary': summary,
        'teacher_notifications': teacher_flags,
        'student_notifications': len(records),
        'parent_notifications_rules_applied': True,
        'pending_action_ids': sorted(set(created_action_ids)),
        'rules': rules,
    }
