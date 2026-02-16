from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.time_provider import default_time_provider
from app.models import AutomationFailureLog, AuthUser, ClassSession, CommunicationLog, Student
from app.services.observability_counters import count_observability_events


def _scoped_communication_query(db: Session, center_id: int | None):
    query = (
        db.query(CommunicationLog)
        .outerjoin(AuthUser, AuthUser.id == CommunicationLog.teacher_id)
        .outerjoin(Student, Student.id == CommunicationLog.student_id)
        .outerjoin(ClassSession, ClassSession.id == CommunicationLog.session_id)
    )
    if center_id is None:
        return query
    scoped_center = int(center_id)
    return query.filter(
        or_(
            AuthUser.center_id == scoped_center,
            Student.center_id == scoped_center,
            ClassSession.center_id == scoped_center,
        )
    )


def _classify_health(payload: dict) -> str:
    permanently_failed = int(payload.get('permanently_failed_communications') or 0)
    post_class_error_sessions = int(payload.get('post_class_error_sessions') or 0)
    dead_letter_count = int(payload.get('dead_letter_count') or 0)
    retry_backlog_count = int(payload.get('retry_backlog_count') or 0)

    if permanently_failed > 50 or dead_letter_count > 100:
        return 'critical'
    if permanently_failed > 10 or post_class_error_sessions > 0 or retry_backlog_count > 20:
        return 'degraded'
    return 'healthy'


def get_system_health(db: Session, center_id: int | None = None, *, now: datetime | None = None) -> dict:
    current = (now or default_time_provider.now()).replace(tzinfo=None)
    since_24h = current - timedelta(hours=24)
    retry_cutoff = current - timedelta(minutes=5)
    scoped_center_id = int(center_id) if center_id is not None else None

    comms_q = _scoped_communication_query(db, scoped_center_id)

    failed_communications_last_24h = int(
        comms_q.filter(
            CommunicationLog.delivery_status == 'failed',
            func.coalesce(CommunicationLog.last_attempt_at, CommunicationLog.created_at) >= since_24h,
        ).count()
    )
    permanently_failed_communications = int(
        comms_q.filter(CommunicationLog.delivery_status == 'permanently_failed').count()
    )
    retry_backlog_count = int(
        comms_q.filter(
            CommunicationLog.delivery_status == 'failed',
            CommunicationLog.delivery_attempts < 3,
            or_(
                CommunicationLog.last_attempt_at <= retry_cutoff,
                and_(CommunicationLog.last_attempt_at.is_(None), CommunicationLog.created_at <= retry_cutoff),
            ),
        ).count()
    )

    post_class_q = db.query(ClassSession).filter(ClassSession.post_class_error.is_(True))
    if scoped_center_id is not None:
        post_class_q = post_class_q.filter(ClassSession.center_id == scoped_center_id)
    post_class_error_sessions = int(post_class_q.count())

    failure_q = db.query(AutomationFailureLog)
    if scoped_center_id is not None:
        failure_q = failure_q.filter(AutomationFailureLog.center_id == scoped_center_id)
    automation_failure_count_24h = int(failure_q.filter(AutomationFailureLog.created_at >= since_24h).count())
    dead_letter_count = int(failure_q.count())

    payload = {
        'failed_communications_last_24h': failed_communications_last_24h,
        'permanently_failed_communications': permanently_failed_communications,
        'post_class_error_sessions': post_class_error_sessions,
        'automation_failure_count_24h': automation_failure_count_24h,
        'retry_backlog_count': retry_backlog_count,
        'dead_letter_count': dead_letter_count,
        'cache_center_mismatch_count_last_24h': count_observability_events(
            'cache_center_mismatch',
            window_hours=24,
            now=current,
        ),
        'job_lock_skipped_count_last_24h': count_observability_events(
            'job_lock_skipped',
            window_hours=24,
            now=current,
        ),
        'rate_limit_blocks_last_24h': count_observability_events(
            'rate_limit_block',
            window_hours=24,
            now=current,
        ),
        'snapshot_drift_last_24h': count_observability_events(
            'snapshot_drift',
            window_hours=24,
            now=current,
        ),
        'snapshot_rebuild_runs_last_24h': count_observability_events(
            'snapshot_rebuild_run',
            window_hours=24,
            now=current,
        ),
    }
    payload['health_status'] = _classify_health(payload)
    return payload
