import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.services.system_health_service import get_system_health
from app.models import AutomationFailureLog, AuthUser, Center, ClassSession, CommunicationLog
from app.services.observability_counters import clear_observability_events, record_observability_event


class SystemHealthServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_system_health.db'
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
            for table in (AutomationFailureLog, CommunicationLog, ClassSession, AuthUser, Center):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def test_system_health_aggregation_center_scoped(self):
        db = self._session_factory()
        now = datetime(2026, 2, 16, 9, 0, 0)
        try:
            db.add_all(
                [
                    Center(id=1, name='Center A', slug='center-a'),
                    Center(id=2, name='Center B', slug='center-b'),
                ]
            )
            db.flush()

            t1 = AuthUser(phone='9000000001', role='teacher', center_id=1)
            t2 = AuthUser(phone='9000000002', role='teacher', center_id=2)
            db.add_all([t1, t2])
            db.flush()

            db.add(
                ClassSession(
                    batch_id=101,
                    center_id=1,
                    subject='Math',
                    scheduled_start=now - timedelta(hours=2),
                    duration_minutes=60,
                    status='closed',
                    teacher_id=t1.id,
                    post_class_error=True,
                )
            )

            db.add_all(
                [
                    CommunicationLog(
                        teacher_id=t1.id,
                        channel='telegram',
                        message='failed-retry',
                        status='failed',
                        event_type='inbox_escalation',
                        reference_id=11,
                        delivery_status='failed',
                        delivery_attempts=2,
                        last_attempt_at=now - timedelta(minutes=10),
                        created_at=now - timedelta(hours=1),
                    ),
                    CommunicationLog(
                        teacher_id=t1.id,
                        channel='telegram',
                        message='perm-failed',
                        status='failed',
                        event_type='post_class_summary',
                        reference_id=12,
                        delivery_status='permanently_failed',
                        delivery_attempts=3,
                        last_attempt_at=now - timedelta(minutes=20),
                        created_at=now - timedelta(hours=2),
                    ),
                    CommunicationLog(
                        teacher_id=t1.id,
                        channel='telegram',
                        message='old-failed',
                        status='failed',
                        event_type='daily_brief',
                        reference_id=13,
                        delivery_status='failed',
                        delivery_attempts=3,
                        last_attempt_at=now - timedelta(hours=30),
                        created_at=now - timedelta(hours=30),
                    ),
                    CommunicationLog(
                        teacher_id=t2.id,
                        channel='telegram',
                        message='other-center',
                        status='failed',
                        event_type='daily_brief',
                        reference_id=14,
                        delivery_status='failed',
                        delivery_attempts=2,
                        last_attempt_at=now - timedelta(minutes=10),
                        created_at=now - timedelta(hours=2),
                    ),
                ]
            )

            db.add_all(
                [
                    AutomationFailureLog(
                        center_id=1,
                        job_name='inbox_escalation',
                        entity_type='pending_action',
                        entity_id=11,
                        error_message='delivery retries exhausted',
                        created_at=now - timedelta(hours=1),
                    ),
                    AutomationFailureLog(
                        center_id=1,
                        job_name='post_class_pipeline',
                        entity_type='class_session',
                        entity_id=51,
                        error_message='pipeline exception',
                        created_at=now - timedelta(hours=40),
                    ),
                    AutomationFailureLog(
                        center_id=2,
                        job_name='inbox_escalation',
                        entity_type='pending_action',
                        entity_id=12,
                        error_message='delivery retries exhausted',
                        created_at=now - timedelta(hours=1),
                    ),
                ]
            )
            db.commit()

            record_observability_event('cache_center_mismatch', at=now - timedelta(hours=1))
            record_observability_event('job_lock_skipped', at=now - timedelta(minutes=30))
            record_observability_event('rate_limit_block', at=now - timedelta(minutes=15))
            record_observability_event('snapshot_drift', at=now - timedelta(minutes=10))
            record_observability_event('snapshot_rebuild_run', at=now - timedelta(minutes=5))

            health = get_system_health(db, center_id=1, now=now)
            self.assertEqual(health['failed_communications_last_24h'], 1)
            self.assertEqual(health['permanently_failed_communications'], 1)
            self.assertEqual(health['post_class_error_sessions'], 1)
            self.assertEqual(health['automation_failure_count_24h'], 1)
            self.assertEqual(health['retry_backlog_count'], 1)
            self.assertEqual(health['dead_letter_count'], 2)
            self.assertEqual(health['cache_center_mismatch_count_last_24h'], 1)
            self.assertEqual(health['job_lock_skipped_count_last_24h'], 1)
            self.assertEqual(health['rate_limit_blocks_last_24h'], 1)
            self.assertEqual(health['snapshot_drift_last_24h'], 1)
            self.assertEqual(health['snapshot_rebuild_runs_last_24h'], 1)
            self.assertEqual(health['health_status'], 'degraded')
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
