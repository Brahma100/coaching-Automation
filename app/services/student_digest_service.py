from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AttendanceRecord, Homework, HomeworkSubmission, Student


def build_student_digest(
    db: Session,
    student: Student,
    *,
    center_id: int,
    time_provider: TimeProvider = default_time_provider,
) -> str | None:
    center_id = int(center_id or 0)
    if center_id <= 0 or int(student.center_id or 0) != center_id:
        return None
    today = time_provider.today()
    attendance_rows = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id == student.id,
        AttendanceRecord.attendance_date == today,
    ).all()
    attended_today = sum(1 for row in attendance_rows if row.status == 'Present')

    start_of_day = datetime.combine(today, datetime.min.time())
    homework_today = (
        db.query(Homework)
        .join(HomeworkSubmission, HomeworkSubmission.homework_id == Homework.id)
        .join(Student, Student.id == HomeworkSubmission.student_id)
        .filter(Homework.created_at >= start_of_day, Student.id == student.id, Student.center_id == center_id)
        .distinct()
        .all()
    )
    homework_due_tomorrow = (
        db.query(Homework)
        .join(HomeworkSubmission, HomeworkSubmission.homework_id == Homework.id)
        .join(Student, Student.id == HomeworkSubmission.student_id)
        .filter(Homework.due_date == today + timedelta(days=1), Student.id == student.id, Student.center_id == center_id)
        .distinct()
        .all()
    )
    submitted_ids = {
        row.homework_id
        for row in db.query(HomeworkSubmission.homework_id)
        .filter(HomeworkSubmission.student_id == student.id)
        .all()
    }
    pending_titles = []
    for hw in homework_due_tomorrow:
        if hw.id not in submitted_ids:
            pending_titles.append(hw.title)

    if attended_today == 0 and not pending_titles and not homework_today:
        return None

    lines = [
        "📅 Today’s Summary",
        f"✔ Classes attended: {attended_today}",
    ]
    if pending_titles:
        lines.append(f"📚 Homework pending: {', '.join(pending_titles[:2])}")
    if homework_today:
        lines.append(f"📝 New homework today: {len(homework_today)} item(s)")
    return "\n".join(lines)
