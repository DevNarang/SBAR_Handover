from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.clock import TIMEZONE_NAME, now as ist_now
from app.config import settings
from app.database import get_db
from app.models import (
    User,
    Escalation,
    EscalationStatus,
    EscalationSeverity,
    Task,
    TaskStatus,
    WardShiftSignoff,
    Admission,
    AdmissionStatus,
    Handover,
    HandoverStatus,
    ShiftType,
    RiskLevel,
    Role,
    AuditLog,
    AiUsageLog,
    Ward,
    UserWardAssignment,
)
from app.schemas import EscalationIn, EscalationUpdate, TaskIn, TaskUpdate, SignoffIn, AiSummaryIn
from app.deps import (
    get_current_user,
    assert_ward_access,
    write_audit,
    current_shift,
    previous_shift,
    next_shift,
    user_ward_ids,
    ward_filter,
    REVIEWERS,
    SUPERINTENDENTS,
    get_shift_assignment,
    is_rostered_for_shift,
    assert_can_edit_handover,
)
from app.ai import summarize_sbar, transcribe_voice

router = APIRouter(tags=["ops"])


@router.get("/meta/shift")
def meta_shift():
    st, sd = current_shift()
    return {
        "shift_type": st.value,
        "shift_date": str(sd),
        "timezone": TIMEZONE_NAME,
        "hospital_name": settings.hospital_name,
        "windows": {
            "morning": f"{settings.morning_start:02d}:00–{settings.morning_end:02d}:00",
            "afternoon": f"{settings.afternoon_start:02d}:00–{settings.afternoon_end:02d}:00",
            "evening": f"{settings.evening_start:02d}:00–{settings.evening_end:02d}:00 (+1)",
        },
        "shifts": ["morning", "afternoon", "evening"],
        "previous_shift": previous_shift(st, sd)[0].value,
        "previous_shift_date": str(previous_shift(st, sd)[1]),
    }


@router.get("/wards/{ward_id}/board")
def ward_board(
    ward_id: int,
    shift_type: ShiftType | None = None,
    shift_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_ward_access(db, user, ward_id)
    st, sd = current_shift()
    shift_type = shift_type or st
    shift_date = shift_date or sd
    admissions = (
        db.query(Admission)
        .options(joinedload(Admission.patient), joinedload(Admission.ward))
        .filter(Admission.ward_id == ward_id, Admission.status == AdmissionStatus.active)
        .order_by(Admission.bed_number)
        .all()
    )
    handovers = (
        db.query(Handover)
        .options(joinedload(Handover.author))
        .filter(
            Handover.admission_id.in_([a.id for a in admissions] or [0]),
            Handover.shift_type == shift_type,
            Handover.shift_date == shift_date,
        )
        .all()
    )
    by_adm = {h.admission_id: h for h in handovers}
    outgoing: dict[int, dict] = {}
    for h in handovers:
        if not h.author:
            continue
        rec = outgoing.setdefault(h.author_id, {"id": h.author_id, "full_name": h.author.full_name, "handover_count": 0})
        rec["handover_count"] += 1
    signoff = (
        db.query(WardShiftSignoff)
        .options(joinedload(WardShiftSignoff.signed_by), joinedload(WardShiftSignoff.outgoing_nurse))
        .filter(
            WardShiftSignoff.ward_id == ward_id,
            WardShiftSignoff.shift_type == shift_type,
            WardShiftSignoff.shift_date == shift_date,
        )
        .first()
    )
    patients = []
    for a in admissions:
        h = by_adm.get(a.id)
        patients.append(
            {
                "admission_id": a.id,
                "patient_id": a.patient_id,
                "name": a.patient.name,
                "age": a.patient.age,
                "sex": a.patient.sex.value,
                "bed_number": a.bed_number,
                "diagnosis": a.diagnosis,
                "handover_id": h.id if h else None,
                "status": h.status.value if h else "missing",
                "risk_level": h.risk_level.value if h else "stable",
                "critical_flag": h.critical_flag if h else False,
                "outgoing_nurse": h.author.full_name if h and h.author else None,
            }
        )
    incomplete = [p for p in patients if p["status"] in ("missing", "draft", "returned")]
    critical_unreviewed = [
        p
        for p in patients
        if p["risk_level"] == "critical" and p["status"] not in ("accepted",)
    ]
    assignment = get_shift_assignment(db, ward_id, shift_type, shift_date)
    nxt_st, nxt_sd = next_shift(shift_type, shift_date)
    incoming = get_shift_assignment(db, ward_id, nxt_st, nxt_sd)
    can_write = is_rostered_for_shift(db, user, ward_id, shift_type, shift_date)
    can_receive = False
    if signoff is None and user.id != (assignment.nurse_id if assignment else None):
        if user.role in REVIEWERS:
            can_receive = True
        elif user.role == Role.nursing_officer and incoming and incoming.nurse_id == user.id:
            can_receive = True
    def _nurse(row):
        if not row or not row.nurse:
            return None
        return {"id": row.nurse_id, "full_name": row.nurse.full_name}
    return {
        "ward_id": ward_id,
        "shift_type": shift_type.value,
        "shift_date": str(shift_date),
        "patients": patients,
        "outgoing_nurses": list(outgoing.values()),
        "assigned_nurse": _nurse(assignment),
        "incoming_nurse": _nurse(incoming),
        "next_shift_type": nxt_st.value,
        "next_shift_date": str(nxt_sd),
        "can_write": can_write,
        "can_receive": can_receive,
        "signoff": {
            "id": signoff.id,
            "signed_by_id": signoff.signed_by_id,
            "signed_by_name": signoff.signed_by.full_name if signoff.signed_by else None,
            "outgoing_nurse_id": signoff.outgoing_nurse_id,
            "outgoing_nurse_name": signoff.outgoing_nurse.full_name if signoff.outgoing_nurse else None,
            "signed_at": signoff.signed_at.isoformat(),
            "notes": signoff.notes,
            "patient_count": signoff.patient_count,
        }
        if signoff
        else None,
        "blockers": {
            "incomplete": incomplete,
            "critical_unreviewed": critical_unreviewed,
            "can_signoff": len(incomplete) == 0 and len(critical_unreviewed) == 0 and signoff is None,
        },
    }


@router.post("/signoff")
def signoff(
    body: SignoffIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS | {Role.nursing_officer}:
        raise HTTPException(403, "Incoming nurse or supervisor must receive the handover")
    assert_ward_access(db, user, body.ward_id)
    outgoing = db.get(User, body.outgoing_nurse_id)
    if not outgoing or not outgoing.is_active:
        raise HTTPException(400, "Outgoing nurse not found")
    if outgoing.id == user.id:
        raise HTTPException(400, "Incoming nurse must be different from the outgoing nurse")
    nxt_st, nxt_sd = next_shift(body.shift_type, body.shift_date)
    incoming_slot = get_shift_assignment(db, body.ward_id, nxt_st, nxt_sd)
    if user.role == Role.nursing_officer:
        if not incoming_slot or incoming_slot.nurse_id != user.id:
            raise HTTPException(403, "Only the nurse assigned to the next shift can receive this handover")
    board = ward_board(body.ward_id, body.shift_type, body.shift_date, db, user)
    if not board["blockers"]["can_signoff"]:
        raise HTTPException(400, detail={"message": "Handover cannot be received yet", "blockers": board["blockers"]})
    authors = {n["id"] for n in board["outgoing_nurses"]}
    if body.outgoing_nurse_id not in authors:
        raise HTTPException(400, "Outgoing nurse did not author this shift's handovers")
    row = WardShiftSignoff(
        ward_id=body.ward_id,
        shift_type=body.shift_type,
        shift_date=body.shift_date,
        signed_by_id=user.id,
        outgoing_nurse_id=body.outgoing_nurse_id,
        notes=body.notes,
        patient_count=len(board["patients"]),
    )
    db.add(row)
    db.commit()
    write_audit(db, user, "signoff", "ward_shift", row.id, request=request)
    return {"ok": True, "id": row.id, "patient_count": row.patient_count}


@router.get("/escalations")
def list_escalations(
    status: EscalationStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    allowed = user_ward_ids(db, user)
    q = (
        db.query(Escalation)
        .join(Handover)
        .join(Admission)
        .options(joinedload(Escalation.handover).joinedload(Handover.admission).joinedload(Admission.patient))
        .filter(ward_filter(Admission.ward_id, allowed))
    )
    if status:
        q = q.filter(Escalation.status == status)
    rows = q.order_by(Escalation.created_at.desc()).all()
    out = []
    for e in rows:
        p = e.handover.admission.patient
        out.append(
            {
                "id": e.id,
                "handover_id": e.handover_id,
                "severity": e.severity.value,
                "status": e.status.value,
                "description": e.description,
                "resolution_notes": e.resolution_notes,
                "created_at": e.created_at.isoformat(),
                "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
                "raised_by_id": e.raised_by_id,
                "assigned_to_id": e.assigned_to_id,
                "patient_name": p.name if p else None,
                "ward_id": e.handover.admission.ward_id,
            }
        )
    return out


@router.post("/escalations")
def create_escalation(
    body: EscalationIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = db.get(Handover, body.handover_id)
    if not h:
        raise HTTPException(404, "Handover not found")
    assert_ward_access(db, user, h.admission.ward_id)
    e = Escalation(
        handover_id=body.handover_id,
        raised_by_id=user.id,
        severity=body.severity,
        description=body.description,
        status=EscalationStatus.open,
    )
    db.add(e)
    db.commit()
    write_audit(db, user, "create", "escalation", e.id, request=request)
    return {"id": e.id}


@router.patch("/escalations/{eid}")
def update_escalation(
    eid: int,
    body: EscalationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    e = db.get(Escalation, eid)
    if not e:
        raise HTTPException(404)
    h = db.get(Handover, e.handover_id)
    assert_ward_access(db, user, h.admission.ward_id)
    if body.status == EscalationStatus.resolved and user.role not in REVIEWERS:
        raise HTTPException(403, "Nursing officers cannot resolve escalations")
    if body.status:
        e.status = body.status
        if body.status == EscalationStatus.resolved:
            e.resolved_at = ist_now()
    if body.assigned_to_id:
        e.assigned_to_id = body.assigned_to_id
    if body.resolution_notes is not None:
        e.resolution_notes = body.resolution_notes
    if body.escalate_up:
        e.status = EscalationStatus.in_progress
        e.severity = EscalationSeverity.critical
        sup = (
            db.query(User)
            .filter(User.role == Role.nursing_superintendent, User.is_active.is_(True))
            .first()
        )
        if sup:
            e.assigned_to_id = sup.id
        db.commit()
        write_audit(db, user, "escalate", "escalation", e.id, request=request)
        return {"ok": True, "assigned_to_id": e.assigned_to_id}
    db.commit()
    action = "approve" if body.status == EscalationStatus.resolved else "update"
    write_audit(db, user, action, "escalation", e.id, request=request)
    return {"ok": True}


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    allowed = user_ward_ids(db, user)
    rows = (
        db.query(Task)
        .join(Admission)
        .options(joinedload(Task.admission).joinedload(Admission.patient))
        .filter(ward_filter(Admission.ward_id, allowed))
        .order_by(Task.due_at.asc().nullslast())
        .all()
    )
    return [
        {
            "id": t.id,
            "admission_id": t.admission_id,
            "assignee_id": t.assignee_id,
            "title": t.title,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "priority": t.priority,
            "status": t.status.value,
            "patient_name": t.admission.patient.name if t.admission and t.admission.patient else None,
            "overdue": bool(t.due_at and t.due_at < ist_now() and t.status != TaskStatus.done),
        }
        for t in rows
    ]


@router.post("/tasks")
def create_task(
    body: TaskIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = db.get(Admission, body.admission_id)
    if not a:
        raise HTTPException(404)
    assert_ward_access(db, user, a.ward_id)
    t = Task(
        admission_id=body.admission_id,
        assignee_id=body.assignee_id,
        created_by_id=user.id,
        title=body.title,
        due_at=body.due_at,
        priority=body.priority,
    )
    db.add(t)
    db.commit()
    write_audit(db, user, "assign_action", "task", t.id, request=request)
    return {"id": t.id}


@router.patch("/tasks/{tid}")
def update_task(
    tid: int,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(404)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    st, sd = current_shift()
    allowed = user_ward_ids(db, user)
    wards = db.query(Ward).filter(ward_filter(Ward.id, allowed)).all()
    open_esc = (
        db.query(func.count(Escalation.id))
        .join(Handover)
        .join(Admission)
        .filter(
            Escalation.status != EscalationStatus.resolved,
            ward_filter(Admission.ward_id, allowed),
        )
        .scalar()
        or 0
    )
    overdue_tasks = (
        db.query(func.count(Task.id))
        .join(Admission)
        .filter(
            Task.due_at < ist_now(),
            Task.status != TaskStatus.done,
            ward_filter(Admission.ward_id, allowed),
        )
        .scalar()
        or 0
    )
    ward_stats = []
    for w in wards:
        ads = (
            db.query(Admission)
            .filter(Admission.ward_id == w.id, Admission.status == AdmissionStatus.active)
            .all()
        )
        total = len(ads)
        hs = (
            db.query(Handover)
            .filter(
                Handover.admission_id.in_([a.id for a in ads] or [0]),
                Handover.shift_type == st,
                Handover.shift_date == sd,
            )
            .all()
        )
        submitted = len([h for h in hs if h.status != HandoverStatus.draft])
        accepted = len([h for h in hs if h.status == HandoverStatus.accepted])
        critical = len([h for h in hs if h.risk_level == RiskLevel.critical])
        signed = (
            db.query(WardShiftSignoff)
            .filter(
                WardShiftSignoff.ward_id == w.id,
                WardShiftSignoff.shift_type == st,
                WardShiftSignoff.shift_date == sd,
            )
            .first()
        )
        ward_stats.append(
            {
                "ward_id": w.id,
                "name": w.name,
                "department": w.department,
                "patients": total,
                "submitted": submitted,
                "accepted": accepted,
                "critical": critical,
                "signed_off": bool(signed),
                "completion_pct": round(100 * submitted / total) if total else 100,
            }
        )
    pending_reviews = (
        db.query(func.count(Handover.id))
        .join(Admission)
        .filter(
            Handover.status.in_([HandoverStatus.submitted, HandoverStatus.under_review]),
            Handover.shift_type == st,
            Handover.shift_date == sd,
            ward_filter(Admission.ward_id, allowed),
        )
        .scalar()
        or 0
    )
    return {
        "shift_type": st.value,
        "shift_date": str(sd),
        "critical_alerts": open_esc + sum(w["critical"] for w in ward_stats),
        "staffing": [
            {
                "ward_id": w.id,
                "name": w.name,
                "assigned_staff": db.query(func.count(UserWardAssignment.id))
                .filter(UserWardAssignment.ward_id == w.id)
                .scalar()
                or 0,
            }
            for w in wards
        ],
        "open_escalations": open_esc,
        "overdue_tasks": overdue_tasks,
        "pending_reviews": pending_reviews,
        "wards": ward_stats,
        "role": user.role.value,
    }


@router.get("/reports/compliance")
def compliance(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = dashboard(db, user)
    return {"wards": data["wards"], "shift_type": data["shift_type"], "shift_date": data["shift_date"]}


@router.get("/audit")
def audit(
    entity_type: str | None = None,
    entity_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)
    if user.role not in SUPERINTENDENTS | {Role.hod, Role.nursing_supervisor}:
        q = q.filter(AuditLog.user_id == user.id)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == str(entity_id))
    rows = q.all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "diff": r.diff,
            "ip": r.ip,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/ai/summary")
def ai_summary(
    body: AiSummaryIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = body.payload
    if body.handover_id:
        h = db.get(Handover, body.handover_id)
        if h:
            assert_ward_access(db, user, h.admission.ward_id)
            payload = {
                "diagnosis": h.diagnosis,
                "reason": h.reason_for_admission,
                "situation": h.current_situation,
                "concern": h.immediate_concern,
                "vitals": h.vitals,
                "exams": h.system_exams,
                "findings": h.significant_findings,
                "meds": h.medications,
                "history": h.medical_history,
            }
    text, provider = summarize_sbar(payload)
    db.add(AiUsageLog(user_id=user.id, handover_id=body.handover_id, feature="summary"))
    if body.handover_id:
        h = db.get(Handover, body.handover_id)
        if h:
            h.ai_summary = text
    db.commit()
    write_audit(db, user, "ai_summary", "handover", body.handover_id, request=None)
    return {"draft": text, "provider": provider}


@router.post("/ai/voice")
async def ai_voice(
    file: UploadFile = File(...),
    handover_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await file.read()
    if handover_id:
        h = (
            db.query(Handover)
            .options(joinedload(Handover.admission))
            .filter(Handover.id == handover_id)
            .first()
        )
        if h:
            assert_ward_access(db, user, h.admission.ward_id)
            assert_can_edit_handover(db, user, h)
    try:
        text, provider = transcribe_voice(data, file.content_type, file.filename)
    except Exception as exc:
        return {
            "text": f"[Voice transcription failed: {exc}]",
            "provider": "error",
        }
    db.add(AiUsageLog(user_id=user.id, handover_id=handover_id, feature="voice"))
    db.commit()
    return {"text": text, "provider": provider}
