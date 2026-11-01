from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _pdf(title: str, lines: list[str]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
    for line in lines:
        text = (line or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(text.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()


def handover_pdf(h: dict, extras: dict) -> bytes:
    patient = h.get("patient") or {}
    admission = h.get("admission") or {}
    lines = [
        f"Patient: {patient.get('name')} · {patient.get('age')} / {patient.get('sex')} · MRN {patient.get('mrn') or '—'}",
        f"Ward: {admission.get('ward_name')} · Bed {admission.get('bed_number')}",
        f"Shift: {h.get('shift_type')} {h.get('shift_date')} · Status {h.get('status')} · Risk {h.get('risk_level')}",
        f"Written by: {h.get('author_name') or '—'}",
        f"Received by: {extras.get('received_by') or '—'}",
        f"Diagnosis: {h.get('diagnosis') or admission.get('diagnosis') or '—'}",
        f"Reason for admission: {h.get('reason_for_admission') or '—'}",
        f"Situation: {h.get('current_situation') or '—'}",
        f"Immediate concern: {h.get('immediate_concern') or '—'}",
        f"Medical history: {_pairs(h.get('medical_history'), 'item', 'notes')}",
        f"Surgical history: {_pairs(h.get('surgical_history'), 'item', 'notes')}",
        f"Medications: {_meds(h.get('medications'))}",
        f"Allergies: {'NKDA' if h.get('nkda') else _pairs(h.get('allergies'), 'allergen', 'reaction')}",
        f"Vitals: {_vitals(h.get('vitals'))}",
        f"Significant findings: {h.get('significant_findings') or '—'}",
        f"Immediate treatment: {h.get('immediate_treatment') or '—'}",
        f"Nursing care: {h.get('nursing_care') or '—'}",
        f"Team communication: {h.get('team_communication') or '—'}",
        f"Follow up: {h.get('follow_up') or '—'}",
        f"Escalations: {extras.get('escalations') or 'None'}",
        f"Tasks: {extras.get('tasks') or 'None'}",
    ]
    name = patient.get("name") or "Patient"
    return _pdf(f"SBAR handover — {name}", lines)


def notifications_pdf(rows: list[dict]) -> bytes:
    lines = []
    if not rows:
        lines.append("No notifications in this filter.")
    for row in rows:
        state = "Read" if row.get("read") else "Unread"
        lines.append(
            f"{row.get('created_at')} · {state} · {row.get('title')} · {row.get('body')} "
            f"(patient {row.get('patient_name') or '—'}, ward {row.get('ward_name') or '—'})"
        )
    return _pdf("Notification summary", lines)


def _pairs(rows, a: str, b: str) -> str:
    if not rows:
        return "—"
    parts = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parts.append(f"{row.get(a) or ''} {row.get(b) or ''}".strip())
    return "; ".join(p for p in parts if p) or "—"


def _meds(rows) -> str:
    if not rows:
        return "—"
    parts = []
    for row in rows:
        if isinstance(row, dict):
            parts.append(" ".join(str(row.get(k) or "") for k in ("name", "dose", "route", "frequency")).strip())
    return "; ".join(p for p in parts if p) or "—"


def _vitals(vitals: dict | None) -> str:
    if not vitals:
        return "—"
    return ", ".join(f"{k} {v}" for k, v in vitals.items())
