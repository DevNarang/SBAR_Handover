from app.deps import previous_shift, current_shift
from app.models import ShiftType
from datetime import date, timedelta


def auth(client, email: str) -> dict:
    r = client.post("/auth/login", json={"identifier": email, "password": "ChangeMe123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_three_shifts_and_previous_chain(client):
    meta = client.get("/meta/shift", headers=auth(client, "med.super@hospital.local")).json()
    assert set(meta["shifts"]) == {"morning", "afternoon", "evening"}
    assert "night" not in meta["windows"]
    assert "afternoon" in meta["windows"]
    d = date(2026, 8, 15)
    assert previous_shift(ShiftType.afternoon, d) == (ShiftType.morning, d)
    assert previous_shift(ShiftType.evening, d) == (ShiftType.afternoon, d)
    assert previous_shift(ShiftType.morning, d) == (ShiftType.evening, d - timedelta(days=1))


def test_outgoing_nurse_cannot_receive_own_handover(client):
    headers = auth(client, "nurse.s1@hospital.local")
    wards = client.get("/wards", headers=headers).json()
    w = next(w for w in wards if w["name"] == "Surgical Ward 1")
    me = client.get("/auth/me", headers=headers).json()
    st, sd = current_shift()
    board = client.get(f"/wards/{w['id']}/board?shift_type={st.value}&shift_date={sd}", headers=headers).json()
    if not board["outgoing_nurses"]:
        return
    r = client.post(
        "/signoff",
        headers=headers,
        json={
            "ward_id": w["id"],
            "shift_type": board["shift_type"],
            "shift_date": board["shift_date"],
            "outgoing_nurse_id": me["id"],
            "notes": "should fail",
        },
    )
    assert r.status_code in (400, 403)


def test_incoming_nurse_receives_from_outgoing_when_complete(client):
    outgoing = auth(client, "nurse.s1@hospital.local")
    incoming = auth(client, "nurse.s1.in@hospital.local")
    wards = client.get("/wards", headers=outgoing).json()
    w = next(x for x in wards if x["name"] == "Surgical Ward 1")
    st, sd = current_shift()
    board = client.get(f"/wards/{w['id']}/board?shift_type={st.value}&shift_date={sd}", headers=outgoing).json()
    out_id = next(n["id"] for n in board["outgoing_nurses"] if "Anjali" in n["full_name"])

    for p in board["patients"]:
        if p["status"] in ("missing", "draft", "returned"):
            hid = p["handover_id"]
            if not hid:
                hid = client.post(
                    f"/handovers/ensure?admission_id={p['admission_id']}&shift_type={st.value}&shift_date={sd}",
                    headers=outgoing,
                ).json()["id"]
            client.patch(
                f"/handovers/{hid}",
                headers=outgoing,
                json={
                    "current_situation": "Ready for nurse-to-nurse handover test",
                    "immediate_concern": "None",
                    "critical_flag": False,
                    "medical_history": [{"item": "As charted", "notes": ""}],
                    "medications": [{"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""}],
                    "nkda": True,
                    "allergies": [],
                    "vitals": {"temp": 36.8, "bp_systolic": 120, "bp_diastolic": 80, "pr": 72, "rr": 16, "spo2": 98},
                    "system_exams": {
                        s: {"status": "normal", "notes": ""}
                        for s in [
                            "respiratory",
                            "cardiovascular",
                            "neurological",
                            "genitourinary",
                            "musculoskeletal",
                            "integumentary",
                        ]
                    },
                    "immediate_treatment": "Continue plan",
                    "nursing_care": "Q4H obs",
                    "diagnosis": p["diagnosis"],
                    "reason_for_admission": "Test",
                },
            )
            sub = client.post(f"/handovers/{hid}/submit", headers=outgoing)
            assert sub.status_code == 200, sub.text

    board = client.get(f"/wards/{w['id']}/board?shift_type={st.value}&shift_date={sd}", headers=incoming).json()
    if board["signoff"]:
        assert "Rohan" in (board["signoff"]["signed_by_name"] or "")
        assert "Anjali" in (board["signoff"]["outgoing_nurse_name"] or "")
        return
    if board["blockers"]["critical_unreviewed"]:
        sv = auth(client, "supervisor.s1@hospital.local")
        for p in board["blockers"]["critical_unreviewed"]:
            if p.get("handover_id"):
                client.post(
                    f"/handovers/{p['handover_id']}/review",
                    headers=sv,
                    json={"action": "accept", "comment": "Reviewed for receive test"},
                )
        board = client.get(f"/wards/{w['id']}/board?shift_type={st.value}&shift_date={sd}", headers=incoming).json()
    assert board["blockers"]["can_signoff"] is True
    rec = client.post(
        "/signoff",
        headers=incoming,
        json={
            "ward_id": w["id"],
            "shift_type": board["shift_type"],
            "shift_date": board["shift_date"],
            "outgoing_nurse_id": out_id,
            "notes": "Walked round beds S1-02 to S1-15. Questions answered.",
        },
    )
    assert rec.status_code == 200, rec.text
    done = client.get(f"/wards/{w['id']}/board?shift_type={st.value}&shift_date={sd}", headers=incoming).json()
    assert done["signoff"]
    assert "Rohan" in (done["signoff"]["signed_by_name"] or "")
    assert "Anjali" in (done["signoff"]["outgoing_nurse_name"] or "")
    again = client.post(
        "/signoff",
        headers=incoming,
        json={
            "ward_id": w["id"],
            "shift_type": board["shift_type"],
            "shift_date": board["shift_date"],
            "outgoing_nurse_id": out_id,
            "notes": "dup",
        },
    )
    assert again.status_code == 400
