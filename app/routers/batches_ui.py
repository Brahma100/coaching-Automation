from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Batch
from app.services.auth_service import validate_session_token
from app.services.batch_management_service import (
    add_schedule,
    create_batch,
    delete_schedule,
    get_batch_detail,
    link_student_to_batch,
    list_all_students,
    list_batches_for_student,
    list_batches_with_details,
    list_students_for_batch,
    soft_delete_batch,
    unlink_student_from_batch,
    update_batch,
    update_schedule,
)


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(tags=['Batches UI'])


class BatchCreatePayload(BaseModel):
    name: str
    subject: str = 'General'
    academic_level: str = ''
    max_students: int | None = Field(default=None, ge=1, le=5000)


class BatchUpdatePayload(BaseModel):
    name: str
    subject: str = 'General'
    academic_level: str = ''
    max_students: int | None = Field(default=None, ge=1, le=5000)
    active: bool = True


class BatchSchedulePayload(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str
    duration_minutes: int = Field(gt=0, le=180)


class StudentLinkPayload(BaseModel):
    student_id: int


def _require_teacher(request: Request):
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session or session['role'] not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return session


@router.get('/ui/batches')
def batches_page(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    rows = list_batches_with_details(db, include_inactive=True)
    return templates.TemplateResponse('batches.html', {'request': request, 'rows': rows})


@router.get('/ui/batches/add')
def batches_add_page(
    request: Request,
    _: dict = Depends(_require_teacher),
):
    return templates.TemplateResponse('batches_add.html', {'request': request})


@router.post('/ui/batches/add')
def batches_add_submit(
    request: Request,
    name: str = Form(...),
    subject: str = Form('General'),
    academic_level: str = Form(''),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        create_batch(
            db,
            name=name,
            subject=subject,
            academic_level=academic_level,
            actor=session,
        )
        return RedirectResponse(url='/ui/batches', status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(
            'batches_add.html',
            {'request': request, 'error': str(exc), 'name': name, 'subject': subject, 'academic_level': academic_level},
            status_code=400,
        )


@router.get('/ui/batches/{batch_id}')
def batch_detail_page(
    batch_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        batch = get_batch_detail(db, batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    linked_students = list_students_for_batch(db, batch_id)
    all_students = list_all_students(db)
    linked_ids = {row['student_id'] for row in linked_students}
    available_students = [row for row in all_students if row.id not in linked_ids]

    return templates.TemplateResponse(
        'batch_detail.html',
        {
            'request': request,
            'batch': batch,
            'linked_students': linked_students,
            'available_students': available_students,
        },
    )


@router.post('/ui/batches/{batch_id}/schedule/add')
def batch_schedule_add_submit(
    batch_id: int,
    request: Request,
    weekday: int = Form(...),
    start_time: str = Form(...),
    duration_minutes: int = Form(...),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        add_schedule(
            db,
            batch_id,
            weekday=weekday,
            start_time=start_time,
            duration_minutes=duration_minutes,
            actor=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f'/ui/batches/{batch_id}', status_code=303)


@router.post('/ui/batches/{batch_id}/schedule/{schedule_id}/delete')
def batch_schedule_delete_submit(
    batch_id: int,
    schedule_id: int,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        delete_schedule(db, schedule_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(url=f'/ui/batches/{batch_id}', status_code=303)


@router.post('/ui/batches/{batch_id}/students/link')
def batch_student_link_submit(
    batch_id: int,
    student_id: int = Form(...),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        link_student_to_batch(db, batch_id=batch_id, student_id=student_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f'/ui/batches/{batch_id}', status_code=303)


@router.post('/ui/batches/{batch_id}/students/{student_id}/unlink')
def batch_student_unlink_submit(
    batch_id: int,
    student_id: int,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        unlink_student_from_batch(db, batch_id=batch_id, student_id=student_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f'/ui/batches/{batch_id}', status_code=303)


# Backward-compatible form endpoint used by older UI.
@router.post('/batches/create')
def batches_create_legacy(
    request: Request,
    name: str = Form(...),
    start_time: str = Form('07:00'),
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = create_batch(
            db,
            name=name,
            subject=name,
            academic_level='',
            actor=session,
        )
        if start_time:
            add_schedule(
                db,
                row.id,
                weekday=0,
                start_time=start_time,
                duration_minutes=60,
            )
    except ValueError:
        pass
    return RedirectResponse(url='/ui/batches', status_code=303)


# Backward-compatible API used by frontend.
@router.get('/batches')
def batches_list_api_legacy(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    rows = list_batches_with_details(db, include_inactive=False)
    return [
        {
            'id': row['id'],
            'name': row['name'],
            'start_time': row['start_time'],
            'subject': row['subject'],
            'academic_level': row['academic_level'],
            'active': row['active'],
            'student_count': row['student_count'],
            'schedules': row['schedules'],
        }
        for row in rows
    ]


@router.get('/api/batches')
def api_list_batches(
    request: Request,
    for_date: date | None = Query(default=None),
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    return list_batches_with_details(db, include_inactive=True, for_date=for_date)


@router.post('/api/batches')
def api_create_batch(
    payload: BatchCreatePayload,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = create_batch(
            db,
            name=payload.name,
            subject=payload.subject,
            academic_level=payload.academic_level,
            max_students=payload.max_students,
            actor=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'id': row.id,
        'name': row.name,
        'subject': row.subject,
        'academic_level': row.academic_level,
        'max_students': row.max_students,
        'active': row.active,
    }


@router.put('/api/batches/{batch_id}')
def api_update_batch(
    batch_id: int,
    payload: BatchUpdatePayload,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = update_batch(
            db,
            batch_id,
            name=payload.name,
            subject=payload.subject,
            academic_level=payload.academic_level,
            max_students=payload.max_students,
            active=payload.active,
            actor=session,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == 'Batch not found' else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        'id': row.id,
        'name': row.name,
        'subject': row.subject,
        'academic_level': row.academic_level,
        'max_students': row.max_students,
        'active': row.active,
    }


@router.delete('/api/batches/{batch_id}')
def api_soft_delete_batch(
    batch_id: int,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = soft_delete_batch(db, batch_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'id': row.id, 'active': row.active}


@router.post('/api/batches/{batch_id}/schedule')
def api_add_schedule(
    batch_id: int,
    payload: BatchSchedulePayload,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = add_schedule(
            db,
            batch_id,
            weekday=payload.weekday,
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            actor=session,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == 'Batch not found' else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        'id': row.id,
        'batch_id': row.batch_id,
        'weekday': row.weekday,
        'start_time': row.start_time,
        'duration_minutes': row.duration_minutes,
    }


@router.put('/api/batch-schedules/{schedule_id}')
def api_update_schedule(
    schedule_id: int,
    payload: BatchSchedulePayload,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = update_schedule(
            db,
            schedule_id,
            weekday=payload.weekday,
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            actor=session,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == 'Schedule not found' else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        'id': row.id,
        'batch_id': row.batch_id,
        'weekday': row.weekday,
        'start_time': row.start_time,
        'duration_minutes': row.duration_minutes,
    }


@router.delete('/api/batch-schedules/{schedule_id}')
def api_delete_schedule(
    schedule_id: int,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        delete_schedule(db, schedule_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'ok': True}


@router.post('/api/batches/{batch_id}/students')
def api_link_student_to_batch(
    batch_id: int,
    payload: StudentLinkPayload,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = link_student_to_batch(db, batch_id=batch_id, student_id=payload.student_id, actor=session)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message in ('Batch not found', 'Student not found') else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    return {
        'id': row.id,
        'student_id': row.student_id,
        'batch_id': row.batch_id,
        'active': row.active,
        'joined_at': row.joined_at.isoformat() if row.joined_at else None,
    }


@router.get('/api/batches/{batch_id}/students')
def api_list_batch_students(
    batch_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    return list_students_for_batch(db, batch_id)


@router.delete('/api/batches/{batch_id}/students/{student_id}')
def api_unlink_student_from_batch(
    batch_id: int,
    student_id: int,
    request: Request,
    session: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    try:
        row = unlink_student_from_batch(db, batch_id=batch_id, student_id=student_id, actor=session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        'id': row.id,
        'student_id': row.student_id,
        'batch_id': row.batch_id,
        'active': row.active,
    }


@router.get('/api/students/{student_id}/batches')
def api_list_student_batches(
    student_id: int,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    return list_batches_for_student(db, student_id)
