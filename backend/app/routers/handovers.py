from datetime import date, datetime
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    User,
    Handover,
    Admission,
    AdmissionStatus,
    HandoverStatus,
    ShiftType,
    Role,
    RiskLevel,
    Escalation,
    EscalationSeverity,
    EscalationStatus,
)
from app.schemas import HandoverUpdate, ReviewIn
from app.deps import (
    get_current_user,
    assert_ward_access,
    write_audit,
    current_shift,
    previous_shift,
    REVIEWERS,
    user_ward_ids,
    ward_filter,
    handover_edit_block_reason,
    assert_can_edit_handover,
    assert_rostered_writer,
)
from app.risk import suggest_risk

router = APIRouter(prefix="/handovers", tags=["handovers"])

REQUIRED_ON_SUBMIT = [
    "diagnosis",
    "reason_for_admission",
    "current_situation",
    "immediate_treatment",
    "nursing_care",
]

DEFAULT_EXAMS = {
    k: {"status": "normal", "notes": ""}
    for k in [
        "respiratory",
        "cardiovascular",
        "neurological",
        "genitourinary",
        "musculoskeletal",
        "integumentary",
    ]
}

CARRY_FIELDS = [
    "diagnosis",
    "reason_for_admission",
    "current_situation",
    "immediate_concern",
    "critical_flag",
    "medical_history",
    "surgical_history",
    "medications",
    "allergies",
    "nkda",
    "vitals",
    "system_exams",
    "significant_findings",
    "diagnostics",
    "immediate_treatment",
    "nursing_care",
    "team_communication",
    "expected_discharge_date",
    "follow_up",
    "home_care_needs",
    "risk_level",
    "risk_override_reason",
]


def _previous_handover(db: Session, admission_id: int, shift_type: ShiftType, shift_date: date) -> Handover | None:
    pst, psd = previous_shift(shift_type, shift_date)
    return (
        db.query(Handover)
        .options(joinedload(Handover.author))
        .filter(
            Handover.admission_id == admission_id,
            Handover.shift_type == pst,
            Handover.shift_date == psd,
        )
        .first()
    )


def serialize(h: Handover, user: User | None = None, db=None) -> dict:
    a = h.admission
    p = a.patient if a else None
    prev = _previous_handover(db, h.admission_id, h.shift_type, h.shift_date) if db is not None else None
    return {
        "id": h.id,
        "admission_id": h.admission_id,
        "shift_type": h.shift_type.value,
        "shift_date": str(h.shift_date),
        "author_id": h.author_id,
        "author_name": h.author.full_name if h.author else None,
        "status": h.status.value,
        "risk_level": h.risk_level.value,
        "risk_override_reason": h.risk_override_reason,
        "submitted_at": h.submitted_at.isoformat() if h.submitted_at else None,
        "reviewed_by_id": h.reviewed_by_id,
        "reviewed_at": h.reviewed_at.isoformat() if h.reviewed_at else None,
        "review_comment": h.review_comment,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
        "diagnosis": h.diagnosis,
        "reason_for_admission": h.reason_for_admission,
        "current_situation": h.current_situation,
        "immediate_concern": h.immediate_concern,
        "critical_flag": h.critical_flag,
        "medical_history": h.medical_history or [],
        "surgical_history": h.surgical_history or [],
        "medications": h.medications or [],
        "allergies": h.allergies or [],
        "nkda": h.nkda,
        "vitals": h.vitals or {},
        "system_exams": h.system_exams or {},
        "significant_findings": h.significant_findings,
        "diagnostics": h.diagnostics or [],
        "immediate_treatment": h.immediate_treatment,
        "nursing_care": h.nursing_care,
        "team_communication": h.team_communication,
        "expected_discharge_date": str(h.expected_discharge_date) if h.expected_discharge_date else None,
        "follow_up": h.follow_up,
        "home_care_needs": h.home_care_needs,
        "ai_summary": h.ai_summary,
        "patient": {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "sex": p.sex.value,
            "mrn": p.mrn,
        }
        if p
        else None,
        "admission": {
            "id": a.id,
            "ward_id": a.ward_id,
            "bed_number": a.bed_number,
            "diagnosis": a.diagnosis,
            "reason_for_admission": a.reason_for_admission,
            "ward_name": a.ward.name if a.ward else None,
        }
        if a
        else None,
        "suggested_risk": suggest_risk(h.vitals, h.critical_flag).value,
        "can_edit": not handover_edit_block_reason(db, user, h) if user is not None and db is not None else False,
        "lock_reason": handover_edit_block_reason(db, user, h) if user is not None and db is not None else None,
        "previous_handover_id": prev.id if prev else None,
        "previous_author_name": prev.author.full_name if prev and prev.author else None,
        "previous_shift_type": prev.shift_type.value if prev else None,
        "previous_shift_date": str(prev.shift_date) if prev else None,
    }


def _load(db: Session, hid: int) -> Handover | None:
    return (
        db.query(Handover)
        .options(
            joinedload(Handover.admission).joinedload(Admission.patient),
            joinedload(Handover.admission).joinedload(Admission.ward),
            joinedload(Handover.author),
        )
        .filter(Handover.id == hid)
        .first()
    )


@router.get("/")
def list_handovers(
    ward_id: int | None = None,
    shift_type: ShiftType | None = None,
    shift_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st, sd = current_shift()
    shift_type = shift_type or st
    shift_date = shift_date or sd
    q = db.query(Handover).join(Admission).options(
        joinedload(Handover.admission).joinedload(Admission.patient),
        joinedload(Handover.admission).joinedload(Admission.ward),
        joinedload(Handover.author),
    )
    allowed = user_ward_ids(db, user)
    q = q.filter(ward_filter(Admission.ward_id, allowed))
    if ward_id:
        assert_ward_access(db, user, ward_id)
        q = q.filter(Admission.ward_id == ward_id)
    q = q.filter(Handover.shift_type == shift_type, Handover.shift_date == shift_date)
    return [serialize(h, user, db) for h in q.all()]


@router.post("/ensure")
def ensure_handover(
    admission_id: int,
    shift_type: ShiftType | None = None,
    shift_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    st, sd = current_shift()
    shift_type = shift_type or st
    shift_date = shift_date or sd
    admission = db.get(Admission, admission_id)
    if not admission or admission.status != AdmissionStatus.active:
        raise HTTPException(404, "Active admission not found")
    assert_ward_access(db, user, admission.ward_id)
    existing = (
        db.query(Handover)
        .filter(
            Handover.admission_id == admission_id,
            Handover.shift_type == shift_type,
            Handover.shift_date == shift_date,
        )
        .first()
    )
    if existing:
        return serialize(_load(db, existing.id), user, db)
    assert_rostered_writer(db, user, admission.ward_id, shift_type, shift_date)
    prev = _previous_handover(db, admission_id, shift_type, shift_date)
    carried = {}
    if prev:
        for key in CARRY_FIELDS:
            val = getattr(prev, key)
            carried[key] = deepcopy(val) if isinstance(val, (dict, list)) else val
    h = Handover(
        admission_id=admission_id,
        shift_type=shift_type,
        shift_date=shift_date,
        author_id=user.id,
        diagnosis=carried.get("diagnosis") or admission.diagnosis,
        reason_for_admission=carried.get("reason_for_admission") or admission.reason_for_admission,
        current_situation=carried.get("current_situation"),
        immediate_concern=carried.get("immediate_concern"),
        critical_flag=bool(carried.get("critical_flag")),
        medical_history=carried.get("medical_history") or [],
        surgical_history=carried.get("surgical_history") or [],
        medications=carried.get("medications") or [],
        allergies=carried.get("allergies") or [],
        nkda=bool(carried.get("nkda")),
        vitals=carried.get("vitals") or {},
        system_exams=carried.get("system_exams") or deepcopy(DEFAULT_EXAMS),
        significant_findings=carried.get("significant_findings"),
        diagnostics=carried.get("diagnostics") or [],
        immediate_treatment=carried.get("immediate_treatment"),
        nursing_care=carried.get("nursing_care"),
        team_communication=carried.get("team_communication"),
        expected_discharge_date=carried.get("expected_discharge_date"),
        follow_up=carried.get("follow_up"),
        home_care_needs=carried.get("home_care_needs"),
        risk_level=carried.get("risk_level") or RiskLevel.stable,
        risk_override_reason=carried.get("risk_override_reason"),
    )
    db.add(h)
    db.commit()
    return serialize(_load(db, h.id), user, db)


@router.get("/{handover_id}")
def get_handover(handover_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    h = _load(db, handover_id)
    if not h:
        raise HTTPException(404, "Not found")
    assert_ward_access(db, user, h.admission.ward_id)
    return serialize(h, user, db)


@router.patch("/{handover_id}")
def update_handover(
    handover_id: int,
    body: HandoverUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = _load(db, handover_id)
    if not h:
        raise HTTPException(404, "Not found")
    assert_ward_access(db, user, h.admission.ward_id)
    assert_can_edit_handover(db, user, h)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(h, k, v)
    suggested = suggest_risk(h.vitals, h.critical_flag)
    if "risk_level" not in data or not h.risk_override_reason:
        h.risk_level = suggested
    h.updated_at = datetime.utcnow()
    db.commit()
    write_audit(db, user, "update", "handover", h.id, request=request)
    return serialize(_load(db, h.id), user, db)


@router.post("/{handover_id}/submit")
def submit(
    handover_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = _load(db, handover_id)
    if not h:
        raise HTTPException(404, "Not found")
    assert_ward_access(db, user, h.admission.ward_id)
    assert_can_edit_handover(db, user, h)
    missing = [f for f in REQUIRED_ON_SUBMIT if not getattr(h, f)]
    if not h.vitals or not h.vitals.get("temp"):
        missing.append("vitals")
    exams = h.system_exams or {}
    for sys in ["respiratory", "cardiovascular", "neurological", "genitourinary", "musculoskeletal", "integumentary"]:
        if sys not in exams:
            missing.append(f"exam:{sys}")
    if not h.nkda and not (h.allergies or []):
        missing.append("allergies_or_nkda")
    if not (h.medications or []):
        missing.append("medications")
    if not (h.medical_history or []):
        missing.append("medical_history")
    if h.critical_flag and not h.immediate_concern:
        missing.append("immediate_concern")
    if missing:
        raise HTTPException(400, detail={"missing": missing})
    h.status = HandoverStatus.submitted
    h.submitted_at = datetime.utcnow()
    h.author_id = user.id
    if h.critical_flag or h.risk_level == RiskLevel.critical:
        existing = (
            db.query(Escalation)
            .filter(Escalation.handover_id == h.id, Escalation.status != EscalationStatus.resolved)
            .first()
        )
        if not existing:
            db.add(
                Escalation(
                    handover_id=h.id,
                    raised_by_id=user.id,
                    severity=EscalationSeverity.critical,
                    description=h.immediate_concern or "Patient flagged critical on SBAR submit",
                    status=EscalationStatus.open,
                )
            )
            db.flush()
    db.commit()
    write_audit(db, user, "submit", "handover", h.id, request=request)
    if h.critical_flag or h.risk_level == RiskLevel.critical:
        write_audit(db, user, "flag_critical", "handover", h.id, request=request)
    return serialize(_load(db, h.id), user, db)


@router.post("/{handover_id}/review")
def review(
    handover_id: int,
    body: ReviewIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS:
        raise HTTPException(403, "Reviewers only")
    h = _load(db, handover_id)
    if not h:
        raise HTTPException(404, "Not found")
    assert_ward_access(db, user, h.admission.ward_id)
    h.status = HandoverStatus.under_review
    if body.action == "accept":
        h.status = HandoverStatus.accepted
    elif body.action == "return":
        h.status = HandoverStatus.returned
    else:
        raise HTTPException(400, "action must be accept or return")
    h.reviewed_by_id = user.id
    h.reviewed_at = datetime.utcnow()
    h.review_comment = body.comment
    db.commit()
    write_audit(db, user, body.action, "handover", h.id, request=request)
    return serialize(_load(db, h.id), user, db)
