import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app, migrate_schema
from app.models import LoginAttempt
from app.seed import seed_if_empty


@pytest.fixture(scope="session")
def client():
    migrate_schema()
    db = SessionLocal()
    try:
        db.query(LoginAttempt).delete()
        seed_if_empty(db, include_census=True)
        db.commit()
    finally:
        db.close()
    with TestClient(app) as c:
        yield c
