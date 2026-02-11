import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache, cache_key
from app.db import Base, get_db
from app.models import (
    AdminOpsSnapshot,
    AllowedUser,
    AllowedUserStatus,
    AttendanceRecord,
    AuthUser,
    Batch,
    BatchSchedule,
    ClassSession,
    Role,
    Student,
    StudentDashboardSnapshot,
    TeacherTodaySnapshot,
)
from app.routers import admin_ops, attendance_session_api, dashboard_today, student_api
from app.services import allowlist_admin_service, auth_service, student_portal_service


class SnapshotReadPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_snapshots_read.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate_router = dashboard_today.validate_session_token
        cls._orig_validate_admin = allowlist_admin_service.validate_session_token
        cls._orig_validate_student = student_portal_service.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'sub': 1, 'user_id': 1, 'phone': '9990000001', 'role': Role.TEACHER.value}
            if token == 'token-admin':
                return {'sub': 2, 'user_id': 2, 'phone': '9000000009', 'role': Role.ADMIN.value}
            if token == 'token-student':
                return {'sub': 3, 'phone': '9000000001', 'role': Role.STUDENT.value}
            return None

        dashboard_today.validate_session_token = fake_validate_session_token
        allowlist_admin_service.validate_session_token = fake_validate_session_token
        student_portal_service.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(dashboard_today.router)
        app.include_router(admin_ops.router)
        app.include_router(student_api.router)

        def override_get_db():
            db = cls._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        dashboard_today.validate_session_token = cls._orig_validate_router
        allowlist_admin_service.validate_session_token = cls._orig_validate_admin
        student_portal_service.validate_session_token = cls._orig_validate_student
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            cache.invalidate_prefix('today_view')
            cache.invalidate('admin_ops')
            cache.invalidate_prefix('student_dashboard')
            for table in (
                AdminOpsSnapshot,
                TeacherTodaySnapshot,
                StudentDashboardSnapshot,
                AllowedUser,
                Student,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()

            # Seed identities for auth and snapshots.
            teacher = AuthUser(id=1, phone='9990000001', role=Role.TEACHER.value)
            admin = AuthUser(id=2, phone='9000000009', role=Role.ADMIN.value)
            student = Student(id=1, name='Student One', guardian_phone='9000000001', batch_id=1)
            allowed_admin = AllowedUser(phone='9000000009', role=Role.ADMIN.value, status=AllowedUserStatus.ACTIVE.value)
            db.add_all([teacher, admin, student, allowed_admin])
            db.commit()
        finally:
            db.close()

    def test_today_endpoint_uses_snapshot_after_first_compute(self):
        # First hit: compute + upsert snapshot.
        resp1 = self.client.get('/api/dashboard/today', cookies={'auth_session': 'token-teacher'})
        self.assertEqual(resp1.status_code, 200)

        db = self._session_factory()
        try:
            row = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == datetime.utcnow().date()).first()
            self.assertIsNotNone(row)
        finally:
            db.close()

        # Second hit: invalidate memory cache, then ensure we can serve from DB snapshot even if compute breaks.
        cache.invalidate_prefix('today_view')
        original = dashboard_today.get_today_view
        try:
            dashboard_today.get_today_view = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom'))
            resp2 = self.client.get('/api/dashboard/today', cookies={'auth_session': 'token-teacher'})
            self.assertEqual(resp2.status_code, 200)
        finally:
            dashboard_today.get_today_view = original

    def test_admin_ops_endpoint_uses_snapshot_after_first_compute(self):
        resp1 = self.client.get('/api/admin/ops-dashboard', headers={'Authorization': 'Bearer token-admin'})
        self.assertEqual(resp1.status_code, 200)

        db = self._session_factory()
        try:
            row = db.query(AdminOpsSnapshot).filter(AdminOpsSnapshot.date == datetime.utcnow().date()).first()
            self.assertIsNotNone(row)
        finally:
            db.close()

        cache.invalidate('admin_ops')
        original = admin_ops.get_admin_ops_dashboard
        try:
            admin_ops.get_admin_ops_dashboard = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom'))
            resp2 = self.client.get('/api/admin/ops-dashboard', headers={'Authorization': 'Bearer token-admin'})
            self.assertEqual(resp2.status_code, 200)
        finally:
            admin_ops.get_admin_ops_dashboard = original

    def test_student_dashboard_endpoint_uses_snapshot_after_first_compute(self):
        resp1 = self.client.get('/api/student/dashboard', headers={'Authorization': 'Bearer token-student'})
        self.assertEqual(resp1.status_code, 200)

        db = self._session_factory()
        try:
            row = (
                db.query(StudentDashboardSnapshot)
                .filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == datetime.utcnow().date())
                .first()
            )
            self.assertIsNotNone(row)
        finally:
            db.close()

        cache.invalidate(cache_key('student_dashboard', 1))
        original = student_api.get_student_dashboard
        try:
            student_api.get_student_dashboard = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom'))
            resp2 = self.client.get('/api/student/dashboard', headers={'Authorization': 'Bearer token-student'})
            self.assertEqual(resp2.status_code, 200)
        finally:
            student_api.get_student_dashboard = original


class SnapshotWriteTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_snapshots_writes.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate_attendance = attendance_session_api.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'sub': 1, 'user_id': 1, 'phone': '9990000001', 'role': Role.TEACHER.value}
            return None

        attendance_session_api.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(attendance_session_api.router)

        def override_get_db():
            db = cls._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        attendance_session_api.validate_session_token = cls._orig_validate_attendance
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            cache.invalidate_prefix('today_view')
            cache.invalidate_prefix('student_dashboard')
            for table in (
                TeacherTodaySnapshot,
                StudentDashboardSnapshot,
                AttendanceRecord,
                ClassSession,
                BatchSchedule,
                Batch,
                Student,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()

            teacher = AuthUser(id=1, phone='9990000001', role=Role.TEACHER.value)
            batch = Batch(id=1, name='Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
            schedule = BatchSchedule(batch_id=1, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60)
            session = ClassSession(
                id=1,
                batch_id=1,
                subject='Math',
                scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                duration_minutes=60,
                status='open',
                teacher_id=1,
            )
            s1 = Student(id=1, name='Student One', guardian_phone='9000000001', batch_id=1)
            s2 = Student(id=2, name='Student Two', guardian_phone='9000000002', batch_id=1)
            db.add_all([teacher, batch, schedule, session, s1, s2])
            db.commit()
        finally:
            db.close()

    def test_snapshots_created_after_attendance_submit(self):
        payload = {
            'records': [
                {'student_id': 1, 'status': 'Present', 'comment': ''},
                {'student_id': 2, 'status': 'Absent', 'comment': ''},
            ]
        }
        resp = self.client.post('/api/attendance/session/1/submit', json=payload, cookies={'auth_session': 'token-teacher'})
        self.assertEqual(resp.status_code, 200)

        db = self._session_factory()
        try:
            today = datetime.utcnow().date()
            teacher_snapshot = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == today).first()
            self.assertIsNotNone(teacher_snapshot)
            student_1 = db.query(StudentDashboardSnapshot).filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == today).first()
            student_2 = db.query(StudentDashboardSnapshot).filter(StudentDashboardSnapshot.student_id == 2, StudentDashboardSnapshot.date == today).first()
            self.assertIsNotNone(student_1)
            self.assertIsNotNone(student_2)
        finally:
            db.close()
