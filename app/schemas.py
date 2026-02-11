from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class AttendanceItem(BaseModel):
    student_id: int
    status: Literal['Present', 'Absent', 'Late']
    comment: str = ''


class AttendanceSubmitRequest(BaseModel):
    batch_id: int
    attendance_date: date
    records: list[AttendanceItem]
    subject: str = 'General'
    teacher_id: int = 0
    scheduled_start: datetime | None = None
    topic_planned: str = ''
    topic_completed: str = ''


class FeeMarkPaidRequest(BaseModel):
    fee_record_id: int
    paid_amount: float = Field(gt=0)


class ReferralCreateRequest(BaseModel):
    student_id: int


class HomeworkCreateRequest(BaseModel):
    title: str
    description: str = ''
    due_date: date
    attachment_path: str = ''


class HomeworkSubmissionRequest(BaseModel):
    homework_id: int
    student_id: int
    file_path: str


class ClassSessionCreateRequest(BaseModel):
    batch_id: int
    subject: str
    scheduled_start: datetime
    topic_planned: str = ''
    teacher_id: int
    duration_minutes: int = Field(default=60, ge=1, le=180)


class ClassSessionUpdateRequest(BaseModel):
    actual_start: datetime | None = None
    topic_completed: str = ''
    status: Literal['scheduled', 'open', 'submitted', 'closed', 'missed', 'running', 'completed']


class ParentCreateRequest(BaseModel):
    name: str
    phone: str = ''
    telegram_chat_id: str = ''


class ParentStudentLinkRequest(BaseModel):
    parent_id: int
    student_id: int
    relation: str = 'guardian'


class ActionTokenCreateRequest(BaseModel):
    action_type: str
    payload: dict = Field(default_factory=dict)
    ttl_minutes: int = Field(default=30, ge=1, le=240)


class ActionTokenExecuteRequest(BaseModel):
    token: str
    message: str = ''
    parent_id: int | None = None
    student_id: int | None = None
    fee_record_id: int | None = None


class OfferCreateRequest(BaseModel):
    code: str
    title: str
    discount_type: Literal['flat', 'percent']
    discount_value: float = Field(gt=0)
    valid_from: date
    valid_to: date
    active: bool = True


class OfferApplyRequest(BaseModel):
    code: str
    student_id: int
    fee_record_id: int
    referral_code: str | None = None


class ClassSummaryResponse(BaseModel):
    class_session_id: int
    present_count: int
    absent_count: int
    late_count: int
    topic_completed: str
    homework_status_summary: dict
    unpaid_students_present: list[int]


class RuleConfigUpsertRequest(BaseModel):
    batch_id: int | None = None
    absence_streak_threshold: int = Field(default=3, ge=1, le=30)
    notify_parent_on_absence: bool = True
    notify_parent_on_fee_due: bool = True
    reminder_grace_period_days: int = Field(default=0, ge=0, le=30)
    quiet_hours_start: str = '22:00'
    quiet_hours_end: str = '06:00'


class ProgramCreate(BaseModel):
    name: str
    description: str = ''


class ProgramRead(BaseModel):
    id: int
    name: str
    description: str = ''
    created_at: datetime

    class Config:
        from_attributes = True


class BoardCreate(BaseModel):
    name: str
    shortcode: str


class BoardRead(BaseModel):
    id: int
    name: str
    shortcode: str
    created_at: datetime

    class Config:
        from_attributes = True


class ClassLevelCreate(BaseModel):
    name: str
    min_grade: int | None = None
    max_grade: int | None = None


class ClassLevelRead(BaseModel):
    id: int
    name: str
    min_grade: int | None = None
    max_grade: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    name: str
    code: str | None = ''


class SubjectRead(BaseModel):
    id: int
    name: str
    code: str | None = ''
    created_at: datetime

    class Config:
        from_attributes = True
