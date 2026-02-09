from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.allowlist_admin_service import (
    activate_allowed_user_admin,
    deactivate_allowed_user_admin,
    invite_allowed_user,
    list_allowed_users_admin,
    require_admin_session,
)


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(tags=['Admin Allowlist UI'])


def _require_admin(request: Request, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get('auth_session')
    try:
        return require_admin_session(db, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or 'Forbidden') from exc


@router.get('/ui/admin/allowed-users')
def allowed_users_list_page(
    request: Request,
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = list_allowed_users_admin(db)
    return templates.TemplateResponse(
        'allowed_users.html',
        {
            'request': request,
            'rows': rows,
            'success': request.query_params.get('success', ''),
            'error': request.query_params.get('error', ''),
        },
    )


@router.get('/ui/admin/allowed-users/invite')
def allowed_users_invite_page(
    request: Request,
    _: dict = Depends(_require_admin),
):
    return templates.TemplateResponse(
        'allowed_users_invite.html',
        {
            'request': request,
            'success': request.query_params.get('success', ''),
            'error': request.query_params.get('error', ''),
        },
    )


@router.post('/ui/admin/allowed-users/invite')
def allowed_users_invite_submit(
    request: Request,
    phone: str = Form(...),
    role: str = Form(...),
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        invite_allowed_user(db, phone, role)
        return RedirectResponse(
            url='/ui/admin/allowed-users?success=User+invited',
            status_code=303,
        )
    except ValueError as exc:
        query = urlencode({'error': str(exc)})
        return RedirectResponse(url=f'/ui/admin/allowed-users/invite?{query}', status_code=303)


@router.post('/ui/admin/allowed-users/activate')
def allowed_users_activate_submit(
    request: Request,
    phone: str = Form(...),
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        activate_allowed_user_admin(db, phone)
        return RedirectResponse(
            url='/ui/admin/allowed-users?success=User+activated',
            status_code=303,
        )
    except ValueError as exc:
        query = urlencode({'error': str(exc)})
        return RedirectResponse(url=f'/ui/admin/allowed-users?{query}', status_code=303)


@router.post('/ui/admin/allowed-users/deactivate')
def allowed_users_deactivate_submit(
    request: Request,
    phone: str = Form(...),
    _: dict = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    try:
        deactivate_allowed_user_admin(db, phone)
        return RedirectResponse(
            url='/ui/admin/allowed-users?success=User+deactivated',
            status_code=303,
        )
    except ValueError as exc:
        query = urlencode({'error': str(exc)})
        return RedirectResponse(url=f'/ui/admin/allowed-users?{query}', status_code=303)
