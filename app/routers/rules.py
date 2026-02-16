from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import RuleConfigUpsertRequest
from app.services.rule_config_service import get_effective_rule_config, list_rule_configs, upsert_rule_config


router = APIRouter(prefix='/rules', tags=['Rules'])


@router.get('/effective')
def effective(batch_id: int | None = None, db: Session = Depends(get_db)):
    return get_effective_rule_config(db, batch_id=batch_id)


@router.get('/list')
def list_all(db: Session = Depends(get_db)):
    rows = list_rule_configs(db)
    return [
        {
            'id': r.id,
            'batch_id': r.batch_id,
            'absence_streak_threshold': r.absence_streak_threshold,
            'notify_parent_on_absence': r.notify_parent_on_absence,
            'notify_parent_on_fee_due': r.notify_parent_on_fee_due,
            'enable_student_lifecycle_notifications': r.enable_student_lifecycle_notifications,
            'reminder_grace_period_days': r.reminder_grace_period_days,
            'quiet_hours_start': r.quiet_hours_start,
            'quiet_hours_end': r.quiet_hours_end,
        }
        for r in rows
    ]


@router.post('/upsert')
def upsert(payload: RuleConfigUpsertRequest, db: Session = Depends(get_db)):
    row = upsert_rule_config(
        db,
        batch_id=payload.batch_id,
        absence_streak_threshold=payload.absence_streak_threshold,
        notify_parent_on_absence=payload.notify_parent_on_absence,
        notify_parent_on_fee_due=payload.notify_parent_on_fee_due,
        enable_student_lifecycle_notifications=payload.enable_student_lifecycle_notifications,
        reminder_grace_period_days=payload.reminder_grace_period_days,
        quiet_hours_start=payload.quiet_hours_start,
        quiet_hours_end=payload.quiet_hours_end,
    )
    return {'id': row.id, 'batch_id': row.batch_id}
