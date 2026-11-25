"""Skema structured output agen evaluator MITI.

Sesuai aturan repo, field alasan selalu diletakkan SEBELUM field keputusan/label.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

MitiCode = Literal["GI", "P", "PWP", "Q", "SR", "CR", "AF", "SEEK", "EA", "CONFRONT"]
GlobalDimension = Literal["cultivating_change_talk", "softening_sustain_talk", "partnership", "empathy"]
MiProcess = Literal["engaging", "focusing", "evoking", "planning"]
FeedbackKind = Literal["strength", "improvement", "alternative_response"]

MITI_CODES: tuple[str, ...] = ("GI", "P", "PWP", "Q", "SR", "CR", "AF", "SEEK", "EA", "CONFRONT")
GLOBAL_DIMENSIONS: tuple[str, ...] = ("cultivating_change_talk", "softening_sustain_talk", "partnership", "empathy")
MI_PROCESSES: tuple[str, ...] = ("engaging", "focusing", "evoking", "planning")


# --- Behavior Coding Agent -------------------------------------------------------------


class CodedUnit(BaseModel):
    unit_no: int = Field(..., description="Nomor unit ujaran dalam giliran ini, mulai 1")
    excerpt: str = Field(..., description="Kutipan persis unit ujaran dari transkrip (bahasa asli)")
    reason: str = Field(..., description="Alasan pengodean dalam bahasa Indonesia, merujuk aturan MITI")
    code: MitiCode | None = Field(..., description="Kode utama, atau null jika unit tidak dikode")
    alternative_code: MitiCode | None = Field(..., description="Kode kandidat kedua yang juga dipertimbangkan, atau null")
    certain: bool = Field(..., description="true jika kode utama (dan alternatif, bila ada) jelas terpenuhi; false jika ragu")
    same_affirmation_as_turn: int | None = Field(
        ..., description="Untuk AF: nomor giliran afirmasi sebelumnya yang isinya sama (diulang), atau null"
    )
    uncertainty_note: str | None = Field(..., description="Catatan ketidakpastian (mis. nada tidak tersedia), atau null")


class CodedCounselorTurn(BaseModel):
    turn_no: int = Field(..., description="Nomor giliran konselor seperti tertulis di transkrip")
    volley_reason: str = Field(..., description="Alasan apakah giliran ini melanjutkan volley sebelumnya (MITI E.3)")
    continues_previous_volley: bool = Field(
        ..., description="true jika ujaran klien sebelumnya hanya fasilitatif sehingga volley tidak terputus"
    )
    units: list[CodedUnit]


class BehaviorCodingOutput(BaseModel):
    turns: list[CodedCounselorTurn]


# --- Global Scoring Agent --------------------------------------------------------------


class GlobalRating(BaseModel):
    reason: str = Field(..., description="Alasan skor dalam bahasa Indonesia: bukti yang mendukung dan membatasi")
    evidence_turn_nos: list[int] = Field(..., description="Nomor giliran yang menjadi bukti")
    score: int = Field(..., description="Skor 1-5")


class GlobalScoringOutput(BaseModel):
    cultivating_change_talk: GlobalRating
    softening_sustain_talk: GlobalRating
    partnership: GlobalRating
    empathy: GlobalRating


# --- Process Observation Agent ---------------------------------------------------------


class ProcessObservationItem(BaseModel):
    process: MiProcess
    reason: str = Field(..., description="Alasan pengamatan dalam bahasa Indonesia berdasarkan ciri yang diamati")
    evidence_found: bool = Field(..., description="false jika belum cukup bukti untuk mengidentifikasi proses ini")
    start_turn_no: int | None
    end_turn_no: int | None
    excerpt: str | None = Field(..., description="Kutipan konselor (dan respons klien) yang mendukung, atau null")


class ProcessObservationOutput(BaseModel):
    observations: list[ProcessObservationItem]


# --- Feedback Agent ---------------------------------------------------------------------


class FeedbackItemOut(BaseModel):
    kind: FeedbackKind
    turn_no: int = Field(..., description="Giliran yang ditunjuk; untuk alternative_response wajib giliran konselor")
    evidence_turn_nos: list[int] = Field(..., description="Giliran lain yang relevan (boleh kosong)")
    excerpt: str = Field(..., description="Kutipan persis dari giliran turn_no")
    explanation: str = Field(..., description="Penjelasan dalam bahasa Indonesia yang menautkan bukti percakapan")
    alternative_text: str | None = Field(
        ...,
        description="Hanya untuk alternative_response: kalimat konkret yang bisa langsung diucapkan konselor; lainnya null",
    )


class FeedbackOutput(BaseModel):
    items: list[FeedbackItemOut]
