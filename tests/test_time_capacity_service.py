import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.time_provider import TimeProvider
from app.db import Base
from app.models import AuthUser, Batch, BatchSchedule, ClassSession, Student, StudentBatchMap, TeacherBatchMap, TeacherUnavailability
from app.services.time_capacity_service import (
    create_teacher_unavailability,
    delete_teacher_unavailability,
    get_batch_capacity,
    get_reschedule_options,
    get_teacher_availability,
    get_weekly_load,
)
from app.services.center_scope_service import center_context

class FixedTimeProvider(TimeProvider):
    def __init__(self, frozen_dt: datetime):
        self._frozen_dt = frozen_dt

    def now(self) -> datetime:
        return self._frozen_dt


class TimeCapacityServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_time_capacity.db'
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
            for table in (
                TeacherUnavailability,
                ClassSession,
                StudentBatchMap,
                TeacherBatchMap,
                Student,
                BatchSchedule,
                Batch,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_teacher(self, db) -> AuthUser:
        teacher = AuthUser(
            phone='9999999999',
            role='teacher',
            daily_work_start_time=time(hour=7, minute=0),
            daily_work_end_time=time(hour=20, minute=0),
            calendar_snap_minutes=15,
        )
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return teacher

    def _seed_batch(self, db, *, name='Batch A', max_students=10, weekday=3, start_time='10:00', duration=60, teacher_id=None):
        batch = Batch(
            name=name,
            subject='Math',
            academic_level='8',
            active=True,
            default_duration_minutes=duration,
            max_students=max_students,
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        db.add(BatchSchedule(batch_id=batch.id, weekday=weekday, start_time=start_time, duration_minutes=duration))
        if teacher_id:
            db.add(TeacherBatchMap(teacher_id=int(teacher_id), batch_id=batch.id, is_primary=True))
        db.commit()
        db.refresh(batch)
        return batch

    @freeze_time('2026-02-13 10:00:00')
    def test_availability_computation_includes_busy_free_and_blocked(self):
        db = self._session_factory()
        try:
            fixed_provider = FixedTimeProvider(datetime(2026, 2, 13, 10, 0, 0, tzinfo=timezone.utc))
            teacher = self._seed_teacher(db)
            batch = self._seed_batch(db, teacher_id=teacher.id)
            today = date(2026, 2, 13)
            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.combine(today, time(hour=10, minute=0)),
                    duration_minutes=60,
                    teacher_id=teacher.id,
                    status='scheduled',
                )
            )
            db.commit()

            create_teacher_unavailability(
                db,
                teacher_id=teacher.id,
                target_date=today,
                start_time_value=time(hour=12, minute=0),
                end_time_value=time(hour=12, minute=30),
                reason='Personal errand',
            )

            with center_context(1):
                payload = get_teacher_availability(db, teacher.id, today, time_provider=fixed_provider)
            self.assertGreaterEqual(payload['total_busy_minutes'], 90)
            self.assertGreater(payload['total_free_minutes'], 0)
            self.assertTrue(any(slot['source'] == 'teacher_block' for slot in payload['busy_slots']))
        finally:
            db.close()

    @freeze_time('2026-02-13 10:00:00')
    def test_batch_capacity_uses_active_student_mappings(self):
        db = self._session_factory()
        try:
            batch = self._seed_batch(db, max_students=5)
            student_1 = Student(name='One', guardian_phone='1', telegram_chat_id='t1', batch_id=batch.id)
            student_2 = Student(name='Two', guardian_phone='2', telegram_chat_id='t2', batch_id=batch.id)
            db.add_all([student_1, student_2])
            db.commit()
            db.refresh(student_1)
            db.refresh(student_2)
            db.add(StudentBatchMap(student_id=student_1.id, batch_id=batch.id, active=True))
            db.add(StudentBatchMap(student_id=student_2.id, batch_id=batch.id, active=False))
            db.commit()

            with center_context(1):
                payload = get_batch_capacity(db)
            row = next(item for item in payload if item['batch_id'] == batch.id)
            self.assertEqual(row['enrolled_students'], 1)
            self.assertEqual(row['available_seats'], 4)
            self.assertEqual(row['utilization_percentage'], 20.0)
        finally:
            db.close()

    @freeze_time('2026-02-13 10:00:00')
    def test_reschedule_options_respect_blocked_slots(self):
        db = self._session_factory()
        try:
            fixed_provider = FixedTimeProvider(datetime(2026, 2, 13, 10, 0, 0, tzinfo=timezone.utc))
            teacher = self._seed_teacher(db)
            batch = self._seed_batch(db, start_time='09:00', duration=60, teacher_id=teacher.id)
            target = date(2026, 2, 13)
            create_teacher_unavailability(
                db,
                teacher_id=teacher.id,
                target_date=target,
                start_time_value=time(hour=9, minute=0),
                end_time_value=time(hour=11, minute=0),
                reason='Blocked morning',
            )

            with center_context(1):
                payload = get_reschedule_options(db, teacher.id, batch.id, target, time_provider=fixed_provider)
            self.assertTrue(payload)
            blocked_overlap = [
                row
                for row in payload
                if row['date'] == target.isoformat() and row['start_time'] >= '09:00' and row['start_time'] < '11:00'
            ]
            self.assertEqual(blocked_overlap, [])
        finally:
            db.close()

    @freeze_time('2026-02-13 10:00:00')
    def test_reschedule_options_exclude_past_times_for_today(self):
        db = self._session_factory()
        try:
            fixed_provider = FixedTimeProvider(datetime(2026, 2, 13, 10, 0, 0, tzinfo=timezone.utc))
            teacher = self._seed_teacher(db)
            batch = self._seed_batch(db, start_time='08:00', duration=60, teacher_id=teacher.id)
            target = date(2026, 2, 13)

            with center_context(1):
                payload = get_reschedule_options(db, teacher.id, batch.id, target, time_provider=fixed_provider)
            self.assertTrue(payload)
            same_day_rows = [row for row in payload if row['date'] == target.isoformat()]
            self.assertTrue(same_day_rows)
            self.assertTrue(all(row['start_time'] > '10:00' for row in same_day_rows))
        finally:
            db.close()

    @freeze_time('2026-02-13 10:00:00')
    def test_weekly_load_calculation(self):
        db = self._session_factory()
        try:
            fixed_provider = FixedTimeProvider(datetime(2026, 2, 13, 10, 0, 0, tzinfo=timezone.utc))
            teacher = self._seed_teacher(db)
            batch = self._seed_batch(db, weekday=0, start_time='10:00', duration=90, teacher_id=teacher.id)
            monday = date(2026, 2, 9)
            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.combine(monday, time(hour=10, minute=0)),
                    duration_minutes=90,
                    teacher_id=teacher.id,
                    status='scheduled',
                )
            )
            db.commit()

            with center_context(1):
                payload = get_weekly_load(db, teacher.id, monday, time_provider=fixed_provider)
            self.assertEqual(len(payload['daily_hours']), 7)
            self.assertGreaterEqual(payload['total_weekly_minutes'], 90)
            self.assertGreaterEqual(payload['utilization_percentage'], 0)
        finally:
            db.close()

    @freeze_time('2026-02-13 10:00:00')
    def test_block_create_and_delete(self):
        db = self._session_factory()
        try:
            teacher = self._seed_teacher(db)
            today = date(2026, 2, 13)
            row = create_teacher_unavailability(
                db,
                teacher_id=teacher.id,
                target_date=today,
                start_time_value=time(hour=15, minute=0),
                end_time_value=time(hour=16, minute=0),
                reason='Meeting',
            )
            self.assertIsNotNone(row.id)
            deleted = delete_teacher_unavailability(db, teacher_id=teacher.id, block_id=row.id, admin=False)
            self.assertTrue(deleted)
            exists = db.query(TeacherUnavailability).filter(TeacherUnavailability.id == row.id).first()
            self.assertIsNone(exists)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
