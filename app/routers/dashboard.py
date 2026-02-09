from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.insights_service import generate_insights
from app.services.auth_service import validate_session_token


router = APIRouter(prefix='/dashboard', tags=['Dashboard'])


@router.get('/teacher')
def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session or session['role'] not in ('teacher', 'admin'):
        raise HTTPException(status_code=401, detail='Unauthorized')
    return generate_insights(db)
