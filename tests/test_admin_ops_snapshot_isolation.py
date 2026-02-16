import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AdminOpsSnapshot, Center
from app.services.center_scope_service import center_context
from app.services.snapshot_service import get_admin_ops_snapshot, upsert_admin_ops_snapshot


class AdminOpsSnapshotIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_admin_ops_snapshot_isolation.db'
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
            db.query(AdminOpsSnapshot).delete()
            db.query(Center).delete()
            db.add_all(
                [
                    Center(id=1, name='Center A', slug='center-a', timezone='UTC'),
                    Center(id=2, name='Center B', slug='center-b', timezone='UTC'),
                ]
            )
            db.commit()
        finally:
            db.close()

    def test_same_day_snapshots_are_isolated_per_center(self):
        day = datetime.utcnow().date()
        payload_a = {'center_id': 1, 'metric': 'a'}
        payload_b = {'center_id': 2, 'metric': 'b'}

        db = self._session_factory()
        try:
            with center_context(1):
                upsert_admin_ops_snapshot(db, day=day, payload=payload_a)
            with center_context(2):
                upsert_admin_ops_snapshot(db, day=day, payload=payload_b)
        finally:
            db.close()

        db = self._session_factory()
        try:
            rows = db.query(AdminOpsSnapshot).filter(AdminOpsSnapshot.date == day).all()
            self.assertEqual(len(rows), 2)

            with center_context(1):
                loaded_a = get_admin_ops_snapshot(db, day=day)
            with center_context(2):
                loaded_b = get_admin_ops_snapshot(db, day=day)

            self.assertEqual(loaded_a.get('metric'), 'a')
            self.assertEqual(loaded_b.get('metric'), 'b')
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
