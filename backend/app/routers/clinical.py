from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Patient, Admission, AdmissionStatus, User, Role
from app.schemas import PatientIn, PatientOut, AdmissionIn, AdmissionOut, TransferIn
from app.deps import get_current_user, assert_ward_access, write_audit, ADMINS, REVIEWERS, user_ward_ids, ward_filter

router = APIRouter(tags=["clinical"])


@router.get("/patients", response_model=list[PatientOut])
def list_patients(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Patient).order_by(Patient.name).all()


@router.post("/patients", response_model=PatientOut)
def create_patient(
    body: PatientIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = body.model_dump()
    mrn = (data.get("mrn") or "").strip() or None
    data["mrn"] = mrn
    if mrn:
        taken = db.query(Patient).filter(func.lower(Patient.mrn) == mrn.lower()).first()
        if taken:
            raise HTTPException(400, "MRN / UHID already exists")
    p = Patient(**data)
    db.add(p)
    db.commit()
    db.refresh(p)
    write_audit(db, user, "create", "patient", p.id, request=request)
    return p


@router.get("/admissions", response_model=list[AdmissionOut])
def list_admissions(
    ward_id: int | None = None,
    status: AdmissionStatus | None = AdmissionStatus.active,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Admission).options(joinedload(Admission.patient), joinedload(Admission.ward))
    allowed = user_ward_ids(db, user)
    q = q.filter(ward_filter(Admission.ward_id, allowed))
    if ward_id:
        assert_ward_access(db, user, ward_id)
        q = q.filter(Admission.ward_id == ward_id)
    if status:
        q = q.filter(Admission.status == status)
    return q.order_by(Admission.bed_number).all()


@router.post("/admissions", response_model=AdmissionOut)
def create_admission(
    body: AdmissionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_ward_access(db, user, body.ward_id)
    if not db.get(Patient, body.patient_id):
        raise HTTPException(404, "Patient not found")
    a = Admission(**body.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    write_audit(db, user, "create", "admission", a.id, request=request)
    return (
        db.query(Admission)
        .options(joinedload(Admission.patient), joinedload(Admission.ward))
        .filter(Admission.id == a.id)
        .first()
    )


@router.post("/admissions/{admission_id}/transfer", response_model=AdmissionOut)
def transfer_admission(
    admission_id: int,
    body: TransferIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    a = db.get(Admission, admission_id)
    if not a or a.status != AdmissionStatus.active:
        raise HTTPException(404, "Active admission not found")
    assert_ward_access(db, user, a.ward_id)
    assert_ward_access(db, user, body.ward_id)
    a.status = AdmissionStatus.transferred
    a.discharged_at = datetime.utcnow()
    new_a = Admission(
        patient_id=a.patient_id,
        ward_id=body.ward_id,
        bed_number=body.bed_number,
        diagnosis=a.diagnosis,
        reason_for_admission=a.reason_for_admission,
        status=AdmissionStatus.active,
    )
    db.add(new_a)
    db.commit()
    write_audit(db, user, "transfer", "admission", a.id, {"to_ward": body.ward_id}, request)
    return (
        db.query(Admission)
        .options(joinedload(Admission.patient), joinedload(Admission.ward))
        .filter(Admission.id == new_a.id)
        .first()
    )


@router.post("/admissions/{admission_id}/discharge")
def discharge(
    admission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS | ADMINS and user.role != Role.nursing_officer:
        raise HTTPException(403, "Cannot discharge")
    a = db.get(Admission, admission_id)
    if not a:
        raise HTTPException(404, "Admission not found")
    assert_ward_access(db, user, a.ward_id)
    a.status = AdmissionStatus.discharged
    a.discharged_at = datetime.utcnow()
    db.commit()
    write_audit(db, user, "discharge", "admission", a.id, request=request)
    return {"ok": True}
