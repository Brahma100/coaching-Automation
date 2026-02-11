import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache
from app.db import Base
from app.models import Batch, BatchSchedule, CalendarOverride, ClassSession, FeeRecord, Room, Student, StudentBatchMap, StudentRiskProfile
from app.services.teacher_calendar_service import _calendar_cache_key, clear_teacher_calendar_cache, get_teacher_calendar, validate_calendar_conflicts


class TeacherCalendarServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_teacher_calendar.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

    @classmethod
    def tearDownClass(cls):
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            clear_teacher_calendar_cache()
            for table in (
                StudentRiskProfile,
                FeeRecord,
                StudentBatchMap,
                Student,
                CalendarOverride,
                ClassSession,
                Room,
                BatchSchedule,
                Batch,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_batch_with_schedule(self, db, *, name='Batch A', subject='Math', level='8', weekday=0, start_time='09:00', duration=60):
        batch = Batch(name=name, subject=subject, academic_level=level, active=True, start_time=start_time)
        db.add(batch)
        db.commit()
        db.refresh(batch)

        schedule = BatchSchedule(batch_id=batch.id, weekday=weekday, start_time=start_time, duration_minutes=duration)
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return batch, schedule

    def test_calendar_view_expands_recurring_and_counts_flags(self):
        db = self._session_factory()
        try:
            today = date.today()
            weekday = today.weekday()
            batch, _ = self._seed_batch_with_schedule(db, weekday=weekday)

            student = Student(name='Alice', guardian_phone='111', telegram_chat_id='tg1', batch_id=batch.id)
            db.add(student)
            db.commit()
            db.refresh(student)
            db.add(StudentBatchMap(student_id=student.id, batch_id=batch.id, active=True))
            db.add(FeeRecord(student_id=student.id, due_date=today, amount=400, paid_amount=0, is_paid=False))
            db.add(StudentRiskProfile(student_id=student.id, risk_level='HIGH', final_risk_score=22))
            db.commit()

            payload = get_teacher_calendar(
                db,
                teacher_id=0,
                start_date=today,
                end_date=today,
                view='day',
                actor_role='teacher',
                actor_user_id=5,
                bypass_cache=True,
            )['items']
            self.assertEqual(len(payload), 1)
            row = payload[0]
            self.assertEqual(row['batch_name'], 'Batch A')
            self.assertEqual(row['student_count'], 1)
            self.assertEqual(row['fee_due_count'], 1)
            self.assertEqual(row['risk_count'], 1)
            self.assertTrue(row['flags']['has_overdue_fees'])
            self.assertTrue(row['flags']['has_high_risk_students'])
        finally:
            db.close()

    def test_override_logic_cancel_and_extra_class(self):
        db = self._session_factory()
        try:
            today = date.today()
            weekday = today.weekday()
            batch, _ = self._seed_batch_with_schedule(db, weekday=weekday, start_time='10:00', duration=60)

            db.add(
                CalendarOverride(
                    batch_id=batch.id,
                    override_date=today,
                    cancelled=True,
                    reason='Holiday',
                )
            )
            extra_date = today + timedelta(days=1)
            db.add(
                CalendarOverride(
                    batch_id=batch.id,
                    override_date=extra_date,
                    new_start_time='12:30',
                    new_duration_minutes=90,
                    cancelled=False,
                    reason='Extra class',
                )
            )
            db.commit()

            payload = get_teacher_calendar(
                db,
                teacher_id=0,
                start_date=today,
                end_date=extra_date,
                view='week',
                actor_role='teacher',
                actor_user_id=5,
                bypass_cache=True,
            )['items']
            dates = [row['start_datetime'][:10] for row in payload]
            self.assertNotIn(today.isoformat(), dates)
            self.assertIn(extra_date.isoformat(), dates)
        finally:
            db.close()

    def test_live_status_detection(self):
        db = self._session_factory()
        try:
            today = date.today()
            weekday = today.weekday()
            start_dt = datetime.utcnow() - timedelta(minutes=10)
            start_time = start_dt.strftime('%H:%M')
            batch, _ = self._seed_batch_with_schedule(db, weekday=weekday, start_time=start_time, duration=60)
            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.combine(today, datetime.strptime(start_time, '%H:%M').time()),
                    duration_minutes=60,
                    teacher_id=42,
                    status='open',
                )
            )
            db.commit()

            payload = get_teacher_calendar(
                db,
                teacher_id=42,
                start_date=today,
                end_date=today,
                view='day',
                actor_role='teacher',
                actor_user_id=42,
                bypass_cache=True,
            )['items']
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]['status'], 'live')
        finally:
            db.close()

    def test_conflict_detection(self):
        db = self._session_factory()
        try:
            batch, _ = self._seed_batch_with_schedule(db, weekday=2, start_time='10:00', duration=60)
            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.utcnow(),
                    duration_minutes=60,
                    teacher_id=99,
                    status='scheduled',
                )
            )
            db.commit()

            target_day = date.today()
            result = validate_calendar_conflicts(db, teacher_id=99, target_date=target_day, start_time='10:30', duration_minutes=45, room_id=None)
            self.assertFalse(result['ok'])
            self.assertEqual(result['conflicts'][0]['type'], 'teacher_conflict')
        finally:
            db.close()

    def test_room_conflict_detection(self):
        db = self._session_factory()
        try:
            room = Room(name='Room A', institute_id=1, capacity=20, color_code='#999999')
            db.add(room)
            db.commit()
            db.refresh(room)

            batch, _ = self._seed_batch_with_schedule(db, weekday=2, start_time='10:00', duration=60)
            batch.room_id = room.id
            db.commit()

            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.utcnow(),
                    duration_minutes=60,
                    teacher_id=10,
                    status='scheduled',
                )
            )
            db.commit()

            target_day = date.today()
            result = validate_calendar_conflicts(db, teacher_id=11, target_date=target_day, start_time='10:30', duration_minutes=45, room_id=room.id)
            self.assertFalse(result['ok'])
            self.assertTrue(any(row['type'] == 'room_conflict' for row in result['conflicts']))
        finally:
            db.close()

    def test_cache_key_scoping(self):
        key_teacher = _calendar_cache_key(
            role='teacher',
            actor_user_id=7,
            teacher_id=7,
            start_date=date(2026, 2, 11),
            end_date=date(2026, 2, 17),
            view='week',
        )
        key_admin = _calendar_cache_key(
            role='admin',
            actor_user_id=1,
            teacher_id=7,
            start_date=date(2026, 2, 11),
            end_date=date(2026, 2, 17),
            view='week',
        )
        self.assertNotEqual(key_teacher, key_admin)

        cache.set_cached(key_teacher, {'role': 'teacher'}, ttl=60)
        cache.set_cached(key_admin, {'role': 'admin'}, ttl=60)
        self.assertEqual(cache.get_cached(key_teacher), {'role': 'teacher'})
        self.assertEqual(cache.get_cached(key_admin), {'role': 'admin'})


if __name__ == '__main__':
    unittest.main()
