from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.routers import auth, admin, clinical, handovers, ops, roster
from app.seed import seed_if_empty

Base.metadata.create_all(bind=engine)


def migrate_schema() -> None:
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(handovers)")).fetchall()]
        if "ai_summary" not in cols:
            conn.execute(text("ALTER TABLE handovers ADD COLUMN ai_summary TEXT"))
        sign_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(ward_shift_signoffs)")).fetchall()]
        if "outgoing_nurse_id" not in sign_cols:
            conn.execute(text("ALTER TABLE ward_shift_signoffs ADD COLUMN outgoing_nurse_id INTEGER"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version="1.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(clinical.router)
app.include_router(handovers.router)
app.include_router(ops.router)
app.include_router(roster.router)


@app.get("/health")
def health():
    return {"ok": True, "hospital": settings.hospital_name}
