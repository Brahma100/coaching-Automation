from sqlalchemy.orm import Session

from app.models import Homework, HomeworkSubmission


def create_homework(db: Session, payload: dict):
    hw = Homework(**payload)
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return hw


def list_homework(db: Session):
    return db.query(Homework).order_by(Homework.created_at.desc()).all()


def submit_homework(db: Session, payload: dict):
    submission = HomeworkSubmission(**payload)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(db: Session, homework_id: int):
    return db.query(HomeworkSubmission).filter(HomeworkSubmission.homework_id == homework_id).all()
