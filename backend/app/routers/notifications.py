from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload

from app.clock import now as ist_now
from app.database import get_db
from app.deps import get_current_user
from app.events import record_event
from app.models import Notification, NotificationRead, Task, TaskStatus, User
from app.pdf_reports import notifications_pdf

router = APIRouter(tags=["notifications"])


def ensure_task_due(db: Session) -> None:
    now = ist_now()
    tasks = (
        db.query(Task)
        .options(joinedload(Task.admission))
        .filter(Task.status != TaskStatus.done, Task.due_at.isnot(None), Task.due_at <= now)
        .all()
    )
    changed = False
    for task in tasks:
        admission = task.admission
        row = record_event(
            db,
            kind="task_due",
            title="Task due",
            body=task.title,
            patient_id=admission.patient_id if admission else None,
            ward_id=admission.ward_id if admission else None,
            entity_key=f"task:{task.id}",
        )
        if row is not None:
            changed = True
    if changed:
        db.commit()


def _rows(db: Session, user: User, patient_id: int | None, ward_id: int | None) -> list[dict]:
    ensure_task_due(db)
    q = db.query(Notification).options(joinedload(Notification.patient), joinedload(Notification.ward))
    if patient_id:
        q = q.filter(Notification.patient_id == patient_id)
    if ward_id:
        q = q.filter(Notification.ward_id == ward_id)
    notes = q.order_by(Notification.created_at.desc()).all()
    read_ids = {
        r.notification_id
        for r in db.query(NotificationRead).filter(NotificationRead.user_id == user.id).all()
    }
    out = []
    for note in notes:
        out.append(
            {
                "id": note.id,
                "kind": note.kind,
                "title": note.title,
                "body": note.body,
                "patient_id": note.patient_id,
                "patient_name": note.patient.name if note.patient else None,
                "ward_id": note.ward_id,
                "ward_name": note.ward.name if note.ward else None,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "read": note.id in read_ids,
            }
        )
    return out


@router.get("/notifications")
def list_notifications(
    patient_id: int | None = None,
    ward_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _rows(db, user, patient_id, ward_id)


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    note = db.get(Notification, notification_id)
    if not note:
        return {"ok": False}
    existing = (
        db.query(NotificationRead)
        .filter(NotificationRead.user_id == user.id, NotificationRead.notification_id == notification_id)
        .first()
    )
    if not existing:
        db.add(NotificationRead(user_id=user.id, notification_id=notification_id, read_at=ist_now()))
        db.commit()
    return {"ok": True}


@router.get("/notifications/download.pdf")
def download_notifications(
    patient_id: int | None = None,
    ward_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = notifications_pdf(_rows(db, user, patient_id, ward_id))
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=notification-summary.pdf"},
    )
