from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SBAR Nursing Handover"
    hospital_name: str = "All India Institute of Medical Sciences (AIIMS) - Bibinagar, Hyderabad"
    secret_key: str = "change-me-in-production-sbar-handover"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    database_url: str = "sqlite:///./sbar.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    stt_provider: str = "gemini"  # gemini | google_medical
    google_stt_api_key: str = ""
    google_medical_stt_model: str = "medical_dictation"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    morning_start: int = 7
    morning_end: int = 14
    afternoon_start: int = 14
    afternoon_end: int = 21
    evening_start: int = 21
    evening_end: int = 7


settings = Settings()
