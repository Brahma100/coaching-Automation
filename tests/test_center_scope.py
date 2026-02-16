import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache, cache_key
from app.db import Base
from app.models import AuthUser, Batch, BatchSchedule, Center, ClassSession, TeacherBatchMap
from app.services.center_scope_service import center_context
from app.services.dashboard_today_service import clear_today_view_cache, get_today_view


class CenterScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_center_scope.db'
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
            clear_today_view_cache()
            db.query(ClassSession).delete()
            db.query(BatchSchedule).delete()
            db.query(TeacherBatchMap).delete()
            db.query(Batch).delete()
            db.query(AuthUser).delete()
            db.query(Center).delete()
            db.commit()
        finally:
            db.close()

    def _seed_two_centers(self, db):
        center_a = Center(name='Center A', slug='center-a', timezone='Asia/Kolkata')
        center_b = Center(name='Center B', slug='center-b', timezone='Asia/Kolkata')
        db.add_all([center_a, center_b])
        db.commit()
        db.refresh(center_a)
        db.refresh(center_b)
        return center_a, center_b

    def test_teacher_cannot_see_other_center_batches(self):
        db = self._session_factory()
        try:
            center_a, center_b = self._seed_two_centers(db)
            teacher = AuthUser(phone='9000000001', role='teacher', center_id=center_a.id)
            db.add(teacher)
            db.commit()
            db.refresh(teacher)

            batch_a = Batch(name='Center A Batch', subject='Math', academic_level='', center_id=center_a.id, active=True, start_time='09:00')
            batch_b = Batch(name='Center B Batch', subject='Science', academic_level='', center_id=center_b.id, active=True, start_time='10:00')
            db.add_all([batch_a, batch_b])
            db.commit()
            db.refresh(batch_a)
            db.refresh(batch_b)

            db.add_all(
                [
                    TeacherBatchMap(teacher_id=teacher.id, batch_id=batch_a.id, center_id=center_a.id, is_primary=True),
                    BatchSchedule(batch_id=batch_a.id, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60),
                    BatchSchedule(batch_id=batch_b.id, weekday=date.today().weekday(), start_time='10:00', duration_minutes=60),
                    ClassSession(
                        batch_id=batch_a.id,
                        subject='Math',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher.id,
                        center_id=center_a.id,
                    ),
                    ClassSession(
                        batch_id=batch_b.id,
                        subject='Science',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('10:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher.id,
                        center_id=center_b.id,
                    ),
                ]
            )
            db.commit()

            payload = get_today_view(db, actor={'user_id': teacher.id, 'role': 'teacher', 'center_id': center_a.id})
            visible_batch_ids = {int(row['batch_id']) for row in payload.get('today_classes', [])}
            self.assertIn(batch_a.id, visible_batch_ids)
            self.assertNotIn(batch_b.id, visible_batch_ids)
        finally:
            db.close()

    def test_admin_isolation_by_center(self):
        db = self._session_factory()
        try:
            center_a, center_b = self._seed_two_centers(db)
            admin = AuthUser(phone='9000000002', role='admin', center_id=center_a.id)
            db.add(admin)
            db.commit()
            db.refresh(admin)

            batch_a = Batch(name='Admin A Batch', subject='Math', academic_level='', center_id=center_a.id, active=True, start_time='08:00')
            batch_b = Batch(name='Admin B Batch', subject='Science', academic_level='', center_id=center_b.id, active=True, start_time='11:00')
            db.add_all([batch_a, batch_b])
            db.commit()
            db.refresh(batch_a)
            db.refresh(batch_b)

            db.add_all(
                [
                    BatchSchedule(batch_id=batch_a.id, weekday=date.today().weekday(), start_time='08:00', duration_minutes=60),
                    BatchSchedule(batch_id=batch_b.id, weekday=date.today().weekday(), start_time='11:00', duration_minutes=60),
                ]
            )
            db.commit()

            payload = get_today_view(db, actor={'user_id': admin.id, 'role': 'admin', 'center_id': center_a.id})
            visible_batch_ids = {int(row['batch_id']) for row in payload.get('today_classes', [])}
            self.assertIn(batch_a.id, visible_batch_ids)
            self.assertNotIn(batch_b.id, visible_batch_ids)
        finally:
            db.close()

    def test_cache_isolation_by_center(self):
        base_key = cache_key('today_view', 'teacher:1')

        with center_context(101):
            cache.set_cached(base_key, {'value': 'center-a'}, ttl=60)
        with center_context(202):
            cache.set_cached(base_key, {'value': 'center-b'}, ttl=60)

        with center_context(101):
            self.assertEqual(cache.get_cached(base_key), {'value': 'center-a'})
        with center_context(202):
            self.assertEqual(cache.get_cached(base_key), {'value': 'center-b'})


if __name__ == '__main__':
    unittest.main()
