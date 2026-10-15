import base64
import json
import os

import httpx

from app.config import settings

CLINICAL_TRANSCRIBE_PROMPT = """Transcribe this nursing handover dictation verbatim for a hospital SBAR note.
Preserve drug names, doses, routes, vitals, abbreviations (BP, PR, SpO2, NKDA), and procedure names.
Do not add clinical advice. Do not summarize. Return only the transcript text."""

SUMMARY_PROMPT = (
    "You are a senior nurse writing a concise SBAR handover. "
    "Use professional clinical language. Return JSON with keys: "
    "current_situation, significant_findings, immediate_treatment, nursing_care. "
    "Do not invent facts not present in the data.\n\nDATA:\n"
)


def _fallback_summary(payload: dict) -> str:
    vitals = payload.get("vitals") or {}
    dx = payload.get("diagnosis") or "the recorded diagnosis"
    return (
        '{"current_situation":"Patient remains admitted with '
        + str(dx)
        + f'. Latest vitals: T {vitals.get("temp", "—")}°C, BP {vitals.get("bp_systolic", "—")}/{vitals.get("bp_diastolic", "—")}, PR {vitals.get("pr", "—")}, RR {vitals.get("rr", "—")}, SpO2 {vitals.get("spo2", "—")}%.",'
        '"significant_findings":"'
        + (payload.get("findings") or "No additional significant findings documented.")
        + '",'
        '"immediate_treatment":"Continue current orders, monitor vitals, escalate if deterioration.",'
        '"nursing_care":"Q4H vitals, pressure care, medication as charted, document intake/output."}'
    )


def _google_key() -> str:
    return (settings.gemini_api_key or settings.google_stt_api_key or "").strip()


def gemini_enabled() -> bool:
    if os.environ.get("TESTING") == "1":
        return False
    return bool(_google_key())


def _gemini_generate(parts: list[dict], temperature: float = 0.2) -> str:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    resp = httpx.post(
        url,
        params={"key": _google_key()},
        json={
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature},
        },
        timeout=60.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(data.get("error", {}).get("message") or "Empty Gemini response")
    texts = []
    for part in candidates[0].get("content", {}).get("parts", []):
        if "text" in part:
            texts.append(part["text"])
    return "\n".join(texts).strip()


def summarize_sbar(payload: dict) -> tuple[str, str]:
    if not gemini_enabled():
        return _fallback_summary(payload), "fallback"
    text = _gemini_generate([{"text": SUMMARY_PROMPT + json.dumps(payload, default=str)}])
    return text, "gemini"


def _audio_mime(content_type: str | None, filename: str | None) -> str:
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw in {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp3", "audio/mpeg", "audio/flac", "audio/aac", "audio/mp4", "audio/m4a"}:
        if raw == "audio/mpeg":
            return "audio/mp3"
        if raw in {"audio/x-wav"}:
            return "audio/wav"
        if raw == "audio/m4a":
            return "audio/mp4"
        return raw
    name = (filename or "").lower()
    if name.endswith(".wav"):
        return "audio/wav"
    if name.endswith(".mp3"):
        return "audio/mp3"
    if name.endswith(".ogg"):
        return "audio/ogg"
    return "audio/webm"


def transcribe_gemini(audio: bytes, content_type: str | None, filename: str | None) -> str:
    mime = _audio_mime(content_type, filename)
    return _gemini_generate(
        [
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}},
            {"text": CLINICAL_TRANSCRIBE_PROMPT},
        ],
        temperature=0.1,
    )


def transcribe_google_medical(audio: bytes, content_type: str | None = None, filename: str | None = None) -> str:
    """Google Cloud Speech-to-Text medical_dictation (nurse/provider dictation)."""
    key = _google_key()
    if not key:
        raise RuntimeError("No Google STT API key configured")
    mime = _audio_mime(content_type, filename)
    encoding = "LINEAR16" if mime in {"audio/wav", "audio/x-wav"} else "WEBM_OPUS"
    config: dict = {
        "languageCode": "en-US",
        "encoding": encoding,
        "model": settings.google_medical_stt_model,
        "enableAutomaticPunctuation": True,
    }
    if encoding == "LINEAR16":
        config["sampleRateHertz"] = 22050
    payload = {
        "config": config,
        "audio": {"content": base64.b64encode(audio).decode()},
    }
    resp = httpx.post(
        "https://speech.googleapis.com/v1/speech:recognize",
        params={"key": key},
        json=payload,
        timeout=60.0,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Cloud STT HTTP {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    results = data.get("results") or []
    bits = []
    for result in results:
        alts = result.get("alternatives") or []
        if alts:
            bits.append(alts[0].get("transcript", ""))
    text = " ".join(bits).strip()
    if not text:
        raise RuntimeError(data.get("error", {}).get("message") or "Empty medical STT transcript")
    return text


def transcribe_voice(audio: bytes, content_type: str | None, filename: str | None) -> tuple[str, str]:
    if not _google_key():
        return (
            "[Voice transcription unavailable — add GEMINI_API_KEY or GOOGLE_STT_API_KEY in backend/.env.]",
            "fallback",
        )
    provider = settings.stt_provider.strip().lower()
    errors = []
    if provider in {"google_medical", "medical_dictation", "cloud_speech_medical"}:
        try:
            return transcribe_google_medical(audio, content_type, filename), "google_medical_dictation"
        except Exception as exc:
            errors.append(str(exc))
            try:
                return transcribe_gemini(audio, content_type, filename), "gemini_fallback"
            except Exception as exc2:
                return f"[Voice transcription failed: {exc2}]", "error"
    try:
        return transcribe_gemini(audio, content_type, filename), "gemini"
    except Exception as exc:
        errors.append(str(exc))
        try:
            return transcribe_google_medical(audio, content_type, filename), "google_medical_fallback"
        except Exception as exc2:
            return f"[Voice transcription failed: {exc}; medical STT: {exc2}]", "error"
