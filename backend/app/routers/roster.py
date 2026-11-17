from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.events import record_event
from app.models import (
    User,
    Role,
    UserWardAssignment,
    ShiftAssignment,
    ShiftType,
    Admission,
    AdmissionStatus,
    PatientShiftAssignment,
)
from app.schemas import ShiftAssignmentIn
from app.deps import (
    get_current_user,
    assert_ward_access,
    write_audit,
    REVIEWERS,
    PATIENT_ASSIGNERS,
    current_shift,
    list_shift_assignments,
    user_ward_ids,
)

router = APIRouter(tags=["roster"])


def _serialize(row: ShiftAssignment) -> dict:
    return {
        "id": row.id,
        "ward_id": row.ward_id,
        "shift_type": row.shift_type.value,
        "shift_date": str(row.shift_date),
        "nurse_id": row.nurse_id,
        "nurse_name": row.nurse.full_name if row.nurse else None,
        "assigned_by_id": row.assigned_by_id,
        "assigned_by_name": row.assigned_by.full_name if row.assigned_by else None,
    }


@router.get("/wards/{ward_id}/officers")
def list_ward_officers(
    ward_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_ward_access(db, user, ward_id)
    rows = (
        db.query(User)
        .join(UserWardAssignment, UserWardAssignment.user_id == User.id)
        .filter(
            UserWardAssignment.ward_id == ward_id,
            User.role == Role.nursing_officer,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "employee_id": u.employee_id} for u in rows]


@router.get("/shift-assignments")
def list_assignments(
    ward_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, today = current_shift()
    start = start or today
    end = end or (today + timedelta(days=2))
    allowed = user_ward_ids(db, user)
    q = (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(ShiftAssignment.shift_date >= start, ShiftAssignment.shift_date <= end)
        .filter(ShiftAssignment.ward_id.in_(allowed or [0]))
    )
    if ward_id:
        assert_ward_access(db, user, ward_id)
        q = q.filter(ShiftAssignment.ward_id == ward_id)
    rows = q.order_by(ShiftAssignment.shift_date, ShiftAssignment.shift_type).all()
    return [_serialize(r) for r in rows]


@router.post("/shift-assignments")
def assign_shift(
    body: ShiftAssignmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS:
        raise HTTPException(403, "Supervisors assign nursing officer shifts")
    assert_ward_access(db, user, body.ward_id)
    nurse = db.get(User, body.nurse_id)
    if not nurse or not nurse.is_active or nurse.role != Role.nursing_officer:
        raise HTTPException(400, "Assign a nursing officer")
    linked = (
        db.query(UserWardAssignment)
        .filter(UserWardAssignment.user_id == nurse.id, UserWardAssignment.ward_id == body.ward_id)
        .first()
    )
    if not linked:
        raise HTTPException(400, "That officer is not assigned to this ward")
    row = next(
        (r for r in list_shift_assignments(db, body.ward_id, body.shift_type, body.shift_date) if r.nurse_id == nurse.id),
        None,
    )
    if not row:
        row = ShiftAssignment(
            ward_id=body.ward_id,
            shift_type=body.shift_type,
            shift_date=body.shift_date,
            nurse_id=nurse.id,
            assigned_by_id=user.id,
        )
        db.add(row)
        db.flush()
        record_event(
            db,
            kind="roster_change",
            title="Ward roster updated",
            body=f"{nurse.full_name} added to {body.shift_type.value} {body.shift_date}",
            ward_id=body.ward_id,
        )
    db.commit()
    db.refresh(row)
    row = (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(ShiftAssignment.id == row.id)
        .first()
    )
    write_audit(db, user, "assign_shift", "shift_assignment", row.id, request=request)
    return _serialize(row)


@router.delete("/shift-assignments/{assignment_id}")
def unassign_shift(
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS:
        raise HTTPException(403, "Supervisors assign nursing officer shifts")
    row = db.get(ShiftAssignment, assignment_id)
    if not row:
        raise HTTPException(404, "Assignment not found")
    assert_ward_access(db, user, row.ward_id)
    nurse_name = row.nurse.full_name if row.nurse else "Nurse"
    record_event(
        db,
        kind="roster_change",
        title="Ward roster updated",
        body=f"{nurse_name} removed from {row.shift_type.value} {row.shift_date}",
        ward_id=row.ward_id,
    )
    db.delete(row)
    db.commit()
    write_audit(db, user, "unassign_shift", "shift_assignment", assignment_id, request=request)
    return {"ok": True}


@router.get("/patient-assignments")
def list_patient_assignments(
    ward_id: int,
    shift_type: ShiftType,
    shift_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_ward_access(db, user, ward_id)
    admissions = (
        db.query(Admission)
        .options(joinedload(Admission.patient))
        .filter(Admission.ward_id == ward_id, Admission.status == AdmissionStatus.active)
        .order_by(Admission.bed_number)
        .all()
    )
    assigned = {
        row.admission_id: row
        for row in db.query(PatientShiftAssignment)
        .options(joinedload(PatientShiftAssignment.nurse))
        .filter(PatientShiftAssignment.shift_type == shift_type, PatientShiftAssignment.shift_date == shift_date)
        .all()
        if row.admission_id in {a.id for a in admissions}
    }
    officers = (
        db.query(User)
        .join(UserWardAssignment, UserWardAssignment.user_id == User.id)
        .filter(
            UserWardAssignment.ward_id == ward_id,
            User.role == Role.nursing_officer,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    return {
        "nurses": [{"id": u.id, "full_name": u.full_name} for u in officers],
        "patients": [
            {
                "admission_id": a.id,
                "patient_id": a.patient_id,
                "name": a.patient.name,
                "bed_number": a.bed_number,
                "nurse_id": assigned[a.id].nurse_id if a.id in assigned else None,
                "nurse_name": assigned[a.id].nurse.full_name if a.id in assigned and assigned[a.id].nurse else None,
            }
            for a in admissions
        ],
    }


@router.post("/patient-assignments")
def assign_patient(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in PATIENT_ASSIGNERS:
        raise HTTPException(403, "Department Admin, Nursing Supervisor, or Medical Superintendent assigns patients")
    admission = db.get(Admission, int(body["admission_id"]))
    if not admission or admission.status != AdmissionStatus.active:
        raise HTTPException(404, "Active admission not found")
    assert_ward_access(db, user, admission.ward_id)
    shift_type = ShiftType(body["shift_type"])
    shift_date = date.fromisoformat(str(body["shift_date"]))
    nurse_id = body.get("nurse_id")
    existing = (
        db.query(PatientShiftAssignment)
        .filter(
            PatientShiftAssignment.admission_id == admission.id,
            PatientShiftAssignment.shift_type == shift_type,
            PatientShiftAssignment.shift_date == shift_date,
        )
        .first()
    )
    if not nurse_id:
        if existing:
            db.delete(existing)
            record_event(
                db,
                kind="roster_change",
                title="Patient allocation cleared",
                body=f"{admission.patient.name if admission.patient else 'Patient'} is unassigned for {shift_type.value} {shift_date}",
                patient_id=admission.patient_id,
                ward_id=admission.ward_id,
            )
        db.commit()
        write_audit(db, user, "unassign_patient", "patient_shift", admission.id, request=request)
        return {"ok": True, "nurse_id": None}
    nurse = db.get(User, int(nurse_id))
    if not nurse or not nurse.is_active or nurse.role != Role.nursing_officer:
        raise HTTPException(400, "Choose an active nurse")
    linked = (
        db.query(UserWardAssignment)
        .filter(UserWardAssignment.user_id == nurse.id, UserWardAssignment.ward_id == admission.ward_id)
        .first()
    )
    if not linked:
        raise HTTPException(400, "That nurse is not assigned to this ward")
    roster_ids = {r.nurse_id for r in list_shift_assignments(db, admission.ward_id, shift_type, shift_date)}
    if nurse.id not in roster_ids:
        db.add(
            ShiftAssignment(
                ward_id=admission.ward_id,
                shift_type=shift_type,
                shift_date=shift_date,
                nurse_id=nurse.id,
                assigned_by_id=user.id,
            )
        )
    if existing:
        existing.nurse_id = nurse.id
        existing.assigned_by_id = user.id
    else:
        db.add(
            PatientShiftAssignment(
                admission_id=admission.id,
                shift_type=shift_type,
                shift_date=shift_date,
                nurse_id=nurse.id,
                assigned_by_id=user.id,
            )
        )
    record_event(
        db,
        kind="roster_change",
        title="Patient allocated",
        body=f"{admission.patient.name if admission.patient else 'Patient'} assigned to {nurse.full_name} for {shift_type.value} {shift_date}",
        patient_id=admission.patient_id,
        ward_id=admission.ward_id,
    )
    db.commit()
    write_audit(db, user, "assign_patient", "patient_shift", admission.id, request=request)
    return {"ok": True, "nurse_id": nurse.id}
