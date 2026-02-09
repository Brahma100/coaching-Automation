import json
import logging
import time
from datetime import date, datetime, timedelta

from sqlalchemy import and_, inspect, text
from sqlalchemy.orm import Session

from app.models import (
    AttendanceRecord,
    FeeRecord,
    Homework,
    HomeworkSubmission,
    PendingAction,
    Student,
    StudentBatchMap,
    StudentRiskEvent,
    StudentRiskProfile,
)
from app.services.pending_action_service import create_pending_action


logger = logging.getLogger(__name__)

WINDOW_ATTENDANCE = 20
WINDOW_HOMEWORK = 10
FEE_OVERDUE_MONTHS_2_DAYS = 60

WEIGHT_ATTENDANCE = 0.40
WEIGHT_HOMEWORK = 0.30
WEIGHT_FEE = 0.20
WEIGHT_TESTS = 0.10


def clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def risk_level_from_score(score: float) -> str:
    if score >= 75:
        return 'LOW'
    if score >= 50:
        return 'MEDIUM'
    return 'HIGH'


def compute_attendance_score(records: list[AttendanceRecord]) -> tuple[float, dict]:
    if not records:
        return 1.0, {'attendance_percentage': 1.0, 'sample_size': 0}
    present_count = sum(1 for row in records if (row.status or '').lower() == 'present')
    ratio = present_count / len(records)
    return clamp_01(ratio), {'attendance_percentage': round(ratio, 4), 'sample_size': len(records)}


def compute_homework_score(assigned_count: int, submitted_count: int) -> tuple[float, dict]:
    if assigned_count <= 0:
        return 1.0, {'assigned_count': 0, 'submitted_count': 0, 'submission_ratio': 1.0}
    ratio = submitted_count / assigned_count
    return clamp_01(ratio), {
        'assigned_count': assigned_count,
        'submitted_count': submitted_count,
        'submission_ratio': round(clamp_01(ratio), 4),
    }


def compute_fee_score(overdue_days: int | None) -> tuple[float, dict]:
    if overdue_days is None or overdue_days <= 0:
        return 1.0, {'max_overdue_days': max(0, overdue_days or 0)}
    if overdue_days >= FEE_OVERDUE_MONTHS_2_DAYS:
        return 0.0, {'max_overdue_days': overdue_days}
    return 0.5, {'max_overdue_days': overdue_days}


def compute_test_score(last_two_marks: list[float]) -> tuple[float | None, dict]:
    if len(last_two_marks) < 2:
        return None, {'marks_available': len(last_two_marks), 'trend': 'no-data'}
    previous_mark, latest_mark = last_two_marks[0], last_two_marks[1]
    if previous_mark <= 0:
        normalized = 0.5
    else:
        delta = (latest_mark - previous_mark) / previous_mark
        normalized = clamp_01(0.5 + (delta / 2.0))
    trend = 'improving' if latest_mark > previous_mark else 'declining' if latest_mark < previous_mark else 'flat'
    return normalized, {'marks_available': 2, 'trend': trend, 'latest_mark': latest_mark, 'previous_mark': previous_mark}


def combine_scores(attendance_score: float, homework_score: float, fee_score: float, test_score: float | None) -> float:
    if test_score is None:
        total = (
            attendance_score * WEIGHT_ATTENDANCE
            + homework_score * WEIGHT_HOMEWORK
            + fee_score * WEIGHT_FEE
        )
        max_without_tests = WEIGHT_ATTENDANCE + WEIGHT_HOMEWORK + WEIGHT_FEE
        return round((total / max_without_tests) * 100.0, 2)
    total = (
        attendance_score * WEIGHT_ATTENDANCE
        + homework_score * WEIGHT_HOMEWORK
        + fee_score * WEIGHT_FEE
        + test_score * WEIGHT_TESTS
    )
    return round(total * 100.0, 2)


def _load_test_marks_if_available(db: Session, student_id: int) -> list[float]:
    inspector = inspect(db.bind)
    if 'test_marks' not in inspector.get_table_names():
        return []
    columns = {col['name'] for col in inspector.get_columns('test_marks')}
    if not {'student_id', 'marks'}.issubset(columns):
        return []

    if 'taken_at' in columns:
        sql = text('SELECT marks FROM test_marks WHERE student_id = :student_id ORDER BY taken_at DESC LIMIT 2')
    elif 'created_at' in columns:
        sql = text('SELECT marks FROM test_marks WHERE student_id = :student_id ORDER BY created_at DESC LIMIT 2')
    else:
        sql = text('SELECT marks FROM test_marks WHERE student_id = :student_id ORDER BY id DESC LIMIT 2')

    rows = db.execute(sql, {'student_id': student_id}).fetchall()
    return [float(row[0]) for row in rows if row and row[0] is not None][::-1]


def _short_reason(risk_level: str, details: dict) -> str:
    attendance_pct = int(round((details.get('attendance', {}).get('attendance_percentage', 0.0)) * 100))
    homework_pct = int(round((details.get('homework', {}).get('submission_ratio', 0.0)) * 100))
    overdue_days = int(details.get('fees', {}).get('max_overdue_days', 0))
    return (
        f'Risk {risk_level}: attendance {attendance_pct}%, '
        f'homework {homework_pct}%, max fee overdue {overdue_days} days.'
    )


def compute_student_risk(db: Session, student: Student) -> dict:
    attendance_rows = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.student_id == student.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())
        .limit(WINDOW_ATTENDANCE)
        .all()
    )
    attendance_score, attendance_details = compute_attendance_score(attendance_rows)

    assigned_homework_ids = [
        row[0]
        for row in (
            db.query(Homework.id)
            .order_by(Homework.due_date.desc(), Homework.id.desc())
            .limit(WINDOW_HOMEWORK)
            .all()
        )
    ]
    assigned_count = len(assigned_homework_ids)
    submitted_count = 0
    if assigned_homework_ids:
        submitted_count = (
            db.query(HomeworkSubmission)
            .filter(
                HomeworkSubmission.student_id == student.id,
                HomeworkSubmission.homework_id.in_(assigned_homework_ids),
            )
            .count()
        )
    homework_score, homework_details = compute_homework_score(assigned_count, submitted_count)

    today = date.today()
    unpaid_rows = db.query(FeeRecord).filter(FeeRecord.student_id == student.id, FeeRecord.is_paid.is_(False)).all()
    max_overdue_days = 0
    for fee in unpaid_rows:
        overdue_days = (today - fee.due_date).days
        if overdue_days > max_overdue_days:
            max_overdue_days = overdue_days
    fee_score, fee_details = compute_fee_score(max_overdue_days if unpaid_rows else None)

    test_marks = _load_test_marks_if_available(db, student.id)
    test_score, test_details = compute_test_score(test_marks)

    final_score = combine_scores(attendance_score, homework_score, fee_score, test_score)
    risk_level = risk_level_from_score(final_score)

    details = {
        'attendance': attendance_details,
        'homework': homework_details,
        'fees': fee_details,
        'tests': test_details,
        'weights': {
            'attendance': WEIGHT_ATTENDANCE,
            'homework': WEIGHT_HOMEWORK,
            'fees': WEIGHT_FEE,
            'tests': WEIGHT_TESTS,
        },
        'computed_at': datetime.utcnow().isoformat(),
    }
    reason_summary = _short_reason(risk_level, details)

    return {
        'student_id': student.id,
        'attendance_score': round(attendance_score, 4),
        'homework_score': round(homework_score, 4),
        'fee_score': round(fee_score, 4),
        'test_score': round(test_score, 4) if test_score is not None else None,
        'final_risk_score': final_score,
        'risk_level': risk_level,
        'reason_summary': reason_summary,
        'reasons': details,
    }


def recompute_student_risk(db: Session, student: Student) -> dict:
    payload = compute_student_risk(db, student)
    now = datetime.utcnow()

    profile = db.query(StudentRiskProfile).filter(StudentRiskProfile.student_id == student.id).first()
    previous_level = profile.risk_level if profile else None

    if not profile:
        profile = StudentRiskProfile(student_id=student.id)
        db.add(profile)

    profile.attendance_score = payload['attendance_score']
    profile.homework_score = payload['homework_score']
    profile.fee_score = payload['fee_score']
    profile.test_score = payload['test_score']
    profile.final_risk_score = payload['final_risk_score']
    profile.risk_level = payload['risk_level']
    profile.last_computed_at = now
    db.flush()

    if previous_level != payload['risk_level']:
        db.add(
            StudentRiskEvent(
                student_id=student.id,
                previous_risk_level=previous_level,
                new_risk_level=payload['risk_level'],
                reason_json=json.dumps(payload['reasons']),
                created_at=now,
            )
        )
        if payload['risk_level'] == 'HIGH':
            existing_open = db.query(PendingAction).filter(
                PendingAction.type == 'student_risk',
                PendingAction.student_id == student.id,
                PendingAction.status == 'open',
            ).first()
            if not existing_open:
                create_pending_action(
                    db,
                    action_type='student_risk',
                    student_id=student.id,
                    related_session_id=None,
                    note=payload['reason_summary'],
                )
    db.commit()
    return payload


def recompute_all_student_risk(db: Session) -> dict:
    started = time.perf_counter()
    students = db.query(Student).order_by(Student.id.asc()).all()
    high_count = 0
    medium_count = 0
    low_count = 0

    for student in students:
        result = recompute_student_risk(db, student)
        if result['risk_level'] == 'HIGH':
            high_count += 1
        elif result['risk_level'] == 'MEDIUM':
            medium_count += 1
        else:
            low_count += 1

    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    logger.info(
        'student_risk_recompute_done',
        extra={
            'students': len(students),
            'high': high_count,
            'medium': medium_count,
            'low': low_count,
            'duration_ms': duration_ms,
        },
    )
    return {
        'students': len(students),
        'high': high_count,
        'medium': medium_count,
        'low': low_count,
        'duration_ms': duration_ms,
    }


def list_student_risk_profiles(db: Session, batch_id: int | None = None) -> list[dict]:
    query = db.query(StudentRiskProfile, Student).join(Student, StudentRiskProfile.student_id == Student.id)
    if batch_id is not None:
        query = query.join(
            StudentBatchMap,
            and_(
                StudentBatchMap.student_id == Student.id,
                StudentBatchMap.batch_id == batch_id,
                StudentBatchMap.active.is_(True),
            ),
        )
    rows = query.order_by(StudentRiskProfile.final_risk_score.asc(), Student.id.asc()).all()
    notes_by_student = {
        row.student_id: row.note
        for row in db.query(PendingAction)
        .filter(PendingAction.type == 'student_risk', PendingAction.status == 'open')
        .all()
    }
    return [
        {
            'student_id': student.id,
            'student_name': student.name,
            'batch_id': student.batch_id,
            'batch_name': student.batch.name if student.batch else '',
            'risk_level': profile.risk_level,
            'final_risk_score': round(profile.final_risk_score, 2),
            'reason_summary': notes_by_student.get(student.id, ''),
            'attendance_score': round(profile.attendance_score, 4),
            'homework_score': round(profile.homework_score, 4),
            'fee_score': round(profile.fee_score, 4),
            'test_score': round(profile.test_score, 4) if profile.test_score is not None else None,
            'last_computed_at': profile.last_computed_at.isoformat() if profile.last_computed_at else None,
        }
        for profile, student in rows
    ]


def get_student_risk_detail(db: Session, student_id: int) -> dict | None:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return None

    profile = db.query(StudentRiskProfile).filter(StudentRiskProfile.student_id == student_id).first()
    if not profile:
        # No profile yet: compute a non-persistent preview for explainability.
        preview = compute_student_risk(db, student)
        return {
            'student_id': student.id,
            'student_name': student.name,
            'batch_id': student.batch_id,
            'risk_level': preview['risk_level'],
            'final_risk_score': preview['final_risk_score'],
            'attendance_score': preview['attendance_score'],
            'homework_score': preview['homework_score'],
            'fee_score': preview['fee_score'],
            'test_score': preview['test_score'],
            'reasons': preview['reasons'],
            'reason_summary': preview['reason_summary'],
        }

    latest_event = (
        db.query(StudentRiskEvent)
        .filter(StudentRiskEvent.student_id == student_id)
        .order_by(StudentRiskEvent.created_at.desc(), StudentRiskEvent.id.desc())
        .first()
    )
    reasons = {}
    if latest_event and latest_event.reason_json:
        try:
            reasons = json.loads(latest_event.reason_json)
        except json.JSONDecodeError:
            reasons = {}

    # If reasons are unavailable, generate a read-only preview breakdown.
    if not reasons:
        reasons = compute_student_risk(db, student)['reasons']

    return {
        'student_id': student.id,
        'student_name': student.name,
        'batch_id': student.batch_id,
        'risk_level': profile.risk_level,
        'final_risk_score': round(profile.final_risk_score, 2),
        'attendance_score': round(profile.attendance_score, 4),
        'homework_score': round(profile.homework_score, 4),
        'fee_score': round(profile.fee_score, 4),
        'test_score': round(profile.test_score, 4) if profile.test_score is not None else None,
        'last_computed_at': profile.last_computed_at.isoformat() if profile.last_computed_at else None,
        'reasons': reasons,
        'reason_summary': _short_reason(profile.risk_level, reasons),
    }
