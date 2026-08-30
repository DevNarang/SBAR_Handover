from datetime import datetime, date, time
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.models import (
    Role,
    ShiftType,
    AdmissionStatus,
    HandoverStatus,
    RiskLevel,
    EscalationStatus,
    EscalationSeverity,
    TaskStatus,
    Sex,
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    employee_id: str
    full_name: str
    role: Role
    department: str | None
    is_active: bool
    ward_ids: list[int] = []

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    email: EmailStr
    employee_id: str
    full_name: str
    password: str
    role: Role
    department: str | None = None
    ward_ids: list[int] = []
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    department: str | None = None
    ward_ids: list[int] | None = None
    is_active: bool | None = None
    password: str | None = None


class WardIn(BaseModel):
    name: str
    department: str | None = None
    is_active: bool = True


class WardOut(BaseModel):
    id: int
    name: str
    department: str | None
    is_active: bool

    class Config:
        from_attributes = True


class PatientIn(BaseModel):
    name: str
    age: int
    sex: Sex
    mrn: str | None = None


class PatientOut(BaseModel):
    id: int
    name: str
    age: int
    sex: Sex
    mrn: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AdmissionIn(BaseModel):
    patient_id: int
    ward_id: int
    bed_number: str
    diagnosis: str
    reason_for_admission: str


class AdmissionOut(BaseModel):
    id: int
    patient_id: int
    ward_id: int
    bed_number: str
    diagnosis: str
    reason_for_admission: str
    status: AdmissionStatus
    admitted_at: datetime
    discharged_at: datetime | None
    patient: PatientOut | None = None
    ward: WardOut | None = None

    class Config:
        from_attributes = True


class TransferIn(BaseModel):
    ward_id: int
    bed_number: str


class VitalsIn(BaseModel):
    temp: float | None = None
    bp_systolic: int | None = None
    bp_diastolic: int | None = None
    pr: int | None = None
    rr: int | None = None
    spo2: int | None = None
    recorded_at: str | None = None


class SystemExamIn(BaseModel):
    status: str = "normal"
    notes: str = ""


class HandoverUpdate(BaseModel):
    diagnosis: str | None = None
    reason_for_admission: str | None = None
    current_situation: str | None = None
    immediate_concern: str | None = None
    critical_flag: bool | None = None
    medical_history: list[Any] | None = None
    surgical_history: list[Any] | None = None
    medications: list[Any] | None = None
    allergies: list[Any] | None = None
    nkda: bool | None = None
    vitals: dict | None = None
    system_exams: dict | None = None
    significant_findings: str | None = None
    diagnostics: list[Any] | None = None
    immediate_treatment: str | None = None
    nursing_care: str | None = None
    team_communication: str | None = None
    expected_discharge_date: date | None = None
    follow_up: str | None = None
    home_care_needs: str | None = None
    risk_level: RiskLevel | None = None
    risk_override_reason: str | None = None


class ReviewIn(BaseModel):
    action: str  # accept | return
    comment: str | None = None


class ShiftAssignmentIn(BaseModel):
    ward_id: int
    shift_type: ShiftType
    shift_date: date
    nurse_id: int


class ShiftAssignmentOut(BaseModel):
    id: int
    ward_id: int
    shift_type: ShiftType
    shift_date: date
    nurse_id: int
    nurse_name: str | None = None
    assigned_by_id: int
    assigned_by_name: str | None = None

    class Config:
        from_attributes = True


class SignoffIn(BaseModel):
    ward_id: int
    shift_type: ShiftType
    shift_date: date
    outgoing_nurse_id: int
    notes: str | None = None


class EscalationIn(BaseModel):
    handover_id: int
    severity: EscalationSeverity
    description: str


class EscalationUpdate(BaseModel):
    status: EscalationStatus | None = None
    assigned_to_id: int | None = None
    resolution_notes: str | None = None
    escalate_up: bool = False


class TaskIn(BaseModel):
    admission_id: int
    assignee_id: int | None = None
    title: str
    due_at: datetime | None = None
    priority: str = "medium"


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    assignee_id: int | None = None
    title: str | None = None


class ProtocolIn(BaseModel):
    title: str
    body: str
    ward_ids: list[int] = []


class AiSummaryIn(BaseModel):
    handover_id: int | None = None
    payload: dict = Field(default_factory=dict)
