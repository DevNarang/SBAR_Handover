# SBAR Nursing Handover

Nurse-to-nurse shift handover for **AIIMS Bibinagar, Hyderabad**. Outgoing nursing officers complete structured **SBAR** notes (Situation, Background, Assessment, Recommendation); the incoming officer on the next shift receives the ward.

Hospital-wide shifts are morning (07:00–14:00), afternoon (14:00–21:00), and evening (21:00–07:00). Supervisors assign who is on each ward shift. The next nurse gets the previous SBAR as an editable draft and cannot change the outgoing note. Staff nurses can raise escalations; only supervisors and above can resolve them.

## Stack

- Frontend: React + Vite + TypeScript (`frontend/`)
- Backend: FastAPI + SQLAlchemy (`backend/`)
- Default database: SQLite (`backend/sbar.db`, created on first run)
- AI: Gemini (optional). Without a key, summary generation uses a local fallback. Voice uses Gemini audio transcription; optional Google Cloud Speech **medical_dictation**.

## Run locally

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY for live AI + voice
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite proxy forwards `/api` to port 8000.

### Docker

```bash
docker compose up --build
```

## Demo accounts

Password for all: `ChangeMe123!`

| Role | Email |
|------|--------|
| Medical Superintendent | `med.super@hospital.local` |
| Nursing Superintendent | `nursing.super@hospital.local` |
| HOD (Surgical) | `hod.surgical@hospital.local` |
| Nursing Supervisor | `supervisor.s1@hospital.local` |
| Nursing Officer (Surgical 1, outgoing) | `nurse.s1@hospital.local` |
| Nursing Officer (Surgical 1, incoming) | `nurse.s1.in@hospital.local` |
| Nursing Officer (Medical) | `nurse.med@hospital.local` |
| Nursing Officer (ICU) | `nurse.icu@hospital.local` |

QA test cases: see `TEST_CASES.md`.

## AI (Gemini)

Voice-to-text and SBAR drafts go through **Google Gemini**, not OpenAI.

1. Create a key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Set `GEMINI_API_KEY` in `backend/.env`.
3. Restart the API.

Default model: `gemini-2.5-flash` (`GEMINI_MODEL`). The transcription prompt is written for **clinical dictation** (drug names, vitals, SBAR language).

### Google’s medical speech models

Gemini itself does not ship a separate “Medical Gemini STT” API. Google’s dedicated medical speech models are on **Cloud Speech-to-Text**:

| Model | Use |
|-------|-----|
| `medical_dictation` | One clinician dictating notes (best for SBAR voice fields) |
| `medical_conversation` | Two-speaker clinician–patient dialogue |

To use them: enable Speech-to-Text on a GCP project, put an API key in `GOOGLE_STT_API_KEY`, set `STT_PROVIDER=google_medical`, and restart. Browser recordings are WebM/Opus; if medical STT rejects that encoding, the app falls back to Gemini.

MedGemma is a separate **text/image** medical model (not audio). It is not used for voice-to-text.

## v1 vs Phase 2 (offline)

**v1 (what you have now)** needs a working internet connection. Handovers save to the hospital server as you type. If Wi‑Fi drops, you cannot keep working in the app.

**Phase 2 offline sync** (not built yet) would let a ward tablet keep a local copy of the patient list and draft SBARs, then upload when the network returns. That was explicitly deferred so v1 could ship AI without also building conflict-merge, encrypted local storage, and a service worker.

Not in v1: offline sync, EMR integration, SSO.

## Production notes

- Change `SECRET_KEY`.
- Point `DATABASE_URL` at PostgreSQL (SQLAlchemy URL) and install `psycopg2-binary` if you leave SQLite.
- Keep `GEMINI_API_KEY` on the server only (already proxied).
- Put TLS in front of the API and static UI.
