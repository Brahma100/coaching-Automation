from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Student
from app.schemas import AttendanceItem, AttendanceSubmitRequest, HomeworkCreateRequest
from app.services.attendance_service import get_attendance_for_batch_today, submit_attendance
from app.services.fee_service import get_fee_dashboard, mark_fee_paid
from app.services.homework_service import create_homework, list_homework
from app.services.insights_service import generate_insights
from app.services.pending_action_service import list_open_actions, resolve_action
from app.services.referral_service import create_referral_code, list_referrals
from app.services.system_service import get_last_backup, get_sqlite_db_path, run_backup_now


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui', tags=['UI'])


@router.get('/dashboard')
def dashboard(request: Request, db: Session = Depends(get_db)):
    insights = generate_insights(db)
    return templates.TemplateResponse('dashboard.html', {'request': request, 'insights': insights})


@router.get('/attendance/{batch_id}')
def attendance_page(batch_id: int, request: Request, db: Session = Depends(get_db)):
    rows = get_attendance_for_batch_today(db, batch_id, date.today())
    return templates.TemplateResponse('attendance.html', {'request': request, 'rows': rows, 'batch_id': batch_id})


@router.post('/attendance/{batch_id}')
def attendance_submit(
    batch_id: int,
    student_id: list[int] = Form(...),
    status: list[str] = Form(...),
    comment: list[str] = Form(...),
    db: Session = Depends(get_db),
):
    records = [AttendanceItem(student_id=sid, status=st, comment=cm) for sid, st, cm in zip(student_id, status, comment)]
    payload = AttendanceSubmitRequest(batch_id=batch_id, attendance_date=date.today(), records=records)
    submit_attendance(db, payload.batch_id, payload.attendance_date, [r.model_dump() for r in records])
    return RedirectResponse(url=f'/ui/attendance/{batch_id}', status_code=303)


@router.get('/fees')
def fees_page(request: Request, db: Session = Depends(get_db)):
    data = get_fee_dashboard(db)
    return templates.TemplateResponse('fees.html', {'request': request, 'data': data})


@router.post('/fees/mark-paid')
def fees_mark_paid(fee_record_id: int = Form(...), paid_amount: float = Form(...), db: Session = Depends(get_db)):
    mark_fee_paid(db, fee_record_id, paid_amount)
    return RedirectResponse(url='/ui/fees', status_code=303)


@router.get('/homework')
def homework_page(request: Request, db: Session = Depends(get_db)):
    rows = list_homework(db)
    return templates.TemplateResponse('homework.html', {'request': request, 'rows': rows})


@router.post('/homework/create')
def homework_create(
    title: str = Form(...),
    description: str = Form(''),
    due_date: str = Form(...),
    attachment_path: str = Form(''),
    db: Session = Depends(get_db),
):
    payload = HomeworkCreateRequest(title=title, description=description, due_date=due_date, attachment_path=attachment_path)
    create_homework(db, payload.model_dump())
    return RedirectResponse(url='/ui/homework', status_code=303)


@router.get('/referrals')
def referrals_page(request: Request, db: Session = Depends(get_db)):
    rows = list_referrals(db)
    students = db.query(Student).all()
    return templates.TemplateResponse('referrals.html', {'request': request, 'rows': rows, 'students': students})


@router.post('/referrals/create')
def referral_create(student_id: int = Form(...), db: Session = Depends(get_db)):
    create_referral_code(db, student_id)
    return RedirectResponse(url='/ui/referrals', status_code=303)


@router.get('/teacher-actions')
def teacher_actions_page(request: Request, db: Session = Depends(get_db)):
    rows = list_open_actions(db)
    students = {s.id: s.name for s in db.query(Student).all()}
    return templates.TemplateResponse('teacher_actions.html', {'request': request, 'rows': rows, 'students': students})


@router.post('/teacher-actions/{action_id}/resolve')
def teacher_action_resolve(action_id: int, db: Session = Depends(get_db)):
    resolve_action(db, action_id)
    return RedirectResponse(url='/ui/teacher-actions', status_code=303)


@router.get('/system')
def system_page(request: Request, db: Session = Depends(get_db)):
    last = get_last_backup(db)
    db_path = ''
    try:
        db_path = str(get_sqlite_db_path())
    except ValueError:
        db_path = 'non-sqlite database configured'
    return templates.TemplateResponse(
        'system.html',
        {
            'request': request,
            'last_backup': last,
            'db_path': db_path,
        },
    )


@router.post('/system/backup-now')
def system_backup_now(db: Session = Depends(get_db)):
    run_backup_now(db)
    return RedirectResponse(url='/ui/system', status_code=303)


@router.get('/system/download-db')
def system_download_db():
    try:
        path = get_sqlite_db_path()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        path=str(path),
        media_type='application/octet-stream',
        filename=path.name,
    )
