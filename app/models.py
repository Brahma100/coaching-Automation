from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Batch(Base):
    __tablename__ = 'batches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    start_time: Mapped[str] = mapped_column(String(10), default='07:00')

    students: Mapped[list['Student']] = relationship('Student', back_populates='batch')
    class_sessions: Mapped[list['ClassSession']] = relationship('ClassSession', back_populates='batch')


class Student(Base):
    __tablename__ = 'students'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    guardian_phone: Mapped[str] = mapped_column(String(20), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default='')
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'))

    batch: Mapped['Batch'] = relationship('Batch', back_populates='students')
    attendances: Mapped[list['AttendanceRecord']] = relationship('AttendanceRecord', back_populates='student')
    fees: Mapped[list['FeeRecord']] = relationship('FeeRecord', back_populates='student')
    homework_submissions: Mapped[list['HomeworkSubmission']] = relationship('HomeworkSubmission', back_populates='student')
    referrals: Mapped[list['ReferralCode']] = relationship('ReferralCode', back_populates='student')
    parent_links: Mapped[list['ParentStudentMap']] = relationship('ParentStudentMap', back_populates='student')


class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    attendance_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text, default='')
    marked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped['Student'] = relationship('Student', back_populates='attendances')


class FeeRecord(Base):
    __tablename__ = 'fee_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    upi_link: Mapped[str] = mapped_column(String(255), default='')

    student: Mapped['Student'] = relationship('Student', back_populates='fees')


class Homework(Base):
    __tablename__ = 'homework'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default='')
    due_date: Mapped[date] = mapped_column(Date)
    attachment_path: Mapped[str] = mapped_column(String(255), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submissions: Mapped[list['HomeworkSubmission']] = relationship('HomeworkSubmission', back_populates='homework')


class HomeworkSubmission(Base):
    __tablename__ = 'homework_submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    homework_id: Mapped[int] = mapped_column(ForeignKey('homework.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    file_path: Mapped[str] = mapped_column(String(255), default='')
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    homework: Mapped['Homework'] = relationship('Homework', back_populates='submissions')
    student: Mapped['Student'] = relationship('Student', back_populates='homework_submissions')


class ReferralCode(Base):
    __tablename__ = 'referral_codes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    reward_points: Mapped[int] = mapped_column(Integer, default=0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped['Student'] = relationship('Student', back_populates='referrals')


class Offer(Base):
    __tablename__ = 'offers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(140))
    discount_type: Mapped[str] = mapped_column(String(20), default='flat')  # flat | percent
    discount_value: Mapped[float] = mapped_column(Float, default=0)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    redemptions: Mapped[list['OfferRedemption']] = relationship('OfferRedemption', back_populates='offer')


class OfferRedemption(Base):
    __tablename__ = 'offer_redemptions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('offers.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    fee_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referral_code_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    offer: Mapped['Offer'] = relationship('Offer', back_populates='redemptions')


class ClassSession(Base):
    __tablename__ = 'class_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    subject: Mapped[str] = mapped_column(String(80), default='General')
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    topic_planned: Mapped[str] = mapped_column(Text, default='')
    topic_completed: Mapped[str] = mapped_column(Text, default='')
    teacher_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    status: Mapped[str] = mapped_column(String(20), default='scheduled')  # scheduled|running|completed|missed

    batch: Mapped['Batch'] = relationship('Batch', back_populates='class_sessions')


class Parent(Base):
    __tablename__ = 'parents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default='')

    student_links: Mapped[list['ParentStudentMap']] = relationship('ParentStudentMap', back_populates='parent')


class ParentStudentMap(Base):
    __tablename__ = 'parent_student_map'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey('parents.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'), index=True)
    relation: Mapped[str] = mapped_column(String(30), default='guardian')

    parent: Mapped['Parent'] = relationship('Parent', back_populates='student_links')
    student: Mapped['Student'] = relationship('Student', back_populates='parent_links')


class ActionToken(Base):
    __tablename__ = 'action_tokens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RuleConfig(Base):
    __tablename__ = 'rule_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    absence_streak_threshold: Mapped[int] = mapped_column(Integer, default=3)
    notify_parent_on_absence: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_parent_on_fee_due: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_grace_period_days: Mapped[int] = mapped_column(Integer, default=0)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default='22:00')
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default='06:00')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PendingAction(Base):
    __tablename__ = 'pending_actions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)  # fee_followup|absence|homework|manual
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)  # open|resolved
    note: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StaffUser(Base):
    __tablename__ = 'staff_users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)  # admin | teacher
    password_hash: Mapped[str] = mapped_column(String(255), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BackupLog(Base):
    __tablename__ = 'backup_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default='failed', index=True)  # success | failed
    message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CommunicationLog(Base):
    __tablename__ = 'communication_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
