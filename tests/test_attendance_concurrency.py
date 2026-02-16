import tempfile
import threading
import unittest
from datetime import datetime, timedelta
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AttendanceRecord, Batch, ClassSession, Student
import app.services.attendance_auto_close_job as auto_close_module
import app.services.attendance_service as attendance_module


class AttendanceConcurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_attendance_concurrency.db'
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
            db.query(AttendanceRecord).delete()
            db.query(ClassSession).delete()
            db.query(Student).delete()
            db.query(Batch).delete()
            batch = Batch(name='RaceBatch', start_time='08:00', subject='Math', active=True, center_id=1)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            db.add_all(
                [
                    Student(name='S1', guardian_phone='9111111111', batch_id=batch.id, center_id=1),
                    Student(name='S2', guardian_phone='9222222222', batch_id=batch.id, center_id=1),
                ]
            )
            session = ClassSession(
                batch_id=batch.id,
                subject='Math',
                scheduled_start=datetime.utcnow() - timedelta(hours=2),
                duration_minutes=60,
                teacher_id=10,
                center_id=1,
                status='open',
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            self.batch_id = int(batch.id)
            self.session_id = int(session.id)
            self.student_ids = [row.id for row in db.query(Student).order_by(Student.id.asc()).all()]
        finally:
            db.close()

    def test_submit_and_auto_close_only_process_pipeline_once(self):
        pipeline_count = {'count': 0}
        count_lock = threading.Lock()

        original_submit_pipeline = attendance_module.run_post_class_pipeline
        original_autoclose_pipeline = auto_close_module.run_post_class_pipeline
        original_submit_automation = attendance_module.run_post_class_automation
        original_autoclose_automation = auto_close_module.run_post_class_automation

        def fake_pipeline(*args, **kwargs):
            with count_lock:
                pipeline_count['count'] += 1
            return {
                'class_summary': {'class_session_id': self.session_id},
                'teacher_notifications': [],
                'student_notifications': 2,
                'parent_notifications_rules_applied': True,
                'pending_action_ids': [],
                'rules': {},
            }

        def fake_automation(*args, **kwargs):
            return {'ok': True}

        attendance_module.run_post_class_pipeline = fake_pipeline
        auto_close_module.run_post_class_pipeline = fake_pipeline
        attendance_module.run_post_class_automation = fake_automation
        auto_close_module.run_post_class_automation = fake_automation

        submit_error = []
        close_error = []
        barrier = threading.Barrier(2)

        def submit_worker():
            db = self._session_factory()
            try:
                barrier.wait(timeout=5)
                attendance_module.submit_attendance(
                    db=db,
                    batch_id=self.batch_id,
                    attendance_date=datetime.utcnow().date(),
                    records=[
                        {'student_id': self.student_ids[0], 'status': 'Present', 'comment': ''},
                        {'student_id': self.student_ids[1], 'status': 'Absent', 'comment': ''},
                    ],
                    subject='Math',
                    teacher_id=10,
                    class_session_id=self.session_id,
                    actor_role='teacher',
                    actor_user_id=10,
                )
            except Exception as exc:  # pragma: no cover - test diagnostic path
                submit_error.append(exc)
            finally:
                db.close()

        def close_worker():
            db = self._session_factory()
            try:
                barrier.wait(timeout=5)
                time.sleep(0.05)
                auto_close_module.auto_close_attendance_sessions(db, grace_minutes=0, center_id=1)
            except Exception as exc:  # pragma: no cover - test diagnostic path
                close_error.append(exc)
            finally:
                db.close()

        t1 = threading.Thread(target=submit_worker)
        t2 = threading.Thread(target=close_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        attendance_module.run_post_class_pipeline = original_submit_pipeline
        auto_close_module.run_post_class_pipeline = original_autoclose_pipeline
        attendance_module.run_post_class_automation = original_submit_automation
        auto_close_module.run_post_class_automation = original_autoclose_automation

        self.assertFalse(submit_error, f'submit_error={submit_error}')
        self.assertFalse(close_error, f'close_error={close_error}')
        self.assertEqual(pipeline_count['count'], 1)

        db = self._session_factory()
        try:
            records = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.attendance_date == datetime.utcnow().date(),
                    AttendanceRecord.student_id.in_(self.student_ids),
                )
                .all()
            )
            self.assertEqual(len(records), 2)
            session_row = db.query(ClassSession).filter(ClassSession.id == self.session_id).first()
            self.assertIsNotNone(session_row.post_class_processed_at)
            self.assertIn(session_row.status, ('submitted', 'closed'))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
