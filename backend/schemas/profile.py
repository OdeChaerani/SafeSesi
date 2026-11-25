"""Profil mahasiswa/dosen. Hanya untuk respons ke pemilik akun: jangan masukkan ke JWT, log, atau respons lain."""
from __future__ import annotations

from pydantic import BaseModel


class StudentProfile(BaseModel):
    npm: str | None
    asal_institusi: str | None


class LecturerProfile(BaseModel):
    nip: str
