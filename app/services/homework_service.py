from sqlalchemy.orm import Session

from app.models import Homework, HomeworkSubmission
from app.services.student_automation_engine import send_homework_assigned
from app.services import snapshot_service


def create_homework(db: Session, payload: dict):
    hw = Homework(**payload)
    db.add(hw)
    db.commit()
    db.refresh(hw)
    try:
        send_homework_assigned(db, hw)
    except Exception:
        pass

    # CQRS-lite snapshots: homework counts affect student dashboards; refresh today's existing snapshots.
    try:
        snapshot_service.refresh_admin_ops_snapshot(db)
        snapshot_service.refresh_student_dashboards_for_day(db, only_existing=True)
    except Exception:
        pass
    return hw


def list_homework(db: Session):
    return db.query(Homework).order_by(Homework.created_at.desc()).all()


def submit_homework(db: Session, payload: dict):
    submission = HomeworkSubmission(**payload)
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        snapshot_service.refresh_student_dashboard_snapshot(db, student_id=int(submission.student_id))
        snapshot_service.refresh_admin_ops_snapshot(db)
    except Exception:
        pass
    return submission


def list_submissions(db: Session, homework_id: int):
    return db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == homework_id).all()
