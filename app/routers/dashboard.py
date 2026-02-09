from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.insights_service import generate_insights


router = APIRouter(prefix='/dashboard', tags=['Dashboard'])


@router.get('/teacher')
def teacher_dashboard(db: Session = Depends(get_db)):
    return generate_insights(db)
