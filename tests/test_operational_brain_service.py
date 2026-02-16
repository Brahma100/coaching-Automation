import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.core.time_provider import default_time_provider
from app.models import AuthUser, Batch, BatchSchedule, Center, ClassSession, PendingAction, Student, TeacherBatchMap
from app.services.operational_brain_service import get_operational_brain


class OperationalBrainServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_operational_brain.db'
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
            for table in (PendingAction, ClassSession, BatchSchedule, TeacherBatchMap, Student, Batch, AuthUser, Center):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_center_teacher(self, db, *, slug: str, phone: str):
        center = Center(name=slug, slug=slug, timezone='Asia/Kolkata')
        db.add(center)
        db.commit()
        db.refresh(center)
        teacher = AuthUser(phone=phone, role='teacher', center_id=center.id)
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return center, teacher

    def test_teacher_without_batches_returns_empty_dataset(self):
        db = self._session_factory()
        try:
            center, teacher = self._seed_center_teacher(db, slug='center-empty', phone='9000000001')
            payload = get_operational_brain(
                db,
                {'user_id': teacher.id, 'role': 'teacher', 'center_id': center.id},
                bypass_cache=True,
            )
            self.assertEqual(payload.get('timeline'), [])
            self.assertEqual(payload.get('pending_inbox_actions'), [])
            self.assertEqual(payload.get('capacity_warnings'), [])
        finally:
            db.close()

    def test_teacher_brain_is_center_and_batch_scoped(self):
        db = self._session_factory()
        try:
            center_a, teacher_a = self._seed_center_teacher(db, slug='center-a', phone='9000000011')
            batch_a = Batch(name='Batch A', subject='Math', academic_level='', active=True, center_id=center_a.id)
            db.add(batch_a)
            db.commit()
            db.refresh(batch_a)
            db.add(TeacherBatchMap(teacher_id=teacher_a.id, batch_id=batch_a.id, center_id=center_a.id, is_primary=True))

            student_a = Student(name='Alice', guardian_phone='9111111111', batch_id=batch_a.id, center_id=center_a.id)
            db.add(student_a)
            db.commit()
            db.refresh(student_a)

            upcoming = default_time_provider.now().replace(tzinfo=None, second=0, microsecond=0) + timedelta(minutes=45)
            session_a = ClassSession(
                batch_id=batch_a.id,
                subject='Math',
                scheduled_start=upcoming,
                duration_minutes=60,
                status='scheduled',
                teacher_id=teacher_a.id,
                center_id=center_a.id,
            )
            db.add(session_a)
            db.commit()
            db.refresh(session_a)
            db.add(
                PendingAction(
                    type='review_session_summary',
                    action_type='review_session_summary',
                    teacher_id=teacher_a.id,
                    status='open',
                    due_at=upcoming - timedelta(minutes=5),
                    session_id=session_a.id,
                    center_id=center_a.id,
                    student_id=student_a.id,
                )
            )
            db.add(
                BatchSchedule(
                    batch_id=batch_a.id,
                    weekday=upcoming.weekday(),
                    start_time=upcoming.strftime('%H:%M'),
                    duration_minutes=60,
                )
            )

            center_b, teacher_b = self._seed_center_teacher(db, slug='center-b', phone='9000000022')
            batch_b = Batch(name='Batch B', subject='Science', academic_level='', active=True, center_id=center_b.id)
            db.add(batch_b)
            db.commit()
            db.refresh(batch_b)
            db.add(TeacherBatchMap(teacher_id=teacher_b.id, batch_id=batch_b.id, center_id=center_b.id, is_primary=True))
            session_b = ClassSession(
                batch_id=batch_b.id,
                subject='Science',
                scheduled_start=upcoming,
                duration_minutes=60,
                status='scheduled',
                teacher_id=teacher_b.id,
                center_id=center_b.id,
            )
            db.add(session_b)
            db.commit()

            payload = get_operational_brain(
                db,
                {'user_id': teacher_a.id, 'role': 'teacher', 'center_id': center_a.id},
                bypass_cache=True,
            )
            timeline = payload.get('timeline') or []
            self.assertTrue(any(int(row.get('batch_id') or 0) == int(batch_a.id) for row in timeline))
            self.assertFalse(any(int(row.get('batch_id') or 0) == int(batch_b.id) for row in timeline))
            self.assertIsNotNone(payload.get('next_upcoming_class'))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
