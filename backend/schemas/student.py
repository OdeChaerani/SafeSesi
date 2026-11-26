"""Respons alur mahasiswa: kelas, riwayat sesi, dan transkrip. Hanya data yang aman untuk mahasiswa."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from schemas.scenario import CatalogScenarioItem, PublicScenarioInfo

# none = belum pernah diminta; failed = pernah dijalankan tapi gagal (perlu dijalankan ulang)
EvaluationState = Literal["none", "running", "completed", "failed"]


class ClassSummary(BaseModel):
    id: int
    name: str
    academic_year: str
    lecturers: list[str]
    scenario_count: int = 0


class ClassScenariosResponse(BaseModel):
    class_info: ClassSummary
    items: list[CatalogScenarioItem]


class SessionHistoryItem(BaseModel):
    id: int
    scenario_id: int
    scenario_title: str
    client_name: str
    kind: Literal["independent", "class"]
    class_id: int | None = None
    class_name: str | None = None
    parent_session_id: int | None = None
    status: Literal["in_progress", "completed"]
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    evaluation_status: EvaluationState


class SessionHistoryResponse(BaseModel):
    items: list[SessionHistoryItem]
    total: int  # sesuai filter, sebelum dibatasi limit
    total_sessions: int  # semua sesi milik mahasiswa
    completed_sessions: int
    awaiting_evaluation: int  # selesai, belum pernah dievaluasi
    evaluation_failed: int  # evaluasi gagal, perlu dijalankan ulang
    total_duration_seconds: int  # jumlah durasi sesi selesai milik mahasiswa


class TranscriptTurn(BaseModel):
    turn_no: int
    speaker: Literal["counselor", "client"]
    content: str


class TranscriptSession(BaseModel):
    id: int
    status: str
    kind: Literal["independent", "class"]
    class_id: int | None = None
    class_name: str | None = None
    parent_session_id: int | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    scenario: PublicScenarioInfo


class TranscriptResponse(BaseModel):
    session: TranscriptSession
    turns: list[TranscriptTurn]
