from datetime import datetime, timedelta

from app.deps import current_shift, next_shift


def auth(client, email: str) -> dict:
    r = client.post("/auth/login", json={"identifier": email, "password": "ChangeMe123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_supervisor_assigns_shift(client):
    sv = auth(client, "supervisor.s1@hospital.local")
    nurse = auth(client, "nurse.s1.in@hospital.local")
    wards = client.get("/wards", headers=sv).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    officers = client.get(f"/wards/{w['id']}/officers", headers=sv).json()
    rohan = next(o for o in officers if "Rohan" in o["full_name"])
    st, sd = current_shift()
    future = sd + timedelta(days=3)
    r = client.post(
        "/shift-assignments",
        headers=sv,
        json={"ward_id": w["id"], "shift_type": st.value, "shift_date": str(future), "nurse_id": rohan["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nurse_id"] == rohan["id"]
    denied = client.post(
        "/shift-assignments",
        headers=nurse,
        json={"ward_id": w["id"], "shift_type": st.value, "shift_date": str(future), "nurse_id": rohan["id"]},
    )
    assert denied.status_code == 403


def test_incoming_nurse_cannot_edit_previous_sbar(client):
    outgoing = auth(client, "nurse.s1@hospital.local")
    incoming = auth(client, "nurse.s1.in@hospital.local")
    wards = client.get("/wards", headers=outgoing).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    st, sd = current_shift()
    stamp = int(datetime.utcnow().timestamp())
    created = client.post(
        "/patients",
        headers=outgoing,
        json={"name": "Lock Test", "age": 60, "sex": "male", "mrn": f"UHID-LOCK-{stamp}"},
    )
    assert created.status_code == 200, created.text
    adm = client.post(
        "/admissions",
        headers=outgoing,
        json={
            "patient_id": created.json()["id"],
            "ward_id": w["id"],
            "bed_number": "S1-LOCK",
            "diagnosis": "Lock test",
            "reason_for_admission": "Cannot be edited by incoming nurse",
        },
    )
    assert adm.status_code == 200, adm.text
    hid = client.post(
        f"/handovers/ensure?admission_id={adm.json()['id']}&shift_type={st.value}&shift_date={sd}",
        headers=outgoing,
    ).json()["id"]
    client.patch(f"/handovers/{hid}", headers=outgoing, json={"current_situation": "Written by Anjali only"})
    got = client.get(f"/handovers/{hid}", headers=incoming)
    assert got.status_code == 200
    assert got.json()["can_edit"] is False
    blocked = client.patch(
        f"/handovers/{hid}",
        headers=incoming,
        json={"current_situation": "Rohan trying to change Anjali's note"},
    )
    assert blocked.status_code == 403
    still = client.get(f"/handovers/{hid}", headers=outgoing).json()
    assert "Anjali" in (still["current_situation"] or "")


def test_unassigned_officer_cannot_start_sbar(client):
    incoming = auth(client, "nurse.s1.in@hospital.local")
    outgoing = auth(client, "nurse.s1@hospital.local")
    wards = client.get("/wards", headers=outgoing).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    st, sd = current_shift()
    nxt_st, nxt_sd = next_shift(st, sd)
    stamp = int(datetime.utcnow().timestamp())
    created = client.post(
        "/patients",
        headers=outgoing,
        json={"name": "Roster Gate", "age": 50, "sex": "female", "mrn": f"UHID-RG-{stamp}"},
    )
    adm = client.post(
        "/admissions",
        headers=outgoing,
        json={
            "patient_id": created.json()["id"],
            "ward_id": w["id"],
            "bed_number": "S1-RG",
            "diagnosis": "Roster gate",
            "reason_for_admission": "Next shift should create a new note",
        },
    )
    assert adm.status_code == 200
    blocked = client.post(
        f"/handovers/ensure?admission_id={adm.json()['id']}&shift_type={st.value}&shift_date={sd}",
        headers=incoming,
    )
    assert blocked.status_code == 403
    allowed = client.post(
        f"/handovers/ensure?admission_id={adm.json()['id']}&shift_type={nxt_st.value}&shift_date={nxt_sd}",
        headers=incoming,
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["can_edit"] is True


def test_next_shift_carries_forward_previous_sbar(client):
    outgoing = auth(client, "nurse.s1@hospital.local")
    incoming = auth(client, "nurse.s1.in@hospital.local")
    wards = client.get("/wards", headers=outgoing).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    st, sd = current_shift()
    nxt_st, nxt_sd = next_shift(st, sd)
    stamp = int(datetime.utcnow().timestamp())
    created = client.post(
        "/patients",
        headers=outgoing,
        json={"name": "Carry Forward", "age": 55, "sex": "female", "mrn": f"UHID-CF-{stamp}"},
    )
    adm = client.post(
        "/admissions",
        headers=outgoing,
        json={
            "patient_id": created.json()["id"],
            "ward_id": w["id"],
            "bed_number": "S1-CF",
            "diagnosis": "Post-op ileus",
            "reason_for_admission": "Nausea after laparotomy",
        },
    ).json()
    hid = client.post(
        f"/handovers/ensure?admission_id={adm['id']}&shift_type={st.value}&shift_date={sd}",
        headers=outgoing,
    ).json()["id"]
    client.patch(
        f"/handovers/{hid}",
        headers=outgoing,
        json={
            "current_situation": "NG tube draining bilious fluid, abdomen soft.",
            "nursing_care": "Q4H obs, keep NBM",
            "medications": [{"name": "Ondansetron", "dose": "4mg", "route": "IV", "frequency": "Q8H", "notes": ""}],
            "nkda": True,
        },
    )
    nxt = client.post(
        f"/handovers/ensure?admission_id={adm['id']}&shift_type={nxt_st.value}&shift_date={nxt_sd}",
        headers=incoming,
    )
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["id"] != hid
    assert body["can_edit"] is True
    assert body["current_situation"] == "NG tube draining bilious fluid, abdomen soft."
    assert body["nursing_care"] == "Q4H obs, keep NBM"
    assert body["nkda"] is True
    edited = client.patch(
        f"/handovers/{body['id']}",
        headers=incoming,
        json={"current_situation": "NG output reduced; sipping sips of water."},
    )
    assert edited.status_code == 200, edited.text
    assert "reduced" in edited.json()["current_situation"]
    original = client.get(f"/handovers/{hid}", headers=outgoing).json()
    assert "bilious" in original["current_situation"]


def test_officer_cannot_resolve_escalation(client):
    outgoing = auth(client, "nurse.s1@hospital.local")
    sv = auth(client, "supervisor.s1@hospital.local")
    wards = client.get("/wards", headers=outgoing).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    st, sd = current_shift()
    stamp = int(datetime.utcnow().timestamp())
    created = client.post(
        "/patients",
        headers=outgoing,
        json={"name": "Escalation Lock", "age": 70, "sex": "male", "mrn": f"UHID-EL-{stamp}"},
    )
    adm = client.post(
        "/admissions",
        headers=outgoing,
        json={
            "patient_id": created.json()["id"],
            "ward_id": w["id"],
            "bed_number": "S1-EL",
            "diagnosis": "Wound ooze",
            "reason_for_admission": "Escalate test",
        },
    ).json()
    hid = client.post(
        f"/handovers/ensure?admission_id={adm['id']}&shift_type={st.value}&shift_date={sd}",
        headers=outgoing,
    ).json()["id"]
    raised = client.post(
        "/escalations",
        headers=outgoing,
        json={"handover_id": hid, "severity": "high", "description": "Wound dressing soaked through."},
    )
    assert raised.status_code == 200, raised.text
    eid = raised.json()["id"]
    blocked = client.patch(
        f"/escalations/{eid}",
        headers=outgoing,
        json={"status": "resolved", "resolution_notes": "Nurse closed this"},
    )
    assert blocked.status_code == 403
    ok = client.patch(
        f"/escalations/{eid}",
        headers=sv,
        json={"status": "resolved", "resolution_notes": "Reviewed by supervisor"},
    )
    assert ok.status_code == 200, ok.text
