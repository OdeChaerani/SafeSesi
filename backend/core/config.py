from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Jalur berkas .env di direktori backend
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Konfigurasi global backend SafeSesi menggunakan pydantic-settings."""

    DATABASE_URL: str = ""
    GEMINI_API_KEY: str = ""
    # Model dan thinking budget per peran (A = state, B = responder, C = notes).
    # Thinking budget: 0 = thinking dimatikan; kosong/"none" = thinking_config tidak dikirim
    # (default model). Beberapa model (mis. gemini-3.5-flash-lite) menolak budget 0.
    GEMINI_MODEL_STATE: str = "gemini-3.8-flash"
    GEMINI_MODEL_RESPONDER: str = "gemini-3.8-flash"
    GEMINI_MODEL_NOTES: str = "gemini-3.5-flash-lite"
    GEMINI_THINKING_BUDGET_STATE: int | None = 0
    GEMINI_THINKING_BUDGET_RESPONDER: int | None = 0
    GEMINI_THINKING_BUDGET_NOTES: int | None = None  # flash-lite menolak budget 0
    # Saat startup, uji setiap kombinasi model + budget dengan satu panggilan ringan;
    # startup gagal jika Gemini menolak. Matikan untuk tes / tanpa akses jaringan.
    GEMINI_VALIDATE_ON_STARTUP: bool = True

    # background: respons dikirim setelah turn & state tersimpan, Peran C berjalan setelahnya
    # (giliran berikutnya & end session menunggu Peran C lewat advisory lock per sesi).
    NOTES_UPDATE_MODE: Literal["inline", "background"] = "background"
    NOTES_TIMEOUT_S: float = 20.0  # batas waktu Peran C agar lock sesi tidak tertahan
    TURN_LOCK_TIMEOUT_S: float = 30.0  # batas tunggu lock giliran sebelumnya
    GREETING_SHORTCUT_ENABLED: bool = False
    DEBUG_INCLUDE_INTERNAL: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator(
        "GEMINI_MODEL_STATE",
        "GEMINI_MODEL_RESPONDER",
        "GEMINI_MODEL_NOTES",
        mode="before",
    )
    @classmethod
    def upgrade_deprecated_models(cls, v: Any) -> str:
        if isinstance(v, str) and "gemini-2.5" in v:
            return v.replace("gemini-2.5", "gemini-3.8")
        return v or "gemini-3.8-flash"

    @field_validator(
        "GEMINI_THINKING_BUDGET_STATE",
        "GEMINI_THINKING_BUDGET_RESPONDER",
        "GEMINI_THINKING_BUDGET_NOTES",
        mode="before",
    )
    @classmethod
    def parse_thinking_budget(cls, v: Any) -> Any:
        if v is None or (isinstance(v, str) and v.strip().lower() in ("", "none", "null", "default")):
            return None
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.strip().startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Mengembalikan singleton instance Settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

