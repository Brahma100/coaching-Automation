from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.jobs.runtime import run_job
from app.frontend_routes import attendance_session_url
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Batch, BatchSchedule, ClassSession, Role
from app.services.action_token_service import create_action_token
from app.services.class_session_resolver import resolve_or_create_class_session
from app.services.comms_service import queue_teacher_telegram
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id


def execute(*, time_provider: TimeProvider = default_time_provider) -> None:
    def _job(db: Session, center_id: int):
        today = time_provider.today()
        weekday = today.weekday()
        schedules = (
            db.query(BatchSchedule, Batch)
            .join(Batch, Batch.id == BatchSchedule.batch_id)
            .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True), Batch.center_id == center_id)
            .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
            .all()
        )
        if not schedules:
            return

        resolved_sessions: dict[int, int] = {}
        for schedule, batch in schedules:
            session, _ = resolve_or_create_class_session(
                db=db,
                batch_id=batch.id,
                schedule_id=schedule.id,
                target_date=today,
                source='telegram',
                teacher_id=0,
            )
            resolved_sessions[schedule.id] = session.id

        teachers = (
            db.query(AllowedUser)
            .filter(
                AllowedUser.role == Role.TEACHER.value,
                AllowedUser.status == AllowedUserStatus.ACTIVE.value,
            )
            .all()
        )
        for teacher in teachers:
            chat_id = resolve_teacher_chat_id(db, teacher.phone)
            if not chat_id:
                continue
            auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone, AuthUser.center_id == center_id).first()
            if not auth_user or int(auth_user.center_id or 0) != center_id:
                continue
            teacher_id = auth_user.id if auth_user else 0

            lines = ['Attendance links for today:']
            for schedule, batch in schedules:
                session_id = resolved_sessions.get(schedule.id)
                if not session_id:
                    continue
                session = db.query(ClassSession).filter(ClassSession.id == session_id, ClassSession.center_id == center_id).first()
                if not session:
                    continue
                end_time = session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)
                ttl_minutes = int(max(1, (end_time + timedelta(minutes=10) - time_provider.now().replace(tzinfo=None)).total_seconds() // 60))
                token = create_action_token(
                    db=db,
                    action_type='attendance_open',
                    payload={
                        'session_id': session_id,
                        'batch_id': batch.id,
                        'schedule_id': schedule.id,
                        'teacher_id': teacher_id,
                        'role': 'teacher',
                    },
                    ttl_minutes=ttl_minutes,
                )
                url = attendance_session_url(session_id, token['token'])
                lines.append(f"- {batch.name} at {schedule.start_time}: {url}")

            queue_teacher_telegram(
                db,
                teacher_id=int(teacher_id),
                chat_id=chat_id,
                message='\n'.join(lines),
                critical=True,
                notification_type='teacher_attendance_links',
                session_id=None,
            )

    run_job('teacher_attendance_links', _job)
