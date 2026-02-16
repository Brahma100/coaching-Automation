from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import (
    AuthAuthorizationError,
    clear_session_token,
    google_login,
    login_password,
    request_otp,
    signup_password,
    verify_otp,
)
from app.services.rate_limit_service import SafeRateLimitError


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(tags=['Auth'])


class OtpRequestPayload(BaseModel):
    phone: str


class OtpVerifyPayload(BaseModel):
    phone: str
    otp: str
    next: str = '/dashboard'


class PasswordSignupPayload(BaseModel):
    phone: str
    password: str
    next: str = '/dashboard'


class PasswordLoginPayload(BaseModel):
    phone: str
    password: str
    next: str = '/dashboard'


class GoogleLoginPayload(BaseModel):
    id_token: str
    next: str = '/dashboard'


@router.get('/ui/login')
def login_page(request: Request, next: str = '/dashboard'):
    return templates.TemplateResponse('login.html', {'request': request, 'next': next})


@router.get('/ui/signup')
def signup_page(request: Request, next: str = '/dashboard'):
    return templates.TemplateResponse('login.html', {'request': request, 'next': next})


@router.post('/auth/request-otp')
def auth_request_otp(payload: OtpRequestPayload, db: Session = Depends(get_db)):
    try:
        data = request_otp(db, payload.phone)
        return data
    except SafeRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AuthAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/auth/verify-otp')
def auth_verify_otp(payload: OtpVerifyPayload, db: Session = Depends(get_db)):
    try:
        data = verify_otp(db, payload.phone, payload.otp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    response = JSONResponse(
        {
            'ok': True,
            'token': data['token'],
            'role': data['role'],
            'next': payload.next or '/dashboard',
        }
    )
    response.set_cookie(
        key='auth_session',
        value=data['token'],
        httponly=True,
        samesite='lax',
        secure=False,
        max_age=60 * 60 * 24 * 365 * 5,
    )
    return response


def _session_cookie_response(data: dict, next_url: str):
    response = JSONResponse(
        {
            'ok': True,
            'token': data['token'],
            'role': data['role'],
            'next': next_url or '/dashboard',
        }
    )
    response.set_cookie(
        key='auth_session',
        value=data['token'],
        httponly=True,
        samesite='lax',
        secure=False,
        max_age=60 * 60 * 24 * 365 * 5,
    )
    return response


@router.post('/auth/signup-password')
def auth_signup_password(payload: PasswordSignupPayload, db: Session = Depends(get_db)):
    try:
        data = signup_password(db, payload.phone, payload.password)
    except AuthAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _session_cookie_response(data, payload.next)


@router.post('/auth/login-password')
def auth_login_password(payload: PasswordLoginPayload, db: Session = Depends(get_db)):
    try:
        data = login_password(db, payload.phone, payload.password)
    except AuthAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _session_cookie_response(data, payload.next)


@router.post('/auth/google-login')
def auth_google_login(payload: GoogleLoginPayload, db: Session = Depends(get_db)):
    try:
        data = google_login(db, payload.id_token)
    except ValueError as exc:
        if 'not configured' in str(exc).lower():
            raise HTTPException(status_code=501, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _session_cookie_response(data, payload.next)


@router.post('/auth/logout')
def auth_logout(request: Request):
    token = request.cookies.get('auth_session')
    clear_session_token(token)
    response = JSONResponse({'ok': True})
    response.delete_cookie('auth_session')
    return response
