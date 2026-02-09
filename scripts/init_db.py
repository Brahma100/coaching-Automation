from datetime import date, timedelta
from pathlib import Path
import sys


# Ensure imports work when running this file directly: `python scripts/init_db.py`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import Base, SessionLocal, engine
from app.models import Batch, FeeRecord, Student
from app.services.fee_service import build_upi_link


Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if not db.query(Batch).first():
        batch = Batch(name='Batch A', start_time='07:00')
        db.add(batch)
        db.commit()
        db.refresh(batch)

        students = [
            Student(name='Aarav', batch_id=batch.id, guardian_phone='9999990001', telegram_chat_id=''),
            Student(name='Diya', batch_id=batch.id, guardian_phone='9999990002', telegram_chat_id=''),
            Student(name='Ishaan', batch_id=batch.id, guardian_phone='9999990003', telegram_chat_id=''),
        ]
        db.add_all(students)
        db.commit()

        for s in students:
            due = date.today() + timedelta(days=5)
            fee = FeeRecord(student_id=s.id, due_date=due, amount=2500, paid_amount=0, is_paid=False)
            db.add(fee)
        db.commit()

        rows = db.query(FeeRecord).all()
        for r in rows:
            st = db.query(Student).filter(Student.id == r.student_id).first()
            r.upi_link = build_upi_link(st, r.amount)
        db.commit()
finally:
    db.close()

print('DB initialized with sample data.')
