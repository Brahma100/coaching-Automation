from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import (
    AttendanceRecord,
    Batch,
    BatchSchedule,
    ClassSession,
    FeeRecord,
    Homework,
    HomeworkSubmission,
    AllowedUser,
    AllowedUserStatus,
    AuthUser,
    Parent,
    PendingAction,
    ReferralCode,
    Room,
    Student,
    StudentBatchMap,
    StudentRiskProfile,
    Role,
)
from app.services.attendance_service import submit_attendance
from app.services.class_session_service import create_class_session
from app.services.fee_service import build_upi_link, mark_fee_paid
from app.services.homework_service import create_homework, submit_homework
from app.services.parent_service import create_parent, link_parent_student
from app.services.pending_action_service import create_pending_action
from app.services.referral_service import create_referral_code
from app.services.student_risk_service import recompute_all_student_risk


RNG = random.Random(20260209)

ROOM_BLUEPRINTS = [
    {'name': 'Orion Lab', 'capacity': 24, 'color_code': '#60a5fa'},
    {'name': 'Nova Studio', 'capacity': 28, 'color_code': '#34d399'},
    {'name': 'Zen Room', 'capacity': 20, 'color_code': '#f97316'},
]

BATCH_BLUEPRINTS = [
    {
        'name': 'Physics_9',
        'start_time': '08:00',
        'subject': 'Physics',
        'academic_level': 'Grade 9',
        'color_code': '#60a5fa',
        'duration_minutes': 60,
        'room': 'Orion Lab',
        'location': 'Block A - 2F',
        'max_students': 30,
        'is_online': False,
        'meeting_link': '',
    },
    {
        'name': 'Chemistry_10',
        'start_time': '09:30',
        'subject': 'Chemistry',
        'academic_level': 'Grade 10',
        'color_code': '#34d399',
        'duration_minutes': 60,
        'room': 'Nova Studio',
        'location': 'Block B - 1F',
        'max_students': 28,
        'is_online': False,
        'meeting_link': '',
    },
    {
        'name': 'Maths_12',
        'start_time': '16:00',
        'subject': 'Mathematics',
        'academic_level': 'Grade 12',
        'color_code': '#f97316',
        'duration_minutes': 75,
        'room': 'Zen Room',
        'location': 'Block C - 3F',
        'max_students': 24,
        'is_online': True,
        'meeting_link': 'https://meet.example.com/maths-12',
    },
]

SUBJECTS_BY_BATCH = {
    'Physics_9': ['Motion in a Straight Line', 'Light Reflection', 'Sound Waves', 'Work and Energy', 'Newton Laws'],
    'Chemistry_10': ['Acids and Bases', 'Metals and Non-metals', 'Carbon Compounds', 'Periodic Classification', 'Chemical Reactions'],
    'Maths_12': ['Differentiation', 'Application of Derivatives', 'Integrals', 'Matrices', 'Probability'],
}

ATTENDANCE_COMMENTS = ['Sick leave', 'Family function', 'Late arrival']
INDIAN_STUDENT_NAMES = [
    'Aarav Sharma', 'Vivaan Verma', 'Aditya Mehta', 'Ishaan Gupta', 'Krish Patel', 'Arjun Nair',
    'Sai Reddy', 'Rohan Kulkarni', 'Kabir Singh', 'Ayaan Khan', 'Yash Agarwal', 'Harsh Vora',
    'Pranav Joshi', 'Dhruv Bansal', 'Nikhil Rao', 'Ritvik Jain', 'Ananya Iyer', 'Diya Kapoor',
    'Myra Chawla', 'Saanvi Desai', 'Kiara Malhotra', 'Aadhya Menon', 'Pari Arora', 'Riya Sinha',
    'Nitya Pillai', 'Meera Mishra', 'Aanya Ghosh', 'Tara Saxena', 'Ira Dubey', 'Navya Tiwari',
    'Sneha Patil', 'Pooja Yadav', 'Suhani Bhatt', 'Tanvi Roy', 'Mitali Sen', 'Radhika Jha',
    'Shreya Thakur', 'Kavya Bedi', 'Neha Mondal', 'Ritu Anand', 'Rahul Bhatia', 'Manav Sethi',
    'Devansh Sood', 'Lakshya Arora', 'Samarth Kamat', 'Tejas Kulkarni', 'Aniket Pande', 'Siddharth Bose',
]

BEHAVIOR_TARGETS = {'good': 11, 'average': 14, 'risk': 11}  # 36 students => ~30/40/30

ATTENDANCE_RANGE = {
    'good': (0.90, 0.99),
    'average': (0.70, 0.85),
    'risk': (0.40, 0.60),
}
HOMEWORK_SUBMISSION_RATE = {'good': 0.95, 'average': 0.70, 'risk': 0.30}

HOMEWORK_ITEM_COUNT = {'Physics_9': 8, 'Chemistry_10': 7, 'Maths_12': 9}


@dataclass
class StudentSeed:
    name: str
    student_phone: str
    parent_phone: str
    batch_name: str
    behavior: str
    attendance_propensity: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Populate realistic coaching data.')
    parser.add_argument('--reset-db', action='store_true', help='Wipe and recreate all tables before simulation.')
    return parser.parse_args()


def ensure_schema(reset_db: bool) -> None:
    if reset_db:
        print('Resetting database tables...')
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_or_create_room(db, name: str, capacity: int, color_code: str) -> Room:
    row = db.query(Room).filter(Room.name == name).first()
    if not row:
        row = Room(name=name, capacity=capacity, color_code=color_code)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    changed = False
    if row.capacity != capacity:
        row.capacity = capacity
        changed = True
    if row.color_code != color_code:
        row.color_code = color_code
        changed = True
    if changed:
        db.commit()
        db.refresh(row)
    return row


def get_or_create_batch(db, blueprint: dict, room_id: int | None) -> Batch:
    name = blueprint['name']
    start_time = blueprint['start_time']
    subject = blueprint['subject']
    academic_level = blueprint['academic_level']
    color_code = blueprint['color_code']
    duration_minutes = int(blueprint.get('duration_minutes') or 60)
    location = blueprint.get('location')
    max_students = blueprint.get('max_students')
    is_online = bool(blueprint.get('is_online', False))
    meeting_link = blueprint.get('meeting_link')

    row = db.query(Batch).filter(Batch.name == name).first()
    if row:
        changed = False
        if row.start_time != start_time:
            row.start_time = start_time
            changed = True
        if row.subject != subject:
            row.subject = subject
            changed = True
        if row.academic_level != academic_level:
            row.academic_level = academic_level
            changed = True
        if row.color_code != color_code:
            row.color_code = color_code
            changed = True
        if row.default_duration_minutes != duration_minutes:
            row.default_duration_minutes = duration_minutes
            changed = True
        if row.location != location:
            row.location = location
            changed = True
        if row.max_students != max_students:
            row.max_students = max_students
            changed = True
        if row.is_online != is_online:
            row.is_online = is_online
            changed = True
        if row.meeting_link != meeting_link:
            row.meeting_link = meeting_link
            changed = True
        if row.room_id != room_id:
            row.room_id = room_id
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
        return row

    row = Batch(
        name=name,
        start_time=start_time,
        subject=subject,
        academic_level=academic_level,
        color_code=color_code,
        default_duration_minutes=duration_minutes,
        location=location,
        max_students=max_students,
        is_online=is_online,
        meeting_link=meeting_link,
        room_id=room_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_teacher_user(db, phone: str = '9990000001') -> AuthUser:
    row = db.query(AuthUser).filter(AuthUser.phone == phone).first()
    if not row:
        row = AuthUser(
            phone=phone,
            role=Role.TEACHER.value,
            time_zone='Asia/Kolkata',
            calendar_preferences='{\"snap_interval\":30,\"work_day_start\":\"07:00\",\"work_day_end\":\"20:00\",\"default_view\":\"week\"}',
            calendar_view_preference='week',
            calendar_snap_minutes=30,
            enable_live_mode_auto_open=True,
            default_event_color='#2f7bf6',
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    elif row.role != Role.TEACHER.value:
        row.role = Role.TEACHER.value
        db.commit()
        db.refresh(row)

    if row.time_zone != 'Asia/Kolkata' or not row.calendar_preferences:
        row.time_zone = 'Asia/Kolkata'
        row.calendar_preferences = row.calendar_preferences or '{"snap_interval":30,"work_day_start":"07:00","work_day_end":"20:00","default_view":"week"}'
        row.calendar_view_preference = row.calendar_view_preference or 'week'
        row.calendar_snap_minutes = row.calendar_snap_minutes or 30
        row.enable_live_mode_auto_open = True if row.enable_live_mode_auto_open is None else row.enable_live_mode_auto_open
        row.default_event_color = row.default_event_color or '#2f7bf6'
        db.commit()
        db.refresh(row)

    allowed = db.query(AllowedUser).filter(AllowedUser.phone == phone).first()
    if not allowed:
        allowed = AllowedUser(phone=phone, role=Role.TEACHER.value, status=AllowedUserStatus.ACTIVE.value)
        db.add(allowed)
        db.commit()
    elif allowed.role != Role.TEACHER.value:
        allowed.role = Role.TEACHER.value
        if allowed.status != AllowedUserStatus.ACTIVE.value:
            allowed.status = AllowedUserStatus.ACTIVE.value
        db.commit()

    return row


def ensure_batch_schedules(db, batch: Batch, weekdays: list[int], duration_minutes: int = 60) -> int:
    created = 0
    for weekday in weekdays:
        existing = db.query(BatchSchedule).filter(
            BatchSchedule.batch_id == batch.id,
            BatchSchedule.weekday == weekday,
            BatchSchedule.start_time == batch.start_time,
        ).first()
        if existing:
            continue
        db.add(
            BatchSchedule(
                batch_id=batch.id,
                weekday=weekday,
                start_time=batch.start_time,
                duration_minutes=duration_minutes,
            )
        )
        db.commit()
        created += 1
    return created


def ensure_student_batch_map(db, student: Student, batch_id: int) -> None:
    existing = db.query(StudentBatchMap).filter(
        StudentBatchMap.student_id == student.id,
        StudentBatchMap.batch_id == batch_id,
    ).first()
    if existing:
        if not existing.active:
            existing.active = True
            db.commit()
        return
    db.add(StudentBatchMap(student_id=student.id, batch_id=batch_id, active=True))
    db.commit()


def _generate_mobile(base: int, index: int) -> str:
    return f'{base + index:010d}'


def _build_behaviors() -> list[str]:
    labels: list[str] = []
    for behavior, count in BEHAVIOR_TARGETS.items():
        labels.extend([behavior] * count)
    RNG.shuffle(labels)
    return labels


def build_student_seeds(total_students: int = 36) -> list[StudentSeed]:
    names = INDIAN_STUDENT_NAMES[:]
    RNG.shuffle(names)
    names = names[:total_students]

    behaviors = _build_behaviors()
    batch_names = [row['name'] for row in BATCH_BLUEPRINTS]

    seeds: list[StudentSeed] = []
    for idx, name in enumerate(names):
        behavior = behaviors[idx]
        batch_name = batch_names[idx % len(batch_names)]
        low, high = ATTENDANCE_RANGE[behavior]
        seeds.append(
            StudentSeed(
                name=name,
                student_phone=_generate_mobile(9100000000, idx + 101),
                parent_phone=_generate_mobile(8100000000, idx + 501),
                batch_name=batch_name,
                behavior=behavior,
                attendance_propensity=round(RNG.uniform(low, high), 3),
            )
        )
    return seeds


def get_or_create_parent_for_student(db, student_name: str, parent_phone: str) -> Parent:
    row = db.query(Parent).filter(Parent.phone == parent_phone).first()
    if row:
        return row
    return create_parent(db, name=f'{student_name} Guardian', phone=parent_phone, telegram_chat_id='')


def get_or_create_student(db, seed: StudentSeed, batch_id: int) -> tuple[Student, bool]:
    row = db.query(Student).filter(Student.guardian_phone == seed.student_phone).first()
    if row:
        changed = False
        if row.name != seed.name:
            row.name = seed.name
            changed = True
        if row.batch_id != batch_id:
            row.batch_id = batch_id
            changed = True
        if not row.preferred_contact_method:
            row.preferred_contact_method = RNG.choice(['telegram', 'whatsapp', 'sms'])
            changed = True
        if not row.language_preference:
            row.language_preference = RNG.choice(['en', 'hi', 'ta'])
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
        return row, False

    row = Student(
        name=seed.name,
        guardian_phone=seed.student_phone,
        telegram_chat_id='',
        batch_id=batch_id,
        preferred_contact_method=RNG.choice(['telegram', 'whatsapp', 'sms']),
        language_preference=RNG.choice(['en', 'hi', 'ta']),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def _month_due_dates() -> list[date]:
    today = date.today()
    current_month_start = date(today.year, today.month, 1)
    prev_month_end = current_month_start - timedelta(days=1)
    prev_month_start = date(prev_month_end.year, prev_month_end.month, 1)
    return [prev_month_start + timedelta(days=4), current_month_start + timedelta(days=4)]


def ensure_fees_for_last_two_months(db, students: list[Student], behavior_by_student: dict[int, str]) -> int:
    created = 0
    prev_due, current_due = _month_due_dates()

    for student in students:
        behavior = behavior_by_student[student.id]
        monthly_amount = float(2400 + (student.id % 4) * 150)

        for idx, due_date in enumerate((prev_due, current_due)):
            fee = db.query(FeeRecord).filter(FeeRecord.student_id == student.id, FeeRecord.due_date == due_date).first()
            if not fee:
                fee = FeeRecord(
                    student_id=student.id,
                    due_date=due_date,
                    amount=monthly_amount,
                    paid_amount=0.0,
                    is_paid=False,
                    upi_link=build_upi_link(student, monthly_amount),
                )
                db.add(fee)
                db.commit()
                db.refresh(fee)
                created += 1

            if behavior == 'good':
                remaining = max(0.0, fee.amount - fee.paid_amount)
                if remaining > 0:
                    mark_fee_paid(db, fee.id, remaining)
                continue

            if behavior == 'average':
                if idx == 0:
                    remaining = max(0.0, fee.amount - fee.paid_amount)
                    if remaining > 0:
                        mark_fee_paid(db, fee.id, remaining)
                else:
                    paid_target = round(fee.amount * 0.70, 2)
                    if fee.paid_amount < paid_target:
                        mark_fee_paid(db, fee.id, paid_target - fee.paid_amount)
                    fee.is_paid = fee.paid_amount >= fee.amount
                    fee.upi_link = '' if fee.is_paid else build_upi_link(student, fee.amount - fee.paid_amount)
                    db.commit()
                continue

            if idx == 0:
                paid_target = round(fee.amount * 0.35, 2)
                if fee.paid_amount < paid_target:
                    mark_fee_paid(db, fee.id, paid_target - fee.paid_amount)
                fee.is_paid = fee.paid_amount >= fee.amount
                fee.upi_link = '' if fee.is_paid else build_upi_link(student, fee.amount - fee.paid_amount)
                db.commit()
            else:
                fee.paid_amount = 0.0
                fee.is_paid = False
                fee.upi_link = build_upi_link(student, fee.amount)
                db.commit()

    return created


def build_class_dates() -> list[date]:
    today = date.today()
    start_date = today - timedelta(days=30)
    class_dates: list[date] = []
    for day_idx in range(30):
        class_date = start_date + timedelta(days=day_idx)
        weekday = class_date.weekday()
        if weekday <= 3:
            class_dates.append(class_date)
        elif weekday == 4 and (class_date.isocalendar().week % 2 == 0):
            class_dates.append(class_date)
    return class_dates


def _pick_attendance_status(attendance_propensity: float, behavior: str) -> str:
    threshold = RNG.random()
    late_band = 0.05 if behavior == 'good' else (0.09 if behavior == 'average' else 0.12)

    if threshold <= attendance_propensity:
        return 'Present'
    if threshold <= min(1.0, attendance_propensity + late_band):
        return 'Late'
    return 'Absent'


def simulate_attendance_and_sessions(
    db,
    batches: list[Batch],
    students_by_batch: dict[int, list[Student]],
    behavior_by_student: dict[int, str],
    attendance_propensity_by_student: dict[int, float],
    teacher_id: int,
) -> tuple[int, int]:
    sessions_before = db.query(ClassSession).count()
    attendance_touched = 0
    class_dates = build_class_dates()

    for batch in batches:
        topics = SUBJECTS_BY_BATCH.get(batch.name, ['General Concept'])
        for idx, class_date in enumerate(class_dates):
            records = []
            for student in students_by_batch[batch.id]:
                behavior = behavior_by_student[student.id]
                propensity = attendance_propensity_by_student[student.id]
                status = _pick_attendance_status(propensity, behavior)
                comment = ''
                if status in ('Absent', 'Late') and RNG.random() < 0.85:
                    comment = RNG.choice(ATTENDANCE_COMMENTS)
                records.append({'student_id': student.id, 'status': status, 'comment': comment})

            topic = topics[idx % len(topics)]
            result = submit_attendance(
                db=db,
                batch_id=batch.id,
                attendance_date=class_date,
                records=records,
                subject=topic,
                teacher_id=teacher_id,
                topic_planned=f'{topic} guided practice',
                topic_completed=f'{topic} completed with board examples',
            )
            attendance_touched += int(result.get('updated_records', 0))

    sessions_after = db.query(ClassSession).count()
    return max(0, sessions_after - sessions_before), attendance_touched


def seed_upcoming_sessions(db, batches: list[Batch], teacher_id: int) -> int:
    created = 0
    today = date.today()
    for batch in batches:
        schedules = db.query(BatchSchedule).filter(BatchSchedule.batch_id == batch.id).all()
        if not schedules:
            continue
        for offset in range(0, 7):
            target_day = today + timedelta(days=offset)
            weekday = target_day.weekday()
            day_schedules = [s for s in schedules if s.weekday == weekday]
            for schedule in day_schedules:
                scheduled_start = datetime.combine(target_day, datetime.strptime(schedule.start_time, '%H:%M').time())
                existing = db.query(ClassSession).filter(
                    ClassSession.batch_id == batch.id,
                    ClassSession.scheduled_start == scheduled_start,
                ).first()
                if existing:
                    continue
                create_class_session(
                    db,
                    batch_id=batch.id,
                    subject=batch.subject,
                    scheduled_start=scheduled_start,
                    teacher_id=teacher_id,
                    topic_planned=f'{batch.subject} focus block',
                    duration_minutes=schedule.duration_minutes or 60,
                )
                created += 1
    return created


def simulate_homework(
    db,
    batches: list[Batch],
    students_by_batch: dict[int, list[Student]],
    behavior_by_student: dict[int, str],
) -> tuple[int, int]:
    created_homework = 0
    created_submissions = 0
    today = date.today()

    for batch in batches:
        homework_items = HOMEWORK_ITEM_COUNT.get(batch.name, 6)
        topics = SUBJECTS_BY_BATCH.get(batch.name, ['Practice Set'])

        for idx in range(homework_items):
            due_date = today - timedelta(days=2 + (idx * 3))
            topic = topics[idx % len(topics)]
            title = f'SIM {batch.name} HW-{idx + 1}: {topic}'

            homework = db.query(Homework).filter(Homework.title == title, Homework.due_date == due_date).first()
            if not homework:
                homework = create_homework(
                    db,
                    {
                        'title': title,
                        'description': f'{batch.name} worksheet focused on {topic}.',
                        'due_date': due_date,
                        'attachment_path': '',
                    },
                )
                created_homework += 1

            for student in students_by_batch[batch.id]:
                behavior = behavior_by_student[student.id]
                if RNG.random() > HOMEWORK_SUBMISSION_RATE[behavior]:
                    continue

                existing = db.query(HomeworkSubmission).filter(
                    HomeworkSubmission.homework_id == homework.id,
                    HomeworkSubmission.student_id == student.id,
                ).first()
                if existing:
                    continue

                submit_homework(
                    db,
                    {
                        'homework_id': homework.id,
                        'student_id': student.id,
                        'file_path': f'submissions/sim_{batch.name.lower()}_{student.id}_{homework.id}.pdf',
                    },
                )
                created_submissions += 1

    return created_homework, created_submissions


def simulate_referrals(db, students: list[Student]) -> int:
    created = 0
    selected = students[:]
    RNG.shuffle(selected)
    selected = selected[:6]

    for idx, student in enumerate(selected):
        referral = (
            db.query(ReferralCode)
            .filter(ReferralCode.student_id == student.id)
            .order_by(ReferralCode.id.asc())
            .first()
        )
        if not referral:
            referral = create_referral_code(db, student.id)
            created += 1

        if idx < 3:
            referral.usage_count = idx + 1
            referral.reward_points = 100 * (idx + 1)
        else:
            referral.usage_count = 0
            referral.reward_points = 0
        db.commit()

    return created


def backfill_pending_actions_for_overdue_fees(db) -> None:
    today = date.today()
    overdue_fees = db.query(FeeRecord).filter(FeeRecord.is_paid.is_(False), FeeRecord.due_date <= today).all()
    for fee in overdue_fees:
        create_pending_action(
            db,
            action_type='fee_followup',
            student_id=fee.student_id,
            related_session_id=None,
            note=f'Overdue fee follow-up due {fee.due_date}',
        )


def summarize(db, created_counts: dict[str, int]) -> None:
    total_students = db.query(Student).count()
    total_sessions = db.query(ClassSession).count()
    total_attendance = db.query(AttendanceRecord).count()
    total_open_actions = db.query(PendingAction).filter(PendingAction.status == 'open').count()

    high_risk = db.query(StudentRiskProfile).filter(StudentRiskProfile.risk_level == 'HIGH').count()
    medium_risk = db.query(StudentRiskProfile).filter(StudentRiskProfile.risk_level == 'MEDIUM').count()
    low_risk = db.query(StudentRiskProfile).filter(StudentRiskProfile.risk_level == 'LOW').count()

    print('\nSimulation Summary')
    print('------------------')
    print(f"Students created: {created_counts['students_created']} (total: {total_students})")
    print(f"Sessions created: {created_counts['sessions_created']} (total: {total_sessions})")
    print(f"Attendance records: {created_counts['attendance_records']} (total: {total_attendance})")
    print(f"Actions created: {created_counts['actions_created']} (open total: {total_open_actions})")
    print(f'High-risk students count: {high_risk}')
    print(f'Risk distribution => LOW: {low_risk}, MEDIUM: {medium_risk}, HIGH: {high_risk}')


def main() -> None:
    args = parse_args()
    ensure_schema(reset_db=args.reset_db)

    settings.enable_telegram_notifications = False

    db = SessionLocal()
    try:
        teacher = get_or_create_teacher_user(db)
        actions_before = db.query(PendingAction).count()

        rooms = {
            blueprint['name']: get_or_create_room(db, blueprint['name'], blueprint['capacity'], blueprint['color_code'])
            for blueprint in ROOM_BLUEPRINTS
        }
        batches = [
            get_or_create_batch(db, blueprint, rooms.get(blueprint['room']).id if blueprint.get('room') else None)
            for blueprint in BATCH_BLUEPRINTS
        ]
        batch_by_name = {batch.name: batch for batch in batches}
        for batch in batches:
            ensure_batch_schedules(db, batch, weekdays=[0, 2, 4], duration_minutes=batch.default_duration_minutes or 60)

        seeds = build_student_seeds(total_students=36)

        students_created = 0
        students: list[Student] = []
        behavior_by_student: dict[int, str] = {}
        attendance_propensity_by_student: dict[int, float] = {}

        for seed in seeds:
            batch = batch_by_name[seed.batch_name]
            student, was_created = get_or_create_student(db, seed, batch.id)
            if was_created:
                students_created += 1

            parent = get_or_create_parent_for_student(db, seed.name, seed.parent_phone)
            link_parent_student(db, parent_id=parent.id, student_id=student.id, relation='guardian')
            ensure_student_batch_map(db, student, batch.id)

            students.append(student)
            behavior_by_student[student.id] = seed.behavior
            attendance_propensity_by_student[student.id] = seed.attendance_propensity

        students_by_batch: dict[int, list[Student]] = {batch.id: [] for batch in batches}
        for student in students:
            students_by_batch[student.batch_id].append(student)

        ensure_fees_for_last_two_months(db, students, behavior_by_student)

        sessions_created, attendance_records = simulate_attendance_and_sessions(
            db=db,
            batches=batches,
            students_by_batch=students_by_batch,
            behavior_by_student=behavior_by_student,
            attendance_propensity_by_student=attendance_propensity_by_student,
            teacher_id=teacher.id,
        )

        sessions_created += seed_upcoming_sessions(db, batches=batches, teacher_id=teacher.id)

        simulate_homework(
            db=db,
            batches=batches,
            students_by_batch=students_by_batch,
            behavior_by_student=behavior_by_student,
        )

        simulate_referrals(db, students)

        backfill_pending_actions_for_overdue_fees(db)
        recompute_all_student_risk(db)

        actions_after = db.query(PendingAction).count()
        summarize(
            db,
            created_counts={
                'students_created': students_created,
                'sessions_created': sessions_created,
                'attendance_records': attendance_records,
                'actions_created': max(0, actions_after - actions_before),
            },
        )
    finally:
        db.close()


if __name__ == '__main__':
    main()
