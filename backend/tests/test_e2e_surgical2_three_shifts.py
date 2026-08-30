"""End-to-end: Surgical Ward 2, Rohan morning → Anjali afternoon (escalation) → Rohan evening."""

from datetime import datetime

from app.seed import SYSTEMS


DAY = "2026-08-19"
PASSWORD = "ChangeMe123!"

ROHAN_MORNING = {
    "diagnosis": "Laparoscopic cholecystectomy — day 1",
    "reason_for_admission": "Elective cholecystectomy; admitted to Surgical Ward 2",
    "current_situation": "Comfortable, sipping water, wound dry, no drain.",
    "immediate_concern": "",
    "critical_flag": False,
    "risk_level": "stable",
    "medical_history": [{"item": "Gallstones", "notes": "symptomatic"}],
    "surgical_history": [{"item": "Lap chole", "notes": "this morning"}],
    "medications": [{"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""}],
    "nkda": True,
    "allergies": [],
    "vitals": {"temp": 36.7, "bp_systolic": 122, "bp_diastolic": 76, "pr": 78, "rr": 16, "spo2": 98},
    "system_exams": {s: {"status": "normal", "notes": ""} for s in SYSTEMS},
    "significant_findings": "Abdomen soft, four port sites dry.",
    "diagnostics": [],
    "immediate_treatment": "Analgesia, early mobilisation.",
    "nursing_care": "Q4H obs, wound check, encourage oral fluids.",
    "team_communication": "Surgeon happy; diet as tolerated.",
    "follow_up": "TWOC not required. Home tomorrow if well.",
    "home_care_needs": "Wound advice leaflet.",
}

ANJALI_AFTERNOON = {
    "current_situation": "New pyrexia 38.4, wound slightly erythematous, more pain on movement.",
    "immediate_concern": "Possible early wound infection — surgical review requested.",
    "critical_flag": False,
    "risk_level": "watch",
    "risk_override_reason": "Fever and wound change this afternoon",
    "significant_findings": "Port sites: umbilical slightly red, no pus. Abdomen otherwise soft.",
    "immediate_treatment": "Cultures, paracetamol, surgical SHO informed.",
    "nursing_care": "Q2H temp, wound photos, keep NBM until review.",
    "team_communication": "Escalated to ward supervisor and surgical SHO.",
}


def login(client, email: str) -> dict:
    r = client.post("/auth/login", json={"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_e2e_surgical_ward_2_three_shifts(client):
    results = []
    sv = login(client, "supervisor.s1@hospital.local")
    ns = login(client, "nursing.super@hospital.local")
    rohan = login(client, "nurse.s1.in@hospital.local")
    anjali = login(client, "nurse.s1@hospital.local")

    wards = client.get("/wards", headers=sv).json()
    s2 = next(w for w in wards if w["name"] == "Surgical Ward 2")
    users = client.get("/users", headers=ns).json()
    rohan_u = next(u for u in users if u["email"] == "nurse.s1.in@hospital.local")
    anjali_u = next(u for u in users if u["email"] == "nurse.s1@hospital.local")

    for u in (rohan_u, anjali_u):
        ids = list({*u["ward_ids"], s2["id"]})
        patched = client.patch(f"/users/{u['id']}", headers=ns, json={"ward_ids": ids})
        assert patched.status_code == 200, patched.text
    results.append("Staff assigned to Surgical Ward 2")

    for shift, nurse_id in (
        ("morning", rohan_u["id"]),
        ("afternoon", anjali_u["id"]),
        ("evening", rohan_u["id"]),
    ):
        r = client.post(
            "/shift-assignments",
            headers=sv,
            json={"ward_id": s2["id"], "shift_type": shift, "shift_date": DAY, "nurse_id": nurse_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["nurse_id"] == nurse_id
    results.append("Roster: Rohan morning, Anjali afternoon, Rohan evening")

    stamp = int(datetime.utcnow().timestamp())
    patient = client.post(
        "/patients",
        headers=sv,
        json={"name": "Meera Krishnan", "age": 46, "sex": "female", "mrn": f"UHID-S2-E2E-{stamp}"},
    )
    assert patient.status_code == 200, patient.text
    adm = client.post(
        "/admissions",
        headers=sv,
        json={
            "patient_id": patient.json()["id"],
            "ward_id": s2["id"],
            "bed_number": "S2-E2E",
            "diagnosis": ROHAN_MORNING["diagnosis"],
            "reason_for_admission": ROHAN_MORNING["reason_for_admission"],
        },
    )
    assert adm.status_code == 200, adm.text
    admission_id = adm.json()["id"]
    results.append(f"Supervisor admitted Meera Krishnan to Surgical Ward 2 bed S2-E2E (admission {admission_id})")

    morning = client.post(
        f"/handovers/ensure?admission_id={admission_id}&shift_type=morning&shift_date={DAY}",
        headers=rohan,
    )
    assert morning.status_code == 200, morning.text
    assert morning.json()["can_edit"] is True
    mid = morning.json()["id"]
    patched = client.patch(f"/handovers/{mid}", headers=rohan, json=ROHAN_MORNING)
    assert patched.status_code == 200, patched.text
    submitted = client.post(f"/handovers/{mid}/submit", headers=rohan)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["critical_flag"] is False
    results.append("Rohan submitted morning SBAR — stable, no escalation")

    afternoon = client.post(
        f"/handovers/ensure?admission_id={admission_id}&shift_type=afternoon&shift_date={DAY}",
        headers=anjali,
    )
    assert afternoon.status_code == 200, afternoon.text
    body = afternoon.json()
    assert body["can_edit"] is True
    assert body["id"] != mid
    assert body["current_situation"] == ROHAN_MORNING["current_situation"]
    assert body["previous_author_name"] and "Rohan" in body["previous_author_name"]
    aid = body["id"]
    edited = client.patch(f"/handovers/{aid}", headers=anjali, json=ANJALI_AFTERNOON)
    assert edited.status_code == 200, edited.text
    sub_pm = client.post(f"/handovers/{aid}/submit", headers=anjali)
    assert sub_pm.status_code == 200, sub_pm.text
    results.append("Anjali received Rohan's morning SBAR, updated afternoon details, submitted")

    esc = client.post(
        "/escalations",
        headers=anjali,
        json={
            "handover_id": aid,
            "severity": "high",
            "description": "New fever 38.4 and erythematous umbilical port — possible wound infection. Surgical SHO informed.",
        },
    )
    assert esc.status_code == 200, esc.text
    eid = esc.json()["id"]
    blocked = client.patch(
        f"/escalations/{eid}",
        headers=anjali,
        json={"status": "resolved", "resolution_notes": "Nurse should not close this"},
    )
    assert blocked.status_code == 403
    resolved = client.patch(
        f"/escalations/{eid}",
        headers=sv,
        json={"status": "resolved", "resolution_notes": "SHO reviewed. Oral co-amoxiclav started. Continue Q2H temp. Not for return to theatre tonight."},
    )
    assert resolved.status_code == 200, resolved.text
    results.append("Afternoon escalation raised by Anjali; supervisor resolved it. Anjali could not resolve.")

    evening = client.post(
        f"/handovers/ensure?admission_id={admission_id}&shift_type=evening&shift_date={DAY}",
        headers=rohan,
    )
    assert evening.status_code == 200, evening.text
    ev = evening.json()
    assert ev["can_edit"] is True
    assert ev["id"] not in {mid, aid}
    assert ev["current_situation"] == ANJALI_AFTERNOON["current_situation"]
    assert ev["nursing_care"] == ANJALI_AFTERNOON["nursing_care"]
    assert ev["previous_author_name"] and "Anjali" in ev["previous_author_name"]
    still = client.get(f"/handovers/{ev['id']}", headers=rohan).json()
    assert still["current_situation"] == ANJALI_AFTERNOON["current_situation"]
    submitted_ev = client.post(f"/handovers/{ev['id']}/submit", headers=rohan)
    assert submitted_ev.status_code == 200, submitted_ev.text
    assert submitted_ev.json()["current_situation"] == ANJALI_AFTERNOON["current_situation"]
    results.append("Rohan evening SBAR carried Anjali's afternoon details with no further edits, then submitted")

    morning_locked = client.get(f"/handovers/{mid}", headers=anjali).json()
    assert morning_locked["can_edit"] is False
    assert morning_locked["current_situation"] == ROHAN_MORNING["current_situation"]
    results.append("Rohan's original morning SBAR remains unchanged")

    print("\n".join(f"PASS — {line}" for line in results))
