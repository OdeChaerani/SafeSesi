"""Profil mahasiswa dan dosen: pembacaan dan normalisasi isian (batas sama dengan CHECK di database).

npm dan asal_institusi hanya data identitas; jangan dipakai untuk menentukan akses apa pun.
"""
from __future__ import annotations

import asyncpg

from schemas.profile import LecturerProfile, StudentProfile

NPM_MAX_LENGTH = 30
NIP_MAX_LENGTH = 30
ASAL_INSTITUSI_MAX_LENGTH = 100


def _normalize(value: str | None, max_length: int, label: str) -> str | None:
    value = (value or "").strip()
    if len(value) > max_length:
        # Pesan tidak memuat isiannya, agar tidak ikut tercatat di log.
        raise ValueError(f"{label} maksimal {max_length} karakter.")
    return value or None


def normalize_student_profile(npm: str | None, asal_institusi: str | None) -> StudentProfile:
    profile = StudentProfile(
        npm=_normalize(npm, NPM_MAX_LENGTH, "NPM"),
        asal_institusi=_normalize(asal_institusi, ASAL_INSTITUSI_MAX_LENGTH, "Asal institusi"),
    )
    if profile.npm is None and profile.asal_institusi is None:
        raise ValueError("Asal institusi wajib diisi bila NPM kosong.")
    return profile


def normalize_lecturer_profile(nip: str | None) -> LecturerProfile:
    nip = _normalize(nip, NIP_MAX_LENGTH, "NIP")
    if nip is None:
        raise ValueError("NIP wajib diisi untuk dosen.")
    return LecturerProfile(nip=nip)


async def get_profile(conn: asyncpg.Connection, user_id: int, role: str) -> StudentProfile | LecturerProfile | None:
    """Profil menurut role. None untuk admin, atau bila baris profil belum dibuat."""
    if role == "student":
        row = await conn.fetchrow("SELECT npm, asal_institusi FROM students WHERE user_id = $1", user_id)
        return StudentProfile(**dict(row)) if row else None
    if role == "lecturer":
        row = await conn.fetchrow("SELECT nip FROM lecturers WHERE user_id = $1", user_id)
        return LecturerProfile(**dict(row)) if row else None
    return None
