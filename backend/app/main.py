from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from sqlalchemy import text

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.routers import auth, admin, clinical, handovers, ops, roster, approvals
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
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()]
        extra = {
            "mobile": "VARCHAR(32)",
            "designation": "VARCHAR(128)",
            "account_status": "VARCHAR(32) DEFAULT 'approved'",
            "rejection_reason": "TEXT",
            "requested_ward_id": "INTEGER",
        }
        for name, ddl in extra.items():
            if name not in user_cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))


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
wildcard = not origins or origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if wildcard else origins,
    allow_credentials=not wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _mount_api(prefix: str = "") -> None:
    app.include_router(auth.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    app.include_router(clinical.router, prefix=prefix)
    app.include_router(handovers.router, prefix=prefix)
    app.include_router(ops.router, prefix=prefix)
    app.include_router(roster.router, prefix=prefix)
    app.include_router(approvals.router, prefix=prefix)


def resolve_ui_dir() -> Path | None:
    """Serve the Vite build only when explicitly present (Docker/Render)."""
    env = os.environ.get("UI_DIST", "").strip()
    candidates = [Path(env)] if env else []
    candidates.append(Path("/app/ui"))
    for path in candidates:
        if path.is_dir() and (path / "index.html").is_file():
            return path
    return None


@app.get("/health")
def health():
    return {"ok": True, "hospital": settings.hospital_name}


ui_dir = resolve_ui_dir()
if ui_dir:
    # Combined deploy: browser pages stay at /, API is under /api (same as Vite proxy).
    _mount_api("/api")

    @app.get("/{full_path:path}")
    def serve_ui(full_path: str):
        candidate = ui_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(ui_dir / "index.html")
else:
    _mount_api("")
