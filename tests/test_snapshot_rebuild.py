import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    AdminOpsSnapshot,
    AuthUser,
    Batch,
    Center,
    Student,
    StudentDashboardSnapshot,
    TeacherTodaySnapshot,
)
from app.services.observability_counters import clear_observability_events, count_observability_events
from app.services.snapshot_rebuild_service import rebuild_snapshots_for_center


class SnapshotRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_snapshot_rebuild.db'
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
            clear_observability_events()
            for table in (
                StudentDashboardSnapshot,
                TeacherTodaySnapshot,
                AdminOpsSnapshot,
                Student,
                Batch,
                AuthUser,
                Center,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def test_snapshot_rebuild_heals_drift(self):
        db = self._session_factory()
        try:
            today = datetime.utcnow().date()
            db.add(Center(id=1, name='Center A', slug='center-a'))
            db.add(Batch(id=101, name='Batch A', subject='Math', academic_level='', start_time='09:00', center_id=1))
            db.add(AuthUser(id=11, phone='9000000001', role='teacher', center_id=1))
            db.add(Student(id=21, name='Student A', guardian_phone='9999999999', batch_id=101, center_id=1))
            db.commit()

            corrupted = json.dumps({'corrupted': True})
            db.add(TeacherTodaySnapshot(teacher_id=11, date=today, data_json=corrupted, updated_at=datetime.utcnow()))
            db.add(StudentDashboardSnapshot(student_id=21, date=today, data_json=corrupted, updated_at=datetime.utcnow()))
            db.add(AdminOpsSnapshot(center_id=1, date=today, data_json=corrupted, updated_at=datetime.utcnow()))
            db.commit()

            summary = rebuild_snapshots_for_center(db, center_id=1, day=today)
            self.assertGreaterEqual(int(summary.get('healed_count') or 0), 3)

            teacher_row = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 11, TeacherTodaySnapshot.date == today).first()
            student_row = db.query(StudentDashboardSnapshot).filter(StudentDashboardSnapshot.student_id == 21, StudentDashboardSnapshot.date == today).first()
            admin_row = (
                db.query(AdminOpsSnapshot)
                .filter(AdminOpsSnapshot.center_id == 1, AdminOpsSnapshot.date == today)
                .first()
            )
            self.assertIsNotNone(teacher_row)
            self.assertIsNotNone(student_row)
            self.assertIsNotNone(admin_row)
            self.assertNotEqual(teacher_row.data_json, corrupted)
            self.assertNotEqual(student_row.data_json, corrupted)
            self.assertNotEqual(admin_row.data_json, corrupted)

            self.assertGreaterEqual(count_observability_events('snapshot_drift', window_hours=24), 3)
            self.assertEqual(count_observability_events('snapshot_rebuild_run', window_hours=24), 1)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
