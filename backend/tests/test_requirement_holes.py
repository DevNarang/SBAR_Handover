"""Requirement holes: receive blockers, review, admissions, auth, roles, admin, reports, audit."""

from datetime import date, datetime, timedelta

from app.seed import SYSTEMS

PASSWORD = "ChangeMe123!"
DAY = "2026-11-02"
STABLE = {
    "current_situation": "Stable on the ward, no new concerns.",
    "immediate_concern": "",
    "critical_flag": False,
    "risk_level": "stable",
    "medical_history": [{"item": "As charted", "notes": ""}],
    "medications": [{"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""}],
    "nkda": True,
    "allergies": [],
    "vitals": {"temp": 36.8, "bp_systolic": 120, "bp_diastolic": 80, "pr": 72, "rr": 16, "spo2": 98},
    "system_exams": {s: {"status": "normal", "notes": ""} for s in SYSTEMS},
    "immediate_treatment": "Continue plan",
    "nursing_care": "Q4H obs",
}


def login(client, email: str) -> dict:
    r = client.post("/auth/login", json={"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def stamp() -> str:
    return str(int(datetime.utcnow().timestamp() * 1000))


def complete(diagnosis="Observation", reason="Hole test"):
    return {"diagnosis": diagnosis, "reason_for_admission": reason, **STABLE}


def setup_empty_ward(client, day=DAY):
    sv = login(client, "supervisor.s1@hospital.local")
    ns = login(client, "nursing.super@hospital.local")
    anjali = login(client, "nurse.s1@hospital.local")
    rohan = login(client, "nurse.s1.in@hospital.local")
    tag = stamp()[-8:]
    ward = client.post("/wards", headers=ns, json={"name": f"QA Ward {tag}", "department": "Surgical"})
    assert ward.status_code == 200, ward.text
    wid = ward.json()["id"]
    users = client.get("/users", headers=ns).json()
    anjali_u = next(u for u in users if u["email"] == "nurse.s1@hospital.local")
    rohan_u = next(u for u in users if u["email"] == "nurse.s1.in@hospital.local")
    sv_u = next(u for u in users if u["email"] == "supervisor.s1@hospital.local")
    for u in (anjali_u, rohan_u, sv_u):
        ids = list({*u["ward_ids"], wid})
        assert client.patch(f"/users/{u['id']}", headers=ns, json={"ward_ids": ids}).status_code == 200
    anjali_u = {**anjali_u, "ward_ids": list({*anjali_u["ward_ids"], wid})}
    rohan_u = {**rohan_u, "ward_ids": list({*rohan_u["ward_ids"], wid})}
    for shift, nid in (("morning", anjali_u["id"]), ("afternoon", rohan_u["id"])):
        r = client.post(
            "/shift-assignments",
            headers=ns,
            json={"ward_id": wid, "shift_type": shift, "shift_date": day, "nurse_id": nid},
        )
        assert r.status_code == 200, r.text
    s2 = {"id": wid, "name": ward.json()["name"]}
    return sv, ns, anjali, rohan, s2, anjali_u, rohan_u


setup_s2 = setup_empty_ward


def admit(client, headers, ward_id, bed, name="Hole Patient"):
    p = client.post(
        "/patients",
        headers=headers,
        json={"name": name, "age": 50, "sex": "female", "mrn": f"UHID-HOLE-{stamp()}"},
    )
    assert p.status_code == 200, p.text
    a = client.post(
        "/admissions",
        headers=headers,
        json={
            "patient_id": p.json()["id"],
            "ward_id": ward_id,
            "bed_number": bed,
            "diagnosis": "Observation",
            "reason_for_admission": "Hole test",
        },
    )
    assert a.status_code == 200, a.text
    return a.json()


def start_and_fill(client, headers, admission, shift, day, extra=None):
    h = client.post(
        f"/handovers/ensure?admission_id={admission['id']}&shift_type={shift}&shift_date={day}",
        headers=headers,
    )
    assert h.status_code == 200, h.text
    hid = h.json()["id"]
    body = complete(admission["diagnosis"], admission["reason_for_admission"])
    if extra:
        body.update(extra)
    assert client.patch(f"/handovers/{hid}", headers=headers, json=body).status_code == 200
    return hid


def test_auth_invalid_password_and_lockout(client):
    bad = client.post("/auth/login", json={"identifier": "nobody-lockout@hospital.local", "password": "wrong"})
    assert bad.status_code == 401
    for _ in range(4):
        client.post("/auth/login", json={"identifier": "nobody-lockout@hospital.local", "password": "wrong"})
    locked = client.post("/auth/login", json={"identifier": "nobody-lockout@hospital.local", "password": "wrong"})
    assert locked.status_code == 423


def test_auth_inactive_user_rejected(client):
    ns = login(client, "nursing.super@hospital.local")
    sid = stamp()
    created = client.post(
        "/users",
        headers=ns,
        json={
            "email": f"inactive.{sid}@example.com",
            "employee_id": f"IN{sid[-6:]}",
            "full_name": "Inactive Officer",
            "password": PASSWORD,
            "role": "nursing_officer",
            "ward_ids": [],
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["id"]
    assert client.patch(f"/users/{uid}", headers=ns, json={"is_active": False}).status_code == 200
    denied = client.post("/auth/login", json={"identifier": f"inactive.{sid}@example.com", "password": PASSWORD})
    assert denied.status_code == 401


def test_role_ward_scope_medical_icu_hod_super(client):
    med = login(client, "nurse.med@hospital.local")
    icu = login(client, "nurse.icu@hospital.local")
    hod = login(client, "hod.surgical@hospital.local")
    superu = login(client, "nursing.super@hospital.local")
    med_wards = {w["name"] for w in client.get("/wards", headers=med).json()}
    icu_wards = {w["name"] for w in client.get("/wards", headers=icu).json()}
    hod_wards = {w["name"] for w in client.get("/wards", headers=hod).json()}
    all_wards = {w["name"] for w in client.get("/wards", headers=superu).json()}
    assert med_wards == {"Medical Ward A"}
    assert icu_wards == {"ICU"}
    assert "Surgical Ward 1" in hod_wards and "Surgical Ward 2" in hod_wards
    assert "ICU" not in hod_wards
    assert {"Surgical Ward 1", "Surgical Ward 2", "Medical Ward A", "ICU"} <= all_wards


def test_duplicate_mrn_rejected(client):
    sv = login(client, "supervisor.s1@hospital.local")
    mrn = f"UHID-DUP-{stamp()}"
    first = client.post("/patients", headers=sv, json={"name": "First Dup", "age": 30, "sex": "male", "mrn": mrn})
    assert first.status_code == 200, first.text
    second = client.post("/patients", headers=sv, json={"name": "Second Dup", "age": 31, "sex": "female", "mrn": mrn})
    assert second.status_code == 400


def test_transfer_discharge_and_foreign_ward_admit(client):
    sv = login(client, "supervisor.s1@hospital.local")
    imran = login(client, "nurse.med@hospital.local")
    s1 = next(w for w in client.get("/wards", headers=sv).json() if w["name"] == "Surgical Ward 1")
    s2 = next(w for w in client.get("/wards", headers=sv).json() if w["name"] == "Surgical Ward 2")
    adm = admit(client, sv, s1["id"], "S1-XFER", "Transfer Patient")
    moved = client.post(
        f"/admissions/{adm['id']}/transfer",
        headers=sv,
        json={"ward_id": s2["id"], "bed_number": "S2-XFER"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["ward_id"] == s2["id"]
    assert moved.json()["status"] == "active"
    old = client.get("/admissions?status=transferred", headers=sv).json()
    assert any(a["id"] == adm["id"] for a in old)
    board_s1 = client.get(f"/wards/{s1['id']}/board", headers=sv).json()
    assert all(p["admission_id"] != adm["id"] for p in board_s1["patients"])

    leave = admit(client, sv, s2["id"], "S2-DC", "Discharge Patient")
    dc = client.post(f"/admissions/{leave['id']}/discharge", headers=sv)
    assert dc.status_code == 200, dc.text
    board_s2 = client.get(f"/wards/{s2['id']}/board", headers=sv).json()
    assert all(p["admission_id"] != leave["id"] for p in board_s2["patients"])

    blocked = client.post(
        "/admissions",
        headers=imran,
        json={
            "patient_id": client.post(
                "/patients",
                headers=imran,
                json={"name": "Wrong Ward", "age": 40, "sex": "male", "mrn": f"UHID-WW-{stamp()}"},
            ).json()["id"],
            "ward_id": s1["id"],
            "bed_number": "S1-NO",
            "diagnosis": "Should fail",
            "reason_for_admission": "Medical officer on surgical ward",
        },
    )
    assert blocked.status_code == 403


def test_sbar_critical_without_concern_and_review_loop(client):
    sv, _ns, anjali, _rohan, s2, _au, _ru = setup_s2(client, "2026-11-03")
    adm = admit(client, sv, s2["id"], "S2-REV", "Review Patient")
    hid = start_and_fill(
        client,
        anjali,
        adm,
        "morning",
        "2026-11-03",
        extra={"critical_flag": True, "immediate_concern": "", "risk_level": "critical"},
    )
    blocked = client.post(f"/handovers/{hid}/submit", headers=anjali)
    assert blocked.status_code == 400
    assert "immediate_concern" in str(blocked.json())

    assert client.patch(
        f"/handovers/{hid}",
        headers=anjali,
        json={"immediate_concern": "Hypotension on standing", "critical_flag": True},
    ).status_code == 200
    submitted = client.post(f"/handovers/{hid}/submit", headers=anjali)
    assert submitted.status_code == 200, submitted.text
    locked = client.patch(f"/handovers/{hid}", headers=anjali, json={"current_situation": "Trying to edit submitted"})
    assert locked.status_code == 403

    returned = client.post(f"/handovers/{hid}/review", headers=sv, json={"action": "return", "comment": "Add latest BP"})
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "returned"
    edited = client.patch(f"/handovers/{hid}", headers=anjali, json={"current_situation": "BP rechecked, still low."})
    assert edited.status_code == 200, edited.text
    resub = client.post(f"/handovers/{hid}/submit", headers=anjali)
    assert resub.status_code == 200, resub.text
    accepted = client.post(f"/handovers/{hid}/review", headers=sv, json={"action": "accept", "comment": "Reviewed"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"


def test_receive_blockers_double_wrong_nurse_other_ward_and_supervisor_proxy(client):
    sv, ns, anjali, rohan, s2, anjali_u, rohan_u = setup_s2(client, DAY)
    imran = login(client, "nurse.med@hospital.local")
    adm = admit(client, sv, s2["id"], "S2-RCV", "Receive Patient")
    hid = start_and_fill(client, anjali, adm, "morning", DAY)

    draft_board = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={DAY}", headers=rohan).json()
    assert draft_board["blockers"]["can_signoff"] is False
    early = client.post(
        "/signoff",
        headers=rohan,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": DAY,
            "outgoing_nurse_id": anjali_u["id"],
        },
    )
    assert early.status_code == 400

    assert client.post(f"/handovers/{hid}/submit", headers=anjali).status_code == 200
    board = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={DAY}", headers=rohan).json()
    assert board["blockers"]["can_signoff"] is True
    assert board["can_receive"] is True

    wrong = client.post(
        "/signoff",
        headers=rohan,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": DAY,
            "outgoing_nurse_id": rohan_u["id"],
        },
    )
    assert wrong.status_code == 400

    other_ward = client.post(
        "/signoff",
        headers=imran,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": DAY,
            "outgoing_nurse_id": anjali_u["id"],
        },
    )
    assert other_ward.status_code == 403

    rec = client.post(
        "/signoff",
        headers=rohan,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": DAY,
            "outgoing_nurse_id": anjali_u["id"],
            "notes": "Received from Anjali",
        },
    )
    assert rec.status_code == 200, rec.text
    done = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={DAY}", headers=rohan).json()
    assert done["signoff"]
    assert "Anjali" in (done["signoff"]["outgoing_nurse_name"] or "")
    assert "Rohan" in (done["signoff"]["signed_by_name"] or "")
    again = client.post(
        "/signoff",
        headers=rohan,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": DAY,
            "outgoing_nurse_id": anjali_u["id"],
        },
    )
    assert again.status_code == 400
    assert client.post(f"/admissions/{adm['id']}/discharge", headers=sv).status_code == 200

    proxy_day = "2026-11-04"
    for shift, nid in (("morning", anjali_u["id"]), ("afternoon", rohan_u["id"])):
        r = client.post(
            "/shift-assignments",
            headers=ns,
            json={"ward_id": s2["id"], "shift_type": shift, "shift_date": proxy_day, "nurse_id": nid},
        )
        assert r.status_code == 200, r.text
    adm2 = admit(client, sv, s2["id"], "S2-SV", "Supervisor Proxy")
    hid2 = start_and_fill(client, anjali, adm2, "morning", proxy_day)
    assert client.post(f"/handovers/{hid2}/submit", headers=anjali).status_code == 200
    proxy = client.post(
        "/signoff",
        headers=sv,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": proxy_day,
            "outgoing_nurse_id": anjali_u["id"],
            "notes": "Supervisor received on behalf of incoming staff",
        },
    )
    assert proxy.status_code == 200, proxy.text
    banner = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={proxy_day}", headers=sv).json()
    assert "Kavita" in (banner["signoff"]["signed_by_name"] or "")


def test_critical_unreviewed_blocks_receive_then_supervisor_accepts(client):
    day = "2026-11-05"
    sv, _ns, anjali, rohan, s2, anjali_u, _ru = setup_s2(client, day)
    adm = admit(client, sv, s2["id"], "S2-CRIT", "Critical Blocker")
    hid = start_and_fill(
        client,
        anjali,
        adm,
        "morning",
        day,
        extra={
            "critical_flag": True,
            "risk_level": "critical",
            "immediate_concern": "SpO2 88% on 4 L, work of breathing increased",
            "vitals": {"temp": 37.1, "bp_systolic": 88, "bp_diastolic": 54, "pr": 118, "rr": 28, "spo2": 88},
        },
    )
    sub = client.post(f"/handovers/{hid}/submit", headers=anjali)
    assert sub.status_code == 200, sub.text
    esc = client.get("/escalations?status=open", headers=sv).json()
    assert any(e["handover_id"] == hid for e in esc)
    board = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={day}", headers=rohan).json()
    assert board["blockers"]["can_signoff"] is False
    assert board["blockers"]["critical_unreviewed"]
    blocked = client.post(
        "/signoff",
        headers=rohan,
        json={"ward_id": s2["id"], "shift_type": "morning", "shift_date": day, "outgoing_nurse_id": anjali_u["id"]},
    )
    assert blocked.status_code == 400
    officer_resolve = client.patch(
        f"/escalations/{next(e['id'] for e in esc if e['handover_id'] == hid)}",
        headers=anjali,
        json={"status": "resolved"},
    )
    assert officer_resolve.status_code == 403
    assert client.post(f"/handovers/{hid}/review", headers=sv, json={"action": "accept", "comment": "ICU informed"}).status_code == 200
    ready = client.get(f"/wards/{s2['id']}/board?shift_type=morning&shift_date={day}", headers=rohan).json()
    assert ready["blockers"]["can_signoff"] is True
    rec = client.post(
        "/signoff",
        headers=rohan,
        json={"ward_id": s2["id"], "shift_type": "morning", "shift_date": day, "outgoing_nurse_id": anjali_u["id"]},
    )
    assert rec.status_code == 200, rec.text


def test_admin_create_officer_and_ward_then_sbar(client):
    ns = login(client, "nursing.super@hospital.local")
    sid = stamp()[-6:]
    ward = client.post("/wards", headers=ns, json={"name": f"Day Ward {sid}", "department": "Surgical"})
    assert ward.status_code == 200, ward.text
    wid = ward.json()["id"]
    user = client.post(
        "/users",
        headers=ns,
        json={
            "email": f"new.officer.{sid}@example.com",
            "employee_id": f"NW{sid}",
            "full_name": "Staff Nurse New Officer",
            "password": PASSWORD,
            "role": "nursing_officer",
            "ward_ids": [wid],
        },
    )
    assert user.status_code == 200, user.text
    headers = login(client, f"new.officer.{sid}@example.com")
    me = client.get("/auth/me", headers=headers).json()
    assert wid in me["ward_ids"]
    sv = login(client, "nursing.super@hospital.local")
    day = str(date.today() + timedelta(days=14))
    roster = client.post(
        "/shift-assignments",
        headers=sv,
        json={"ward_id": wid, "shift_type": "morning", "shift_date": day, "nurse_id": me["id"]},
    )
    assert roster.status_code == 200, roster.text
    adm = admit(client, headers, wid, "DW-01", "New Ward Patient")
    hid = start_and_fill(client, headers, adm, "morning", day)
    sub = client.post(f"/handovers/{hid}/submit", headers=headers)
    assert sub.status_code == 200, sub.text


def test_reports_and_audit_after_signoff(client):
    day = "2026-11-06"
    sv, _ns, anjali, rohan, s2, anjali_u, _ru = setup_s2(client, day)
    adm = admit(client, sv, s2["id"], "S2-AUD", "Audit Patient")
    hid = start_and_fill(client, anjali, adm, "morning", day)
    assert client.post(f"/handovers/{hid}/submit", headers=anjali).status_code == 200
    rec = client.post(
        "/signoff",
        headers=rohan,
        json={
            "ward_id": s2["id"],
            "shift_type": "morning",
            "shift_date": day,
            "outgoing_nurse_id": anjali_u["id"],
            "notes": "Audit trail receive",
        },
    )
    assert rec.status_code == 200, rec.text
    reports = client.get("/reports/compliance", headers=sv)
    assert reports.status_code == 200, reports.text
    names = {w["name"] for w in reports.json()["wards"]}
    assert "Surgical Ward 1" in names and "Surgical Ward 2" in names
    logs = client.get("/audit", headers=sv).json()
    actions = {row["action"] for row in logs}
    assert {"login", "submit", "signoff", "assign_shift"} <= actions
    protocols = client.get("/protocols", headers=anjali)
    assert protocols.status_code == 200
    assert protocols.json()
