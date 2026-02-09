from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
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
from app.services.fee_service import build_upi_link
from app.services.parent_service import create_parent, link_parent_student
from app.services.auth_service import validate_session_token
from app.services.batch_membership_service import ensure_active_student_batch_mapping


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
    student = Student(
        name=name.strip(),
        guardian_phone=phone.strip(),
        batch_id=batch_id,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    ensure_active_student_batch_mapping(db, student_id=student.id, batch_id=batch_id)

    if parent_phone.strip():
        parent = db.query(Parent).filter(Parent.phone == parent_phone.strip()).first()
        if not parent:
            parent = create_parent(
                db,
                name=f'{student.name} Guardian',
                phone=parent_phone.strip(),
            )
        link_parent_student(db, parent_id=parent.id, student_id=student.id, relation='guardian')

    due_date = date.today() + timedelta(days=30)
    fee = FeeRecord(
        student_id=student.id,
        due_date=due_date,
        amount=DEFAULT_INITIAL_FEE_AMOUNT,
        paid_amount=0,
        is_paid=False,
    )
    fee.upi_link = build_upi_link(student, fee.amount)
    db.add(fee)

    attendance = AttendanceRecord(
        student_id=student.id,
        attendance_date=date.today(),
        status='Present',
        comment='Auto-created during onboarding',
    )
    db.add(attendance)
    db.commit()

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
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')

    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail='Batch not found')

    student.name = payload.name.strip()
    student.guardian_phone = payload.phone.strip()
    student.batch_id = payload.batch_id
    db.commit()
    db.refresh(student)
    ensure_active_student_batch_mapping(db, student_id=student.id, batch_id=payload.batch_id)

    if payload.parent_phone.strip():
        parent = db.query(Parent).filter(Parent.phone == payload.parent_phone.strip()).first()
        if not parent:
            parent = create_parent(
                db,
                name=f'{student.name} Guardian',
                phone=payload.parent_phone.strip(),
            )
        link_parent_student(db, parent_id=parent.id, student_id=student.id, relation='guardian')

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
