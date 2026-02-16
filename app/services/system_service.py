from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BackupLog
from app.services.center_scope_service import get_current_center_id
from app.services.google_sheets_backup import backup_daily_to_google_sheet


def get_sqlite_db_path() -> Path:
    # Supports sqlite:///relative/path.db
    prefix = 'sqlite:///'
    if not settings.database_url.startswith(prefix):
        raise ValueError('Database URL is not SQLite')
    raw = settings.database_url[len(prefix):]
    return Path(raw).resolve()


def run_backup_now(db: Session) -> BackupLog:
    try:
        center_id = int(get_current_center_id() or 0)
        ok = backup_daily_to_google_sheet(db, center_id=center_id)
        if ok:
            row = BackupLog(status='success', message='Backup synced to Google Sheets')
        else:
            row = BackupLog(status='failed', message='Backup skipped; missing sheets configuration')
    except Exception as exc:
        row = BackupLog(status='failed', message=f'Backup failed: {exc}')

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_last_backup(db: Session) -> BackupLog | None:
    return db.query(BackupLog).order_by(BackupLog.created_at.desc()).first()
