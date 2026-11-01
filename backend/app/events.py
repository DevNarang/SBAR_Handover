from sqlalchemy.orm import Session

from app.models import Notification


def record_event(
    db: Session,
    *,
    kind: str,
    title: str,
    body: str = "",
    patient_id: int | None = None,
    ward_id: int | None = None,
    entity_key: str | None = None,
) -> Notification | None:
    if entity_key:
        existing = (
            db.query(Notification)
            .filter(Notification.kind == kind, Notification.entity_key == entity_key)
            .first()
        )
        if existing:
            return None
    row = Notification(
        kind=kind,
        title=title,
        body=body,
        patient_id=patient_id,
        ward_id=ward_id,
        entity_key=entity_key,
    )
    db.add(row)
    return row
