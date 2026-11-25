"""Profil mahasiswa dan dosen: pembacaan dan normalisasi isian (batas sama dengan CHECK di database).

npm dan asal_institusi hanya data identitas; jangan dipakai untuk menentukan akses apa pun.
"""
from __future__ import annotations

import asyncpg

from schemas.profile import LecturerProfile, StudentProfile

NPM_MAX_LENGTH = 30
NIP_MAX_LENGTH = 30
ASAL_INSTITUSI_MAX_LENGTH = 100


class ProfileError(ValueError):
    """Isian profil tidak sah. `field` menunjuk isian yang bermasalah agar pesannya bisa ditaruh di dekatnya."""

    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field


def _normalize(value: str | None, max_length: int, label: str, field: str, separator: str) -> str | None:
    # separator "" membuang SEMUA spasi (NPM/NIP); " " memangkas ujung dan meratakan spasi ganda (nama institusi).
    value = separator.join((value or "").split())
    if len(value) > max_length:
        # Pesan tidak memuat isiannya, agar tidak ikut tercatat di log.
        raise ProfileError(f"{label} maksimal {max_length} karakter.", field)
    return value or None


def normalize_student_profile(npm: str | None, asal_institusi: str | None) -> StudentProfile:
    profile = StudentProfile(
        npm=_normalize(npm, NPM_MAX_LENGTH, "NPM", "npm", ""),
        asal_institusi=_normalize(asal_institusi, ASAL_INSTITUSI_MAX_LENGTH, "Asal institusi", "asal_institusi", " "),
    )
    if profile.npm is None and profile.asal_institusi is None:
        raise ProfileError("Asal institusi wajib diisi bila NPM kosong.", "asal_institusi")
    return profile


def normalize_lecturer_profile(nip: str | None) -> LecturerProfile:
    nip = _normalize(nip, NIP_MAX_LENGTH, "NIP", "nip", "")
    if nip is None:
        raise ProfileError("NIP wajib diisi untuk dosen.", "nip")
    return LecturerProfile(nip=nip)


def normalize_profile(
    role: str, npm: str | None, asal_institusi: str | None, nip: str | None
) -> StudentProfile | LecturerProfile | None:
    """Profil untuk akun baru menurut role (None untuk admin). Isian milik role lain ditolak, tidak diabaikan."""
    allowed = {"student": ("npm", "asal_institusi"), "lecturer": ("nip",)}.get(role, ())
    for field, value in (("npm", npm), ("asal_institusi", asal_institusi), ("nip", nip)):
        if value is not None and field not in allowed:
            label = {"student": "mahasiswa", "lecturer": "dosen", "admin": "admin"}.get(role, role)
            raise ProfileError(f"Isian {field} tidak berlaku untuk akun {label}.", field)
    if role == "student":
        return normalize_student_profile(npm, asal_institusi)
    if role == "lecturer":
        return normalize_lecturer_profile(nip)
    return None


async def insert_profile(conn: asyncpg.Connection, user_id: int, profile: StudentProfile | LecturerProfile) -> None:
    """Panggil di dalam transaksi yang sama dengan pembuatan pengguna."""
    if isinstance(profile, StudentProfile):
        await conn.execute(
            "INSERT INTO students (user_id, npm, asal_institusi) VALUES ($1, $2, $3)",
            user_id,
            profile.npm,
            profile.asal_institusi,
        )
    else:
        await conn.execute("INSERT INTO lecturers (user_id, nip) VALUES ($1, $2)", user_id, profile.nip)


async def get_profile(conn: asyncpg.Connection, user_id: int, role: str) -> StudentProfile | LecturerProfile | None:
    """Profil menurut role. None untuk admin, atau bila baris profil belum dibuat."""
    if role == "student":
        row = await conn.fetchrow("SELECT npm, asal_institusi FROM students WHERE user_id = $1", user_id)
        return StudentProfile(**dict(row)) if row else None
    if role == "lecturer":
        row = await conn.fetchrow("SELECT nip FROM lecturers WHERE user_id = $1", user_id)
        return LecturerProfile(**dict(row)) if row else None
    return None
