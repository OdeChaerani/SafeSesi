from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

DisclosureLevel = Literal["guarded", "medium", "high"]
AmbivalenceLean = Literal["toward_change", "toward_status_quo", "both"]


class ClientState(BaseModel):
    """Representasi Client State SafeSesi (kolom sama persis dengan tabel client_state_log)."""

    id: int | None = Field(default=None, description="Primary key log")
    session_id: int | None = Field(default=None, description="ID sesi terkait")
    turn_id: int | None = Field(default=None, description="ID turn klien terkait (NULL untuk initial state)")
    emotion_type: str = Field(..., description="Jenis emosi yang dirasakan klien")
    emotion_cause: str | None = Field(default=None, description="Penyebab atau konteks emosi")
    disclosure_level: str = Field(..., description="Tingkat keterbukaan: guarded | medium | high")
    disclosure_trigger: str | None = Field(default=None, description="Pemicu perubahan keterbukaan")
    reasons_to_change: str | None = Field(default=None, description="Alasan klien ingin berubah")
    reasons_to_maintain: str | None = Field(default=None, description="Alasan klien mempertahankan keadaan")
    ambivalence_lean: str = Field(..., description="Kecenderungan ambivalensi: toward_change | toward_status_quo | both")
    discord_present: bool = Field(default=False, description="Apakah ketegangan hubungan tampak")
    discord_context: str | None = Field(default=None, description="Konteks pemicu ketegangan hubungan")
    discord_response: str | None = Field(default=None, description="Bentuk respons ketidaknyamanan klien")
    created_at: datetime | None = Field(default=None, description="Waktu pencatatan state")


# Field deskriptif Client State yang diisi State Detail Agent (mode split).
DETAIL_FIELDS = (
    "emotion_type",
    "emotion_cause",
    "disclosure_trigger",
    "reasons_to_change",
    "reasons_to_maintain",
    "discord_context",
    "discord_response",
)


class StateDecisionNoReason(BaseModel):
    """Keputusan State Decision Agent tanpa field alasan (varian pembanding di skrip replay)."""

    disclosure_level: DisclosureLevel = Field(..., description="Tingkat keterbukaan saat ini")
    discord_present: bool = Field(..., description="Apakah ketegangan hubungan tampak pada giliran ini")
    ambivalence_lean: AmbivalenceLean = Field(..., description="Sisi pertimbangan yang saat ini lebih menonjol")
    emotion_short: str = Field(..., description="Emosi klien saat ini, maksimal 5 kata")


class StateDecision(BaseModel):
    """Keputusan State Decision Agent. Field alasan diletakkan SEBELUM keputusan yang dijelaskannya."""

    disclosure_reason: str = Field(..., description="Alasan singkat tingkat keterbukaan, maksimal 20 kata")
    disclosure_level: DisclosureLevel = Field(..., description="Tingkat keterbukaan saat ini")
    discord_reason: str = Field(..., description="Alasan singkat ada/tidaknya ketegangan hubungan, maksimal 20 kata")
    discord_present: bool = Field(..., description="Apakah ketegangan hubungan tampak pada giliran ini")
    ambivalence_reason: str = Field(..., description="Alasan singkat kecenderungan ambivalensi, maksimal 20 kata")
    ambivalence_lean: AmbivalenceLean = Field(..., description="Sisi pertimbangan yang saat ini lebih menonjol")
    emotion_short: str = Field(..., description="Emosi klien saat ini, maksimal 5 kata")


class StateDetail(BaseModel):
    """Field deskriptif dari State Detail Agent. Sengaja tanpa disclosure_level, discord_present,
    dan ambivalence_lean: keputusan State Decision Agent tidak bisa diubah dari sini."""

    emotion_type: str = Field(..., description="Jenis emosi yang dirasakan klien")
    emotion_cause: str | None = Field(default=None, description="Penyebab atau konteks emosi")
    disclosure_trigger: str | None = Field(default=None, description="Konteks yang memicu/mempertahankan tingkat keterbukaan")
    reasons_to_change: str | None = Field(default=None, description="Alasan klien ingin berubah")
    reasons_to_maintain: str | None = Field(default=None, description="Alasan klien mempertahankan keadaan")
    discord_context: str | None = Field(default=None, description="Pemicu ketegangan (null jika tidak tampak)")
    discord_response: str | None = Field(default=None, description="Respons ketidaknyamanan klien (null jika tidak tampak)")
