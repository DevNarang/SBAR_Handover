import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent.parent / "test_sbar.db"
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["GEMINI_API_KEY"] = ""
if TEST_DB.exists():
    TEST_DB.unlink()

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app, migrate_schema
from app.models import LoginAttempt
from app.seed import seed_test_hospital


@pytest.fixture(scope="session")
def client():
    migrate_schema()
    db = SessionLocal()
    try:
        db.query(LoginAttempt).delete()
        seed_test_hospital(db, include_census=True)
        db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c
