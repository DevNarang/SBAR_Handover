from app.seed import DEMO_PASSWORD, SUPER_ADMIN_EMAIL


def login(client, email: str, password: str = DEMO_PASSWORD):
    return client.post("/auth/login", json={"identifier": email, "password": password})


def test_pending_admin_cannot_use_portal(client):
    r = client.post(
        "/auth/signup",
        json={
            "kind": "department_admin",
            "full_name": "Admin One",
            "employee_id": "DA-100",
            "email": "admin.one@example.com",
            "mobile": "9000000001",
            "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
            "new_department": "Oncology",
            "designation": "Department Admin",
        },
    )
    assert r.status_code == 200, r.text
    pending = login(client, "admin.one@example.com")
    assert pending.status_code == 403
    assert pending.json()["detail"]["code"] == "pending"
    assert client.get("/wards").status_code in (401, 403)


def test_super_admin_approves_admin_then_admin_approves_nurse(client):
    sa = login(client, SUPER_ADMIN_EMAIL)
    if sa.status_code != 200:
        sa = login(client, "nursing.super@hospital.local")
    assert sa.status_code == 200, sa.text
    headers = {"Authorization": f"Bearer {sa.json()['access_token']}"}

    client.post("/wards", headers=headers, json={"name": "Oncology Ward 1", "department": "Oncology"})
    opts = client.get("/auth/signup-options").json()
    ward = next(w for w in opts["wards"] if w["name"] == "Oncology Ward 1")

    admin = client.post(
        "/auth/signup",
        json={
            "kind": "department_admin",
            "full_name": "Oncology Admin",
            "employee_id": "DA-200",
            "email": "onc.admin@example.com",
            "mobile": "9000000002",
            "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
            "department": "Oncology",
            "designation": "Department Admin",
        },
    )
    assert admin.status_code == 200, admin.text
    aid = admin.json()["id"]

    queue = client.get("/approvals/admins?status=pending", headers=headers)
    assert queue.status_code == 200, queue.text
    assert any(item["id"] == aid for item in queue.json()["items"])

    assert client.post(f"/approvals/{aid}/approve", headers=headers).status_code == 200
    admin_login = login(client, "onc.admin@example.com")
    assert admin_login.status_code == 200, admin_login.text
    ah = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    nurse = client.post(
        "/auth/signup",
        json={
            "kind": "nurse",
            "full_name": "Nurse Two",
            "employee_id": "NO-200",
            "email": "onc.nurse@example.com",
            "mobile": "9000000003",
            "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
            "department": "Oncology",
            "ward_id": ward["id"],
        },
    )
    assert nurse.status_code == 200, nurse.text
    nid = nurse.json()["id"]

    other = login(client, "hod.surgical@hospital.local")
    oh = {"Authorization": f"Bearer {other.json()['access_token']}"}
    forbidden = client.post(f"/approvals/{nid}/approve", headers=oh)
    assert forbidden.status_code == 403

    nurses = client.get("/approvals/nurses?status=pending", headers=ah)
    assert nurses.status_code == 200
    assert any(item["id"] == nid for item in nurses.json()["items"])
    assert client.post(f"/approvals/{nid}/approve", headers=ah).status_code == 200
    nurse_login = login(client, "onc.nurse@example.com")
    assert nurse_login.status_code == 200, nurse_login.text
    nh = {"Authorization": f"Bearer {nurse_login.json()['access_token']}"}
    me = client.get("/auth/me", headers=nh).json()
    assert ward["id"] in me["ward_ids"]


def test_reject_shows_reason_on_login(client):
    sa = login(client, SUPER_ADMIN_EMAIL)
    if sa.status_code != 200:
        sa = login(client, "nursing.super@hospital.local")
    headers = {"Authorization": f"Bearer {sa.json()['access_token']}"}
    r = client.post(
        "/auth/signup",
        json={
            "kind": "department_admin",
            "full_name": "Reject Me",
            "employee_id": "DA-300",
            "email": "reject.me@example.com",
            "mobile": "9000000004",
            "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
            "new_department": "Dental",
            "designation": "Department Admin",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    denied = client.post(f"/approvals/{uid}/reject", headers=headers, json={"reason": "Incomplete documents"})
    assert denied.status_code == 200, denied.text
    again = login(client, "reject.me@example.com")
    assert again.status_code == 403
    assert again.json()["detail"]["code"] == "rejected"
    assert "Incomplete" in again.json()["detail"]["reason"]


def test_department_admin_creates_ward_only_in_own_department(client):
    hod = login(client, "hod.surgical@hospital.local")
    assert hod.status_code == 200, hod.text
    hh = {"Authorization": f"Bearer {hod.json()['access_token']}"}
    created = client.post(
        "/wards",
        headers=hh,
        json={"name": "Surgical HOD Unit 1", "department": "Medical"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["department"] == "Surgical"
    assert created.json()["name"] == "Surgical HOD Unit 1"

    dup = client.post("/wards", headers=hh, json={"name": "Surgical HOD Unit 1", "department": "Surgical"})
    assert dup.status_code == 400

    officer = login(client, "nurse.s1@hospital.local")
    oh = {"Authorization": f"Bearer {officer.json()['access_token']}"}
    assert client.post("/wards", headers=oh, json={"name": "Officer Ward", "department": "Surgical"}).status_code == 403
    assert client.post("/users", headers=hh, json={
        "email": "sneaky@example.com",
        "employee_id": "SN1",
        "full_name": "Nope",
        "password": DEMO_PASSWORD,
        "role": "nursing_officer",
    }).status_code == 403
