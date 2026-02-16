import logging
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.time_provider import default_time_provider
from app.models import Batch, ClassSession, FeeRecord, PendingAction, Student, StudentBatchMap
from app.schemas import HomeworkCreateRequest
from app.services.fee_service import get_fee_dashboard, mark_fee_paid
from app.services.homework_service import create_homework, list_homework
from app.services.insights_service import generate_insights
from app.services.pending_action_service import list_open_actions, resolve_action
from app.services.referral_service import create_referral_code, list_referrals
from app.services.system_service import get_last_backup, get_sqlite_db_path, run_backup_now


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui', tags=['UI'])
logger = logging.getLogger(__name__)


@router.get('/dashboard')
def dashboard(request: Request, db: Session = Depends(get_db)):
    insights = generate_insights(db, time_provider=default_time_provider)
    today = default_time_provider.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = start_dt + timedelta(days=1)
    today_session = db.query(ClassSession).filter(
        ClassSession.scheduled_start >= start_dt,
        ClassSession.scheduled_start < end_dt,
    ).order_by(ClassSession.scheduled_start.asc()).first()
    pending_actions_count = db.query(PendingAction).filter(PendingAction.status == 'open').count()

    unpaid = db.query(FeeRecord).filter(FeeRecord.is_paid.is_(False)).all()
    overdue_count = sum(1 for row in unpaid if row.due_date < today)
    due_soon_count = sum(1 for row in unpaid if today <= row.due_date <= (today + timedelta(days=3)))

    return templates.TemplateResponse(
        'dashboard.html',
        {
            'request': request,
            'insights': insights,
            'today_session': today_session,
            'pending_actions_count': pending_actions_count,
            'overdue_count': overdue_count,
            'due_soon_count': due_soon_count,
        },
    )


@router.get('/attendance')
def attendance_page(
    request: Request,
    batch_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _ = request
    _ = db
    url = '/ui/attendance/manage'
    if batch_id:
        url += f'?batch_id={batch_id}'
    return RedirectResponse(url=url, status_code=303)


@router.get('/attendance/{batch_id}')
def attendance_page_for_batch(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    _ = request
    _ = db
    return RedirectResponse(url=f'/ui/attendance/manage?batch_id={batch_id}', status_code=303)


@router.post('/attendance/{batch_id}')
def attendance_submit(
    batch_id: int,
    student_ids_form: list[int] | None = Form(default=None),
    statuses_form: list[str] | None = Form(default=None),
    comments_form: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
):
    _ = student_ids_form
    _ = statuses_form
    _ = comments_form
    _ = db
    return RedirectResponse(url=f'/ui/attendance/manage?batch_id={batch_id}', status_code=303)


@router.get('/fees')
def fees_page(request: Request, batch_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    data = get_fee_dashboard(db)
    batches = db.query(Batch).order_by(Batch.name.asc()).all()

    if batch_id is not None:
        student_ids = {
            sid
            for (sid,) in db.query(StudentBatchMap.student_id).filter(
                StudentBatchMap.batch_id == batch_id,
                StudentBatchMap.active.is_(True),
            ).all()
        }
        if not student_ids:
            student_ids = {
                sid
                for (sid,) in db.query(Student.id).filter(Student.batch_id == batch_id).all()
            }
        data = {
            'due': [row for row in data['due'] if row['student_id'] in student_ids],
            'paid': [row for row in data['paid'] if row['student_id'] in student_ids],
            'overdue': [row for row in data['overdue'] if row['student_id'] in student_ids],
        }

    return templates.TemplateResponse(
        'fees.html',
        {
            'request': request,
            'data': data,
            'batches': batches,
            'selected_batch_id': batch_id,
        },
    )


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
