from sqlalchemy.orm import Session

from app.config import settings
from app.models import RuleConfig


DEFAULT_RULES = {
    'absence_streak_threshold': 3,
    'notify_parent_on_absence': True,
    'notify_parent_on_fee_due': True,
    'reminder_grace_period_days': 0,
    'quiet_hours_start': settings.default_quiet_hours_start,
    'quiet_hours_end': settings.default_quiet_hours_end,
}


def get_effective_rule_config(db: Session, batch_id: int | None = None) -> dict:
    global_row = db.query(RuleConfig).filter(RuleConfig.batch_id.is_(None)).order_by(RuleConfig.id.desc()).first()
    batch_row = None
    if batch_id is not None:
        batch_row = db.query(RuleConfig).filter(RuleConfig.batch_id == batch_id).order_by(RuleConfig.id.desc()).first()

    effective = dict(DEFAULT_RULES)
    source = global_row or batch_row
    if global_row:
        effective.update(
            {
                'absence_streak_threshold': global_row.absence_streak_threshold,
                'notify_parent_on_absence': global_row.notify_parent_on_absence,
                'notify_parent_on_fee_due': global_row.notify_parent_on_fee_due,
                'reminder_grace_period_days': global_row.reminder_grace_period_days,
                'quiet_hours_start': global_row.quiet_hours_start,
                'quiet_hours_end': global_row.quiet_hours_end,
            }
        )
    if batch_row:
        effective.update(
            {
                'absence_streak_threshold': batch_row.absence_streak_threshold,
                'notify_parent_on_absence': batch_row.notify_parent_on_absence,
                'notify_parent_on_fee_due': batch_row.notify_parent_on_fee_due,
                'reminder_grace_period_days': batch_row.reminder_grace_period_days,
                'quiet_hours_start': batch_row.quiet_hours_start,
                'quiet_hours_end': batch_row.quiet_hours_end,
            }
        )
        source = batch_row

    effective['scope'] = 'batch' if batch_row else ('global' if global_row else 'default')
    effective['source_id'] = source.id if source else None
    return effective


def upsert_rule_config(
    db: Session,
    batch_id: int | None,
    absence_streak_threshold: int,
    notify_parent_on_absence: bool,
    notify_parent_on_fee_due: bool,
    reminder_grace_period_days: int,
    quiet_hours_start: str,
    quiet_hours_end: str,
):
    row = db.query(RuleConfig).filter(RuleConfig.batch_id == batch_id).order_by(RuleConfig.id.desc()).first()
    if not row:
        row = RuleConfig(batch_id=batch_id)
        db.add(row)

    row.absence_streak_threshold = absence_streak_threshold
    row.notify_parent_on_absence = notify_parent_on_absence
    row.notify_parent_on_fee_due = notify_parent_on_fee_due
    row.reminder_grace_period_days = reminder_grace_period_days
    row.quiet_hours_start = quiet_hours_start
    row.quiet_hours_end = quiet_hours_end
    db.commit()
    db.refresh(row)
    return row


def list_rule_configs(db: Session):
    return db.query(RuleConfig).order_by(RuleConfig.id.desc()).all()
