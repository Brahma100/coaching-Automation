from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.services.student_service import create_student as domain_create_student, update_student as domain_update_student
from app.models import (
    AttendanceRecord,
    Batch,
    CommunicationLog,
    FeeRecord,
    HomeworkSubmission,
    OfferRedemption,
    Parent,
    ParentStudentMap,
    PendingAction,
    ReferralCode,
    Student,
    StudentRiskEvent,
    StudentRiskProfile,
    StudentBatchMap,
)
from app.services.auth_service import validate_session_token
from app.services.student_notification_service import notify_student


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(tags=['Students UI'])

DEFAULT_INITIAL_FEE_AMOUNT = 2500.0


class StudentUpdatePayload(BaseModel):
    name: str
    phone: str = ''
    batch_id: int
    parent_phone: str = ''


def _require_teacher(request: Request):
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session or session['role'] not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return session


def _notify_student_profile_change(
    db: Session,
    *,
    student: Student,
    old_name: str,
    old_phone: str,
    old_batch_name: str,
    new_batch_name: str,
) -> None:
    changes: list[str] = []
    if old_name != student.name:
        changes.append(f"Name: {old_name or 'N/A'} -> {student.name or 'N/A'}")
    if old_phone != student.guardian_phone:
        changes.append(f"Phone: {old_phone or 'N/A'} -> {student.guardian_phone or 'N/A'}")
    if old_batch_name != new_batch_name:
        changes.append(f"Batch: {old_batch_name or 'N/A'} -> {new_batch_name or 'N/A'}")
    if not changes:
        return
    message = "Your student profile has been updated:\n" + "\n".join(f"- {item}" for item in changes)
    notify_student(
        db,
        student=student,
        message=message,
        notification_type="student_profile_updated",
        critical=True,
    )


@router.get('/ui/students')
def students_list(request: Request, db: Session = Depends(get_db)):
    batches = {b.id: b.name for b in db.query(Batch).all()}
    rows = db.query(Student).order_by(Student.id.desc()).all()
    return templates.TemplateResponse(
        'students_list.html',
        {
            'request': request,
            'rows': rows,
            'batches': batches,
        },
    )


@router.get('/ui/students/add')
def students_add_page(request: Request, db: Session = Depends(get_db)):
    batches = db.query(Batch).order_by(Batch.name.asc()).all()
    return templates.TemplateResponse(
        'students.html',
        {
            'request': request,
            'batches': batches,
            'default_fee_amount': DEFAULT_INITIAL_FEE_AMOUNT,
        },
    )


@router.post('/students/create')
def students_create(
    request: Request,
    name: str = Form(...),
    phone: str = Form(''),
    batch_id: int = Form(...),
    parent_phone: str = Form(''),
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student, batch = domain_create_student(
        db,
        name=name,
        phone=phone,
        batch_id=batch_id,
        parent_phone=parent_phone,
        default_initial_fee_amount=DEFAULT_INITIAL_FEE_AMOUNT,
    )
    notify_student(
        db,
        student=student,
        message=(
            "Welcome to LearningMate.\n"
            f"Your profile is created.\n"
            f"Name: {student.name}\n"
            f"Batch: {batch.name if batch else student.batch_id}\n"
            f"Phone: {student.guardian_phone or 'N/A'}"
        ),
        notification_type="student_created",
        critical=True,
    )

    return RedirectResponse(url='/ui/students', status_code=303)


@router.get('/students')
def students_list_api(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    rows = db.query(Student).order_by(Student.id.desc()).all()
    parent_links = db.query(ParentStudentMap).all()
    parent_ids = {link.parent_id for link in parent_links}
    parents_by_id = {
        row.id: row
        for row in db.query(Parent).filter(Parent.id.in_(parent_ids)).all()
    } if parent_ids else {}
    parent_phone_by_student = {}
    for link in parent_links:
        if link.student_id not in parent_phone_by_student:
            parent_phone_by_student[link.student_id] = (parents_by_id.get(link.parent_id).phone if parents_by_id.get(link.parent_id) else '')

    return [
        {
            'id': row.id,
            'name': row.name,
            'batch_id': row.batch_id,
            'batch': row.batch.name if row.batch else '',
            'phone': row.guardian_phone,
            'guardian_phone': row.guardian_phone,
            'parent_phone': parent_phone_by_student.get(row.id, ''),
        }
        for row in rows
    ]


@router.put('/students/{student_id}')
def students_update_api(
    student_id: int,
    payload: StudentUpdatePayload,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        student, batch, old_name, old_phone, old_batch_name = domain_update_student(
            db,
            student_id=student_id,
            name=payload.name,
            phone=payload.phone,
            batch_id=payload.batch_id,
            parent_phone=payload.parent_phone,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == 'Student not found':
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail == 'Batch not found':
            raise HTTPException(status_code=404, detail=detail) from exc
        raise

    _notify_student_profile_change(
        db,
        student=student,
        old_name=old_name,
        old_phone=old_phone,
        old_batch_name=old_batch_name,
        new_batch_name=batch.name,
    )

    return {
        'id': student.id,
        'name': student.name,
        'batch_id': student.batch_id,
        'phone': student.guardian_phone,
    }


@router.delete('/students/{student_id}')
def students_delete_api(
    student_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')
    notify_student(
        db,
        student=student,
        message=(
            "Account update\n"
            "Your student profile has been removed from the coaching system.\n"
            "If this is unexpected, please contact admin."
        ),
        notification_type="student_deleted",
        critical=True,
    )

    db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student_id).delete(synchronize_session=False)
    db.query(FeeRecord).filter(FeeRecord.student_id == student_id).delete(synchronize_session=False)
    db.query(HomeworkSubmission).filter(HomeworkSubmission.student_id == student_id).delete(synchronize_session=False)
    db.query(ReferralCode).filter(ReferralCode.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentBatchMap).filter(StudentBatchMap.student_id == student_id).delete(synchronize_session=False)
    db.query(PendingAction).filter(PendingAction.student_id == student_id).delete(synchronize_session=False)
    db.query(ParentStudentMap).filter(ParentStudentMap.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentRiskProfile).filter(StudentRiskProfile.student_id == student_id).delete(synchronize_session=False)
    db.query(StudentRiskEvent).filter(StudentRiskEvent.student_id == student_id).delete(synchronize_session=False)
    db.query(CommunicationLog).filter(CommunicationLog.student_id == student_id).delete(synchronize_session=False)
    db.query(OfferRedemption).filter(OfferRedemption.student_id == student_id).delete(synchronize_session=False)
    db.delete(student)
    db.commit()

    return {'ok': True, 'deleted_student_id': student_id}
