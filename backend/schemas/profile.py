"""Profil mahasiswa/dosen. Hanya untuk pemilik akun dan daftar pengguna admin: jangan masukkan ke JWT atau log."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class StudentProfile(BaseModel):
    npm: str | None
    asal_institusi: str | None


class LecturerProfile(BaseModel):
    nip: str


class ClassSummary(BaseModel):
    id: int
    name: str
    academic_year: str
    lecturers: list[str]


class _MeBase(BaseModel):
    """Respons GET /auth/me. Kolom eksplisit: kolom lain dari database tidak ikut terkirim."""

    id: int
    name: str
    email: str
    status: Literal["active"]
    created_at: datetime
    activated_at: datetime | None


class StudentMe(_MeBase):
    role: Literal["student"]
    npm: str | None
    asal_institusi: str | None
    classes: list[ClassSummary]


class LecturerMe(_MeBase):
    role: Literal["lecturer"]
    nip: str | None
    classes: list[ClassSummary]


class AdminMe(_MeBase):
    role: Literal["admin"]
