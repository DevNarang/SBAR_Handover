from datetime import date, datetime

from app.deps import current_shift
from app.models import RiskLevel
from app.risk import suggest_risk
from app.routers.handovers import REQUIRED_ON_SUBMIT
from app.seed import CENSUS, SYSTEMS

SBAR_RESPONSE_KEYS = {
    "diagnosis",
    "reason_for_admission",
    "current_situation",
    "immediate_concern",
    "critical_flag",
    "medical_history",
    "surgical_history",
    "medications",
    "allergies",
    "nkda",
    "vitals",
    "system_exams",
    "significant_findings",
    "diagnostics",
    "immediate_treatment",
    "nursing_care",
    "team_communication",
    "expected_discharge_date",
    "follow_up",
    "home_care_needs",
    "risk_level",
    "status",
    "patient",
    "admission",
    "suggested_risk",
}

PATIENT_KEYS = {"id", "name", "age", "sex", "mrn"}
ADMISSION_KEYS = {"id", "ward_id", "bed_number", "diagnosis", "reason_for_admission", "ward_name"}
VITAL_KEYS = {"temp", "bp_systolic", "bp_diastolic", "pr", "rr", "spo2"}
BOARD_KEYS = {
    "admission_id",
    "patient_id",
    "name",
    "age",
    "sex",
    "bed_number",
    "diagnosis",
    "handover_id",
    "status",
    "risk_level",
    "critical_flag",
}

def login(client, email: str = "med.super@hospital.local") -> dict:
    r = client.post("/auth/login", json={"identifier": email, "password": "ChangeMe123!"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def surgical1_and_roster(client, officer_email="nurse.s1@hospital.local", shift_type=None, shift_date=None):
    headers = login(client, officer_email)
    ns = login(client, "nursing.super@hospital.local")
    wards = client.get("/wards", headers=headers).json()
    s1 = next(w for w in wards if w["name"] == "Surgical Ward 1")
    me = client.get("/auth/me", headers=headers).json()
    st, sd = current_shift()
    shift_type = shift_type or st.value
    shift_date = shift_date or str(sd)
    r = client.post(
        "/shift-assignments",
        headers=ns,
        json={"ward_id": s1["id"], "shift_type": shift_type, "shift_date": shift_date, "nurse_id": me["id"]},
    )
    assert r.status_code == 200, r.text
    return headers, s1


def test_risk_thresholds_match_prd():
    assert suggest_risk({"temp": 36.8, "bp_systolic": 120, "spo2": 98, "pr": 72, "rr": 16}) is RiskLevel.stable
    assert suggest_risk({"temp": 37.8, "bp_systolic": 120, "spo2": 98, "pr": 72, "rr": 16}) is RiskLevel.watch
    assert suggest_risk({"temp": 36.8, "bp_systolic": 120, "spo2": 89, "pr": 72, "rr": 16}) is RiskLevel.critical
    assert suggest_risk({"temp": 36.8, "bp_systolic": 70, "spo2": 98, "pr": 72, "rr": 16}) is RiskLevel.critical
    assert suggest_risk({"temp": 36.8, "bp_systolic": 120, "spo2": 98, "pr": 72, "rr": 16}, critical_flag=True) is RiskLevel.critical


def test_census_has_full_sbar_parameters():
    assert len(CENSUS) >= 15
    for row in CENSUS:
        assert row["mrn"].startswith("UHID-")
        assert row["name"] and row["bed"] and row["diagnosis"] and row["reason"]
        sbar = row["sbar"]
        for key in (
            "current_situation",
            "immediate_concern",
            "medical_history",
            "medications",
            "system_exams",
            "immediate_treatment",
            "nursing_care",
        ):
            assert key in sbar, f"{row['mrn']} missing {key}"
        for sys in SYSTEMS:
            assert sys in sbar["system_exams"]
        if sbar.get("critical_flag"):
            assert sbar["immediate_concern"]
        t = row["vitals"]
        assert len(t) == 6


def test_superintendent_sees_all_seeded_patients(client):
    headers = login(client)
    r = client.get("/admissions", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 15
    mrns = {a["patient"]["mrn"] for a in rows}
    for row in CENSUS:
        assert row["mrn"] in mrns, f"missing {row['mrn']}"
    sample = rows[0]
    assert PATIENT_KEYS <= set(sample["patient"])
    assert {"id", "ward_id", "bed_number", "diagnosis", "reason_for_admission", "status"} <= set(sample)


def test_ward_board_passes_list_parameters(client):
    headers = login(client)
    wards = client.get("/wards", headers=headers).json()
    surgical = next(w for w in wards if w["name"] == "Surgical Ward 1")
    board = client.get(f"/wards/{surgical['id']}/board", headers=headers)
    assert board.status_code == 200, board.text
    data = board.json()
    assert {"ward_id", "shift_type", "shift_date", "patients", "signoff", "blockers"} <= set(data)
    assert data["patients"]
    for p in data["patients"]:
        assert BOARD_KEYS <= set(p)
        assert p["name"]
        assert p["bed_number"]
        assert p["risk_level"] in {"stable", "watch", "critical"}


def test_handover_get_returns_every_sbar_field(client):
    headers = login(client)
    r = client.get("/admissions", headers=headers)
    ramesh = next(a for a in r.json() if a["patient"]["mrn"] == "UHID-10021")
    board = client.get(f"/wards/{ramesh['ward_id']}/board", headers=headers).json()
    card = next(p for p in board["patients"] if p["name"] == "Ramesh Patel")
    hid = card["handover_id"]
    assert hid
    h = client.get(f"/handovers/{hid}", headers=headers)
    assert h.status_code == 200, h.text
    body = h.json()
    missing = SBAR_RESPONSE_KEYS - set(body)
    assert not missing, missing
    assert PATIENT_KEYS <= set(body["patient"])
    assert ADMISSION_KEYS <= set(body["admission"])
    assert VITAL_KEYS <= set(body["vitals"])
    for sys in SYSTEMS:
        assert sys in body["system_exams"]
        assert body["system_exams"][sys]["status"] in {"normal", "abnormal"}
    assert body["medications"]
    assert body["medical_history"]
    assert body["nkda"] is True
    assert "drain" in body["current_situation"].lower()


def test_handover_patch_round_trips_sbar_parameters(client):
    headers, s1 = surgical1_and_roster(client)
    created = client.post(
        "/patients",
        headers=headers,
        json={"name": "Roundtrip Patient", "age": 41, "sex": "female", "mrn": f"UHID-RT-{int(datetime.utcnow().timestamp())}"},
    )
    assert created.status_code == 200, created.text
    adm = client.post(
        "/admissions",
        headers=headers,
        json={
            "patient_id": created.json()["id"],
            "ward_id": s1["id"],
            "bed_number": "S1-RT",
            "bed_number": "S1-RT",
            "diagnosis": "Exploratory laparotomy — SBO (tested)",
            "reason_for_admission": "Failed conservative management — test",
        },
    )
    assert adm.status_code == 200, adm.text
    ensured = client.post(f"/handovers/ensure?admission_id={adm.json()['id']}", headers=headers)
    assert ensured.status_code == 200, ensured.text
    hid = ensured.json()["id"]
    marker = f"ROUNDTRIP-{date.today().isoformat()}"
    payload = {
        "diagnosis": "Exploratory laparotomy — SBO (tested)",
        "reason_for_admission": "Failed conservative management — test",
        "current_situation": marker,
        "immediate_concern": "High NGT output",
        "critical_flag": False,
        "medical_history": [{"item": "Hypothyroidism", "notes": "tested"}],
        "surgical_history": [{"item": "Laparotomy", "notes": "D2"}],
        "medications": [{"name": "Morphine PCA", "dose": "1mg", "route": "IV", "frequency": "5 min", "notes": ""}],
        "allergies": [{"allergen": "Penicillin", "reaction": "Rash", "severity": "moderate"}],
        "nkda": False,
        "vitals": {"temp": 37.8, "bp_systolic": 118, "bp_diastolic": 72, "pr": 98, "rr": 22, "spo2": 95},
        "system_exams": {s: {"status": "normal", "notes": "ok"} for s in SYSTEMS},
        "significant_findings": "Abdomen distended",
        "diagnostics": [{"test": "K+", "result": "3.2", "date": str(date.today()), "abnormal": True}],
        "immediate_treatment": "NGT + K replacement",
        "nursing_care": "Hourly I/O",
        "team_communication": "Registrar this evening",
        "follow_up": "Repeat K+",
        "home_care_needs": "N/A",
        "expected_discharge_date": str(date.today()),
    }
    patched = client.patch(f"/handovers/{hid}", headers=headers, json=payload)
    assert patched.status_code == 200, patched.text
    got = client.get(f"/handovers/{hid}", headers=headers).json()
    assert got["current_situation"] == marker
    assert got["diagnosis"] == payload["diagnosis"]
    assert got["reason_for_admission"] == payload["reason_for_admission"]
    assert got["immediate_concern"] == payload["immediate_concern"]
    assert got["nursing_care"] == payload["nursing_care"]
    assert got["immediate_treatment"] == payload["immediate_treatment"]
    assert got["team_communication"] == payload["team_communication"]
    assert got["follow_up"] == payload["follow_up"]
    assert got["home_care_needs"] == payload["home_care_needs"]
    assert got["nkda"] is False
    assert got["allergies"][0]["allergen"] == "Penicillin"
    assert got["medications"][0]["name"] == "Morphine PCA"
    assert got["medical_history"][0]["item"] == "Hypothyroidism"
    assert got["diagnostics"][0]["test"] == "K+"
    assert got["vitals"]["temp"] == 37.8
    assert got["vitals"]["spo2"] == 95
    assert got["system_exams"]["respiratory"]["status"] == "normal"
    assert got["expected_discharge_date"] == str(date.today())
    assert got["suggested_risk"] == "watch"  # temp 37.8 and rr 22


def test_submit_rejects_incomplete_and_accepts_complete(client):
    headers, s1 = surgical1_and_roster(client)
    created = client.post(
        "/patients",
        headers=headers,
        json={"name": "Test Submit Patient", "age": 40, "sex": "female", "mrn": f"UHID-TEST-{int(datetime.utcnow().timestamp())}"},
    )
    assert created.status_code == 200, created.text
    pid = created.json()["id"]
    adm = client.post(
        "/admissions",
        headers=headers,
        json={
            "patient_id": pid,
            "ward_id": s1["id"],
            "bed_number": "S1-TEST",
            "diagnosis": "Observation",
            "reason_for_admission": "API parameter test",
        },
    )
    assert adm.status_code == 200, adm.text
    hid = client.post(f"/handovers/ensure?admission_id={adm.json()['id']}", headers=headers).json()["id"]
    draft = client.get(f"/handovers/{hid}", headers=headers).json()
    assert draft["diagnosis"] == "Observation"
    assert draft["reason_for_admission"] == "API parameter test"
    empty = client.post(f"/handovers/{hid}/submit", headers=headers)
    assert empty.status_code == 400, empty.text
    missing = empty.json()["detail"]["missing"]
    for field in ["current_situation", "immediate_treatment", "nursing_care", "vitals", "medications", "medical_history"]:
        assert any(field in str(m) for m in missing), f"{field} should be required, got {missing}"

    complete = {
        "diagnosis": "Observation",
        "reason_for_admission": "API parameter test",
        "current_situation": "Stable, awaiting labs",
        "immediate_treatment": "Observe",
        "nursing_care": "Q4H vitals",
        "medical_history": [{"item": "None", "notes": ""}],
        "medications": [{"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""}],
        "nkda": True,
        "allergies": [],
        "vitals": {"temp": 36.8, "bp_systolic": 120, "bp_diastolic": 80, "pr": 70, "rr": 16, "spo2": 98},
        "system_exams": {s: {"status": "normal", "notes": ""} for s in SYSTEMS},
    }
    assert client.patch(f"/handovers/{hid}", headers=headers, json=complete).status_code == 200
    submitted = client.post(f"/handovers/{hid}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    for key in REQUIRED_ON_SUBMIT:
        assert submitted.json()[key]


def test_officer_is_scoped_to_assigned_ward(client):
    headers = login(client, "nurse.s1@hospital.local")
    rows = client.get("/admissions", headers=headers).json()
    names = {a["ward"]["name"] for a in rows if a.get("ward")}
    assert names.isdisjoint({"Medical Ward A", "ICU"})
    icu = [a for a in rows if a["patient"]["mrn"] == "UHID-10027"]
    assert icu == []


def test_critical_patients_carry_flag_and_concern(client):
    headers = login(client)
    rows = client.get("/admissions", headers=headers).json()
    lakshmi = next(a for a in rows if a["patient"]["mrn"] == "UHID-10026")
    board = client.get(f"/wards/{lakshmi['ward_id']}/board", headers=headers).json()
    card = next(p for p in board["patients"] if p["name"] == "Lakshmi Rao")
    h = client.get(f"/handovers/{card['handover_id']}", headers=headers).json()
    assert h["risk_level"] == "critical"
    assert h["critical_flag"] is True
    assert h["immediate_concern"]
    assert h["vitals"]["pr"] >= 110
