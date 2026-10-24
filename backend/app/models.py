import enum
from datetime import datetime, date, time

from app.clock import now as ist_now

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class Role(str, enum.Enum):
    medical_superintendent = "medical_superintendent"
    nursing_superintendent = "nursing_superintendent"
    hod = "hod"
    nursing_supervisor = "nursing_supervisor"
    nursing_officer = "nursing_officer"


class AccountStatus:
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ShiftType(str, enum.Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class AdmissionStatus(str, enum.Enum):
    active = "active"
    transferred = "transferred"
    discharged = "discharged"


class HandoverStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    accepted = "accepted"
    returned = "returned"


class RiskLevel(str, enum.Enum):
    stable = "stable"
    watch = "watch"
    critical = "critical"


class EscalationStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class EscalationSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class ExamStatus(str, enum.Enum):
    normal = "normal"
    abnormal = "abnormal"


class Sex(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account_status: Mapped[str] = mapped_column(String(32), default=AccountStatus.approved)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    ward_assignments: Mapped[list["UserWardAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserWardAssignment(Base):
    __tablename__ = "user_ward_assignments"
    __table_args__ = (UniqueConstraint("user_id", "ward_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))

    user: Mapped[User] = relationship(back_populates="ward_assignments")
    ward: Mapped[Ward] = relationship()


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (UniqueConstraint("ward_id", "shift_type", "shift_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    shift_type: Mapped[ShiftType] = mapped_column(Enum(ShiftType))
    shift_date: Mapped[date] = mapped_column(Date)
    nurse_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    ward: Mapped[Ward] = relationship()
    nurse: Mapped[User] = relationship(foreign_keys=[nurse_id])
    assigned_by: Mapped[User] = relationship(foreign_keys=[assigned_by_id])


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[Sex] = mapped_column(Enum(Sex))
    mrn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    admissions: Mapped[list["Admission"]] = relationship(back_populates="patient")


class Admission(Base):
    __tablename__ = "admissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    bed_number: Mapped[str] = mapped_column(String(32))
    diagnosis: Mapped[str] = mapped_column(Text)
    reason_for_admission: Mapped[str] = mapped_column(Text)
    status: Mapped[AdmissionStatus] = mapped_column(Enum(AdmissionStatus), default=AdmissionStatus.active)
    admitted_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="admissions")
    ward: Mapped[Ward] = relationship()
    handovers: Mapped[list["Handover"]] = relationship(back_populates="admission")


class Handover(Base):
    __tablename__ = "handovers"
    __table_args__ = (UniqueConstraint("admission_id", "shift_type", "shift_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"))
    shift_type: Mapped[ShiftType] = mapped_column(Enum(ShiftType))
    shift_date: Mapped[date] = mapped_column(Date)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[HandoverStatus] = mapped_column(Enum(HandoverStatus), default=HandoverStatus.draft)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), default=RiskLevel.stable)
    risk_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now, onupdate=ist_now)

    # Situation
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_for_admission: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    immediate_concern: Mapped[str | None] = mapped_column(Text, nullable=True)
    critical_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    # Background
    medical_history: Mapped[list | None] = mapped_column(JSON, default=list)
    surgical_history: Mapped[list | None] = mapped_column(JSON, default=list)
    medications: Mapped[list | None] = mapped_column(JSON, default=list)
    allergies: Mapped[list | None] = mapped_column(JSON, default=list)
    nkda: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assessment
    vitals: Mapped[dict | None] = mapped_column(JSON, default=dict)
    system_exams: Mapped[dict | None] = mapped_column(JSON, default=dict)
    significant_findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostics: Mapped[list | None] = mapped_column(JSON, default=list)

    # Recommendation
    immediate_treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    nursing_care: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_communication: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_discharge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_care_needs: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    admission: Mapped[Admission] = relationship(back_populates="handovers")
    author: Mapped[User] = relationship(foreign_keys=[author_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey("handovers.id"))
    raised_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    severity: Mapped[EscalationSeverity] = mapped_column(Enum(EscalationSeverity))
    status: Mapped[EscalationStatus] = mapped_column(Enum(EscalationStatus), default=EscalationStatus.open)
    description: Mapped[str] = mapped_column(Text)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    handover: Mapped[Handover] = relationship()
    raised_by: Mapped[User] = relationship(foreign_keys=[raised_by_id])
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id])


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    admission: Mapped[Admission] = relationship()
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])


class WardShiftSignoff(Base):
    __tablename__ = "ward_shift_signoffs"
    __table_args__ = (UniqueConstraint("ward_id", "shift_type", "shift_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    shift_type: Mapped[ShiftType] = mapped_column(Enum(ShiftType))
    shift_date: Mapped[date] = mapped_column(Date)
    signed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    outgoing_nurse_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    patient_count: Mapped[int] = mapped_column(Integer, default=0)

    ward: Mapped[Ward] = relationship()
    signed_by: Mapped[User] = relationship(foreign_keys=[signed_by_id])
    outgoing_nurse: Mapped[User | None] = relationship(foreign_keys=[outgoing_nurse_id])


class Protocol(Base):
    __tablename__ = "protocols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ward_ids: Mapped[list | None] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    created_by: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)

    user: Mapped[User | None] = relationship()


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    handover_id: Mapped[int | None] = mapped_column(ForeignKey("handovers.id"), nullable=True)
    feature: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=ist_now)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(255), index=True)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
