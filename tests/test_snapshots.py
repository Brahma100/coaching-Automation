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
    Center,
    Role,
    Student,
    StudentBatchMap,
    StudentDashboardSnapshot,
    TeacherBatchMap,
    TeacherTodaySnapshot,
)
from app.routers import admin_ops, attendance_session_api, dashboard_today, student_api
from app.services.snapshot_rebuild_service import rebuild_snapshots_for_center
from app.services import allowlist_admin_service, auth_service, student_portal_service
from app.core import attendance_guards


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
                return {'sub': 1, 'user_id': 1, 'phone': '9990000001', 'role': Role.TEACHER.value, 'center_id': 1}
            if token == 'token-admin':
                return {'sub': 2, 'user_id': 2, 'phone': '9000000009', 'role': Role.ADMIN.value, 'center_id': 1}
            if token == 'token-student':
                return {'sub': 3, 'phone': '9000000001', 'role': Role.STUDENT.value, 'center_id': 1}
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
                Center,
            ):
                db.query(table).delete()
            db.commit()

            # Seed identities for auth and snapshots.
            center = Center(id=1, name='Center A', slug='center-a', timezone='UTC')
            teacher = AuthUser(id=1, phone='9990000001', role=Role.TEACHER.value, center_id=1)
            admin = AuthUser(id=2, phone='9000000009', role=Role.ADMIN.value, center_id=1)
            student = Student(id=1, name='Student One', guardian_phone='9000000001', batch_id=1, center_id=1)
            allowed_admin = AllowedUser(phone='9000000009', role=Role.ADMIN.value, status=AllowedUserStatus.ACTIVE.value)
            db.add_all([center, teacher, admin, student, allowed_admin])
            db.commit()
        finally:
            db.close()

    def test_today_endpoint_is_pure_read(self):
        today = datetime.utcnow().date()
        resp1 = self.client.get('/api/dashboard/today', cookies={'auth_session': 'token-teacher'})
        self.assertEqual(resp1.status_code, 200)
        self.assertIsInstance(resp1.json(), dict)

        db = self._session_factory()
        try:
            row = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == today).first()
            self.assertIsNone(row)
            rebuild_snapshots_for_center(db, center_id=1, day=today)
            rebuilt_row = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == today).first()
            self.assertIsNotNone(rebuilt_row)
        finally:
            db.close()

    def test_admin_ops_endpoint_is_pure_read(self):
        today = datetime.utcnow().date()
        resp1 = self.client.get('/api/admin/ops-dashboard', headers={'Authorization': 'Bearer token-admin'})
        self.assertEqual(resp1.status_code, 200)
        self.assertIsInstance(resp1.json(), dict)

        db = self._session_factory()
        try:
            row = db.query(AdminOpsSnapshot).filter(AdminOpsSnapshot.center_id == 1, AdminOpsSnapshot.date == today).first()
            self.assertIsNone(row)
            rebuild_snapshots_for_center(db, center_id=1, day=today)
            rebuilt_row = db.query(AdminOpsSnapshot).filter(AdminOpsSnapshot.center_id == 1, AdminOpsSnapshot.date == today).first()
            self.assertIsNotNone(rebuilt_row)
        finally:
            db.close()

    def test_student_dashboard_endpoint_is_pure_read(self):
        today = datetime.utcnow().date()
        resp1 = self.client.get('/api/student/dashboard', headers={'Authorization': 'Bearer token-student'})
        self.assertEqual(resp1.status_code, 200)
        self.assertIsInstance(resp1.json(), dict)

        db = self._session_factory()
        try:
            row = (
                db.query(StudentDashboardSnapshot)
                .filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == today)
                .first()
            )
            self.assertIsNone(row)
            rebuild_snapshots_for_center(db, center_id=1, day=today)
            rebuilt_row = (
                db.query(StudentDashboardSnapshot)
                .filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == today)
                .first()
            )
            self.assertIsNotNone(rebuilt_row)
        finally:
            db.close()

    def test_snapshot_rebuild_creates_snapshot_rows(self):
        day = datetime.utcnow().date()
        db = self._session_factory()
        try:
            summary = rebuild_snapshots_for_center(db, center_id=1, day=day)
            self.assertGreaterEqual(int(summary.get('rebuilt_count') or 0), 1)
        finally:
            db.close()

        db = self._session_factory()
        try:
            teacher_row = (
                db.query(TeacherTodaySnapshot)
                .filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == day)
                .first()
            )
            student_row = (
                db.query(StudentDashboardSnapshot)
                .filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == day)
                .first()
            )
            admin_row = (
                db.query(AdminOpsSnapshot)
                .filter(AdminOpsSnapshot.center_id == 1, AdminOpsSnapshot.date == day)
                .first()
            )
            self.assertIsNotNone(teacher_row)
            self.assertIsNotNone(student_row)
            self.assertIsNotNone(admin_row)
        finally:
            db.close()


class SnapshotWriteTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_snapshots_writes.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate_attendance = attendance_session_api.validate_session_token
        cls._orig_validate_attendance_guard = attendance_guards.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'sub': 1, 'user_id': 1, 'phone': '9990000001', 'role': Role.TEACHER.value, 'center_id': 1}
            return None

        attendance_session_api.validate_session_token = fake_validate_session_token
        attendance_guards.validate_session_token = fake_validate_session_token

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
        attendance_guards.validate_session_token = cls._orig_validate_attendance_guard
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
                StudentBatchMap,
                TeacherBatchMap,
                AuthUser,
                Center,
            ):
                db.query(table).delete()
            db.commit()

            center = Center(id=1, name='Center A', slug='center-a', timezone='UTC')
            teacher = AuthUser(id=1, phone='9990000001', role=Role.TEACHER.value, center_id=1)
            batch = Batch(id=1, name='Batch A', subject='Math', academic_level='', active=True, start_time='09:00', center_id=1)
            schedule = BatchSchedule(batch_id=1, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60)
            session = ClassSession(
                id=1,
                batch_id=1,
                subject='Math',
                scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                duration_minutes=60,
                status='open',
                teacher_id=1,
                center_id=1,
            )
            s1 = Student(id=1, name='Student One', guardian_phone='9000000001', batch_id=1, center_id=1)
            s2 = Student(id=2, name='Student Two', guardian_phone='9000000002', batch_id=1, center_id=1)
            teacher_map = TeacherBatchMap(teacher_id=1, batch_id=1, is_primary=True, center_id=1)
            student_map_1 = StudentBatchMap(student_id=1, batch_id=1, active=True)
            student_map_2 = StudentBatchMap(student_id=2, batch_id=1, active=True)
            db.add_all([center, teacher, batch, schedule, session, s1, s2, teacher_map, student_map_1, student_map_2])
            db.commit()
        finally:
            db.close()

    def test_snapshots_created_after_attendance_submit_and_rebuild(self):
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
            rebuild_snapshots_for_center(db, center_id=1, day=today)

            teacher_snapshot = db.query(TeacherTodaySnapshot).filter(TeacherTodaySnapshot.teacher_id == 1, TeacherTodaySnapshot.date == today).first()
            student_1 = db.query(StudentDashboardSnapshot).filter(StudentDashboardSnapshot.student_id == 1, StudentDashboardSnapshot.date == today).first()
            student_2 = db.query(StudentDashboardSnapshot).filter(StudentDashboardSnapshot.student_id == 2, StudentDashboardSnapshot.date == today).first()
            self.assertIsNotNone(teacher_snapshot)
            self.assertIsNotNone(student_1)
            self.assertIsNotNone(student_2)
        finally:
            db.close()
