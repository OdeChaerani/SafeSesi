from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

DisclosureLevel = Literal["guarded", "medium", "high"]

# Sama dengan DEFAULT kolom scenario_hidden_facts.min_disclosure_level.
DEFAULT_MIN_DISCLOSURE_LEVEL: DisclosureLevel = "medium"


class Persona(BaseModel):
    """Profil internal persona klien (10 isian spesifikasi SafeSesi)."""

    name: str = Field(..., description="Nama atau nama fiktif klien")
    age: int = Field(..., ge=10, le=120, description="Usia klien dalam tahun")
    gender: str = Field(..., description="Jenis kelamin klien")
    education: str | None = Field(default=None, description="Jenjang dan latar pendidikan")
    occupation: str | None = Field(default=None, description="Pekerjaan atau kegiatan utama")
    marital_status: str | None = Field(default=None, description="Status pernikahan")
    family_background: str | None = Field(default=None, description="Latar belakang keluarga")
    personality: str = Field(..., description="Karakteristik kepribadian konkret (tanpa Big Five)")
    communication_style: str = Field(..., description="Gaya komunikasi verbal klien")
    additional_background: str | None = Field(default=None, description="Latar tambahan relevan")
    avatar_file: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]+\.glb$", description="File avatar 3D di frontend/public/models/")


class HiddenFact(BaseModel):
    """Informasi tersembunyi yang diungkap bertahap (H1, H2, dst.)."""

    code: str = Field(..., description="Kode fakta tersembunyi (H1, H2, dst.)")
    short_title: str = Field(..., description="Judul singkat fakta (menjadi nama topik)")
    fact: str = Field(..., description="Uraian isi fakta tersembunyi")
    sort_order: int = Field(default=0, description="Urutan penyajian")
    min_disclosure_level: DisclosureLevel = Field(
        default=DEFAULT_MIN_DISCLOSURE_LEVEL,
        description="Tingkat keterbukaan minimal agar fakta boleh diungkap: guarded | medium | high",
    )


class Case(BaseModel):
    """Kasus klien (5 isian spesifikasi SafeSesi)."""

    main_problem: str = Field(..., description="Permasalahan utama yang dirasakan klien")
    history_impact: str | None = Field(default=None, description="Riwayat dan dampak masalah")
    expectation_change_context: str = Field(..., description="Harapan klien dan konteks perubahan perilaku")
    health_condition: str | None = Field(default=None, description="Kondisi kesehatan fisik/mental relevan")
    initial_summary: str | None = Field(
        default=None, description="Ringkasan informasi awal yang ditampilkan di halaman briefing"
    )


class InitialState(BaseModel):
    """Kondisi awal klien virtual sebelum sesi dimulai (sesuai tabel scenario_initial_states)."""

    emotion_type: str = Field(..., description="Perasaan awal klien (mis. Cemas dan kewalahan)")
    emotion_cause: str | None = Field(default=None, description="Kausa/alasan emosi awal")
    disclosure_level: str = Field(..., description="Tingkat keterbukaan awal: guarded | medium | high")
    disclosure_trigger: str | None = Field(default=None, description="Pemicu keterbukaan awal")
    reasons_to_change: str | None = Field(default=None, description="Alasan ingin berubah")
    reasons_to_maintain: str | None = Field(default=None, description="Alasan mempertahankan keadaan saat ini")
    ambivalence_lean: str = Field(..., description="Kecenderungan awal: toward_change | toward_status_quo | both")
    discord_present: bool = Field(default=False, description="Ketegangan hubungan (default false)")
    discord_context: str | None = Field(default=None, description="Konteks ketegangan")
    discord_response: str | None = Field(default=None, description="Bentuk respons ketegangan")


class ScenarioHeader(BaseModel):
    """Informasi metadata skenario konseling."""

    id: int
    title: str
    visibility: str = "class"
    review_status: str = "draft"
    change_target: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScenarioSnapshot(BaseModel):
    """Snapshot lengkap skenario yang dibekukan saat sesi dibuat (keluaran SQL build_scenario_snapshot)."""

    scenario: dict[str, Any]
    persona: Persona
    case: Case
    initial_state: InitialState
    hidden_facts: list[HiddenFact] = []


class PublicScenarioInfo(BaseModel):
    """Informasi skenario yang aman dikirim ke frontend (katalog, briefing, sesi).

    Tidak memuat hidden facts, persona lengkap, isi kasus, maupun client state.
    """

    id: int
    title: str
    change_target: str
    client_name: str
    client_age: int
    client_gender: str
    client_avatar_file: str | None = None
    client_role: str
    initial_summary: str | None = None

    @classmethod
    def from_snapshot(
        cls, snapshot: dict[str, Any], scenario_id: int | None = None
    ) -> "PublicScenarioInfo":
        scenario = snapshot.get("scenario") or {}
        persona = snapshot.get("persona") or {}
        case = snapshot.get("case") or {}
        return cls(
            id=scenario.get("id") or scenario_id,
            title=scenario.get("title", ""),
            change_target=scenario.get("change_target", ""),
            client_name=persona.get("name", ""),
            client_age=persona.get("age", 0),
            client_gender=persona.get("gender", ""),
            client_avatar_file=persona.get("avatar_file"),
            client_role=persona.get("occupation")
            or persona.get("education")
            or "Klien Virtual",
            initial_summary=case.get("initial_summary"),
        )


class CatalogScenarioItem(PublicScenarioInfo):
    """Item skenario pada katalog latihan mandiri (juga sumber data halaman briefing)."""

    attempt_status: str  # 'unattempted' | 'attempted'
    total_attempts: int
    last_completed_session_id: int | None = None
    active_session_id: int | None = None


class CatalogScenarioResponse(BaseModel):
    """Respon data katalog skenario latihan mandiri."""

    items: list[CatalogScenarioItem]
    total: int
    unattempted_count: int
    attempted_count: int
