import json
from datetime import date

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AttendanceRecord, FeeRecord


def backup_daily_to_google_sheet(db: Session) -> bool:
    if not settings.enable_sheets_backup:
        return False
    if not settings.sheet_id or not settings.google_credentials_json:
        return False

    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds_dict = json.loads(settings.google_credentials_json)
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(settings.sheet_id)

    worksheet_name = f"backup-{date.today()}"
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=1000, cols=10)

    records = []
    attendance = db.query(AttendanceRecord).all()
    for row in attendance:
        records.append(['attendance', row.student_id, str(row.attendance_date), row.status, row.comment])

    fees = db.query(FeeRecord).all()
    for row in fees:
        records.append(['fee', row.student_id, str(row.due_date), row.amount, row.paid_amount, row.is_paid])

    ws.clear()
    ws.append_row(['type', 'student_id', 'date', 'field_1', 'field_2', 'field_3'])
    if records:
        ws.append_rows(records)
    return True
