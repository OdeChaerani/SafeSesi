from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Jalur berkas .env di direktori backend
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


# Hanya untuk development lokal; production menolak start dengan nilai ini (lihat validate_auth_settings).
DEV_JWT_SECRET = "dev-only-jwt-secret-ganti-di-production"


class Settings(BaseSettings):
    """Konfigurasi global backend SafeSesi menggunakan pydantic-settings."""

    # development | production. Skrip yang memanggil Gemini menolak jalan di production.
    APP_ENV: str = "development"
    DATABASE_URL: str = ""
    GEMINI_API_KEY: str = ""
    # Model dan thinking budget per peran (A = state, B = responder, C = notes).
    # Thinking budget: 0 = thinking dimatikan; kosong/"none" = thinking_config tidak dikirim
    # (default model). Beberapa model (mis. gemini-3.5-flash-lite) menolak budget 0.
    GEMINI_MODEL_STATE: str = "gemini-3.8-flash"
    GEMINI_MODEL_RESPONDER: str = "gemini-3.1-flash-lite"
    GEMINI_MODEL_NOTES: str = "gemini-3.1-flash-lite"
    GEMINI_THINKING_BUDGET_STATE: int | None = 0
    GEMINI_THINKING_BUDGET_RESPONDER: int | None = None  # flash-lite menolak budget 0
    GEMINI_THINKING_BUDGET_NOTES: int | None = None  # flash-lite menolak budget 0
    # Mode split: State Decision Agent (ditunggu Peran B) dan State Detail Agent (background).
    GEMINI_MODEL_STATE_DECISION: str = "gemini-3.8-flash"
    GEMINI_MODEL_STATE_DETAIL: str = "gemini-3.8-flash"
    GEMINI_THINKING_BUDGET_STATE_DECISION: int | None = 0
    GEMINI_THINKING_BUDGET_STATE_DETAIL: int | None = 0
    # Evaluasi MITI (setelah sesi selesai). Budget None = thinking bawaan model.
    GEMINI_MODEL_BEHAVIOR_CODING: str = "gemini-3.8-flash"
    GEMINI_MODEL_GLOBAL_SCORING: str = "gemini-3.8-flash"
    GEMINI_MODEL_PROCESS_OBSERVATION: str = "gemini-3.8-flash"
    GEMINI_MODEL_FEEDBACK: str = "gemini-3.8-flash"
    GEMINI_THINKING_BUDGET_BEHAVIOR_CODING: int | None = None
    GEMINI_THINKING_BUDGET_GLOBAL_SCORING: int | None = None
    GEMINI_THINKING_BUDGET_PROCESS_OBSERVATION: int | None = None
    GEMINI_THINKING_BUDGET_FEEDBACK: int | None = None
    # combined: Peran A satu panggilan sebelum Peran B. split: State Decision Agent sebelum
    # Peran B, State Detail Agent setelah respons (bersama Peran C, di lock giliran).
    # Mode dipilih eksplisit; tidak ada perpindahan mode otomatis.
    STATE_UPDATE_MODE: Literal["combined", "split"] = "combined"
    # Saat startup, uji setiap kombinasi model + budget dengan satu panggilan ringan;
    # startup gagal jika Gemini menolak. Matikan untuk tes / tanpa akses jaringan.
    GEMINI_VALIDATE_ON_STARTUP: bool = True

    # background: respons dikirim setelah turn & state tersimpan, Peran C berjalan setelahnya
    # (giliran berikutnya & end session menunggu Peran C lewat advisory lock per sesi).
    NOTES_UPDATE_MODE: Literal["inline", "background"] = "background"
    NOTES_TIMEOUT_S: float = 20.0  # batas waktu tahap background (Peran C, State Detail Agent)
    TURN_LOCK_TIMEOUT_S: float = 30.0  # batas tunggu lock giliran sebelumnya
    GREETING_SHORTCUT_ENABLED: bool = False
    DEBUG_INCLUDE_INTERNAL: bool = False

    # Suara: STT konselor (Groq) dan TTS klien (ElevenLabs). Kunci hanya di backend.
    GROQ_API_KEY: str = ""
    GROQ_STT_MODEL: str = "whisper-large-v3-turbo"
    ELEVEN_LABS_API_KEY: str = ""
    # eleven_flash_v2_5: mendukung bahasa Indonesia, latensi rendah (~100 ms).
    ELEVEN_LABS_TTS_MODEL: str = "eleven_flash_v2_5"
    SPEECH_TIMEOUT_S: float = 30.0

    # Origin frontend yang boleh memanggil API dengan cookie (allow_credentials). Harus spesifik, bukan "*".
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Autentikasi. JWT_SECRET wajib diisi nilai acak panjang di luar development (startup gagal bila tidak).
    JWT_SECRET: str = DEV_JWT_SECRET
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7  # sama dengan purge_old_refresh_tokens(days=7)
    ACTIVATION_TOKEN_HOURS: int = 72
    RESET_TOKEN_MINUTES: int = 60  # masa berlaku tautan atur ulang kata sandi dari admin
    # Alamat frontend untuk menyusun tautan aktivasi akun.
    FRONTEND_URL: str = "http://localhost:5173"

    # Pembatasan percobaan endpoint auth (angka batasnya ada di core/rate_limit.py). Matikan hanya di tes/dev.
    RATE_LIMIT_ENABLED: bool = True
    # Nyalakan HANYA bila API berada tepat di belakang satu reverse proxy tepercaya (nginx, Caddy,
    # load balancer) yang menambahkan IP klien ke X-Forwarded-For, dan port API tidak bisa diakses
    # langsung dari luar. Bila dinyalakan tanpa proxy, klien bisa memalsukan header itu untuk
    # menghindari batas. Bila dimatikan di belakang proxy, semua pengguna terlihat dari satu IP.
    TRUST_PROXY_HEADERS: bool = False

    @property
    def is_development(self) -> bool:
        return self.APP_ENV.strip().lower() == "development"

    @field_validator(
        "GEMINI_MODEL_STATE",
        "GEMINI_MODEL_RESPONDER",
        "GEMINI_MODEL_NOTES",
        "GEMINI_MODEL_STATE_DECISION",
        "GEMINI_MODEL_STATE_DETAIL",
        "GEMINI_MODEL_BEHAVIOR_CODING",
        "GEMINI_MODEL_GLOBAL_SCORING",
        "GEMINI_MODEL_PROCESS_OBSERVATION",
        "GEMINI_MODEL_FEEDBACK",
        mode="before",
    )
    @classmethod
    def upgrade_deprecated_models(cls, v: Any, info: ValidationInfo) -> Any:
        # Variabel yang tidak diset memakai default; yang diset tapi kosong ditolak, tanpa pengganti diam-diam.
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError(
                f"{info.field_name} kosong. Isi nama model Gemini, atau hapus barisnya agar memakai default di core/config.py."
            )
        # Hanya nama yang benar-benar deprecated; gemini-2.5-flash-lite masih tersedia.
        deprecated = {"gemini-2.5-flash": "gemini-3.8-flash", "gemini-2.5-pro": "gemini-3.8-flash"}
        if isinstance(v, str):
            v = deprecated.get(v.strip(), v.strip())
        return v

    @field_validator(
        "GEMINI_THINKING_BUDGET_STATE",
        "GEMINI_THINKING_BUDGET_RESPONDER",
        "GEMINI_THINKING_BUDGET_NOTES",
        "GEMINI_THINKING_BUDGET_STATE_DECISION",
        "GEMINI_THINKING_BUDGET_STATE_DETAIL",
        "GEMINI_THINKING_BUDGET_BEHAVIOR_CODING",
        "GEMINI_THINKING_BUDGET_GLOBAL_SCORING",
        "GEMINI_THINKING_BUDGET_PROCESS_OBSERVATION",
        "GEMINI_THINKING_BUDGET_FEEDBACK",
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

    @field_validator("CORS_ORIGINS")
    @classmethod
    def reject_wildcard_origin(cls, v: list[str]) -> list[str]:
        # Cookie refresh token dikirim dengan credentials; browser menolak "*" bersama credentials,
        # dan origin bebas berarti situs mana pun bisa memakai sesi pengguna.
        if any(o.strip() == "*" for o in v):
            raise ValueError("CORS_ORIGINS tidak boleh '*'; tulis origin frontend secara spesifik.")
        return v

    def validate_auth_settings(self) -> None:
        """Dipanggil saat startup: di luar development, JWT_SECRET harus diganti dan cukup panjang."""
        if self.is_development:
            return
        if self.JWT_SECRET == DEV_JWT_SECRET or len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET wajib diisi nilai acak minimal 32 karakter di luar APP_ENV=development.")

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Voice ID ElevenLabs per gender klien. Bukan rahasia, jadi tidak perlu di .env.
ELEVEN_LABS_VOICES: dict[str, str] = {
    "female": "fUesUKVrbYRcEnWoLXet",  # Citra
    "male": "SCDJ1Fy4al0KS1awS6H9",  # Janu
}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Mengembalikan singleton instance Settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

