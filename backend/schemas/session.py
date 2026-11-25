from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator

from schemas.client_state import ClientState
from schemas.scenario import PublicScenarioInfo

# Ekspresi wajah avatar klien (lihat services/simulation/expression.py).
Expression = Literal["neutral", "happy", "sad", "anxious", "tense"]


class CreateSessionRequest(BaseModel):
    """Permintaan pembuatan sesi simulasi konseling baru."""

    scenario_id: int = Field(..., description="ID skenario yang dipilih")
    class_id: int | None = Field(default=None, description="ID kelas jika latihan kelas (NULL untuk latihan mandiri)")
    mode: Literal["new", "repeat", "continue"] = Field(default="new", description="Mode latihan: new | repeat | continue")
    parent_session_id: int | None = Field(default=None, description="ID sesi sebelumnya jika mode continue")


class SessionResponse(BaseModel):
    """Respon data sesi konseling."""

    id: int
    student_id: int
    scenario_id: int
    class_id: int | None = None
    parent_session_id: int | None = None
    # Hanya ringkasan publik; scenario_snapshot (hidden facts, persona, kasus,
    # kondisi awal) tidak pernah dikirim ke frontend.
    scenario: PublicScenarioInfo
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None


class WordTiming(BaseModel):
    """Penanda waktu satu kata dari STT, dalam milidetik sejak awal sesi."""

    word: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)


class CreateTurnRequest(BaseModel):
    """Permintaan pengiriman giliran ucapan konselor."""

    content: str = Field(..., min_length=1, description="Teks ucapan konselor")
    start_ms: int = Field(default=0, ge=0, description="Waktu awal bicara dalam milidetik")
    end_ms: int = Field(default=0, ge=0, description="Waktu akhir bicara dalam milidetik")
    words: list[WordTiming] | None = Field(default=None, description="Penanda waktu per kata (input suara)")

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Teks ucapan konselor tidak boleh hanya berupa spasi kosong.")
        return cleaned


class TurnResponse(BaseModel):
    """Respon giliran dari klien virtual."""

    turn_no: int = Field(..., description="Nomor urut respon klien")
    content: str = Field(..., description="Teks respons klien virtual dalam Bahasa Indonesia")
    expression: Expression = Field(
        default="neutral",
        description="Ekspresi wajah avatar, label kasar dari emosi Client State (bukan state itu sendiri)",
    )
    internal_state: ClientState | None = Field(
        default=None,
        description="State internal klien (HANYA dikembalikan jika DEBUG_INCLUDE_INTERNAL=true)",
    )


class EndSessionResponse(BaseModel):
    """Respon penyelesaian sesi konseling."""

    id: int
    status: str
    duration_seconds: int | None
    ended_at: datetime
