"""Dependency bersama: koneksi DB, autentikasi, pemeriksaan role, dan aturan akses sesi.

Aturan akses sesi (BRD 5 Data & Access Needs, BRD 7.1 no. 16, BRD 7.2 "Akses data tidak sesuai"):
- Mahasiswa: hanya sesinya sendiri (mandiri maupun kelas); hanya dia yang boleh menulis ke sesi itu.
- Dosen: hanya MELIHAT sesi kelas yang dikelolanya (anggota kelas itu di class_members);
  sesi mandiri tidak pernah terlihat oleh dosen.
- Admin: mengelola akun, hak akses, dan kelas; tidak membuka sesi, transkrip, evaluasi, atau audio klien.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Awaitable, Callable

import asyncpg
from fastapi import Depends, Header, HTTPException, Request, status

from core.config import get_settings
from core.security import decode_access_token
from repositories.evaluations import lecturer_manages_session
from repositories.users import get_user_by_id

ROLES = ("student", "lecturer", "admin")
_FORBIDDEN_SESSION = "Anda tidak memiliki izin untuk mengakses sesi simulasi ini."


async def get_db(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency untuk meminjam koneksi PostgreSQL dari pool aplikasi."""
    pool: asyncpg.Pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool belum siap.",
        )
    async with pool.acquire() as connection:
        yield connection


def _unauthorized(detail: str = "Silakan masuk terlebih dahulu.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dev_user_id: int | None = Header(default=None, alias="X-Dev-User-Id"),
) -> dict[str, Any]:
    """User dari `Authorization: Bearer <access token>`.

    X-Dev-User-Id hanya diterima saat APP_ENV=development (untuk curl/uji manual) dan ditolak di luar itu.
    Tidak ada user bawaan: tanpa kredensial, permintaan ditolak 401.
    User selalu dibaca ulang dari DB agar akun yang dihapus atau rolenya berubah langsung berlaku.
    """
    settings = get_settings()
    user_id: int | None = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        payload = decode_access_token(token.strip(), settings) if scheme.lower() == "bearer" else None
        if not payload:
            raise _unauthorized("Sesi masuk tidak valid atau sudah berakhir.")
        user_id = int(payload["sub"])
    elif x_dev_user_id is not None:
        if not settings.is_development:
            raise _unauthorized("Header X-Dev-User-Id hanya diizinkan di lingkungan development.")
        user_id = x_dev_user_id
    else:
        raise _unauthorized()

    pool: asyncpg.Pool | None = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database connection pool belum siap.")
    async with pool.acquire() as conn:
        user = await get_user_by_id(conn, user_id)
    if not user or not user.get("activated_at"):
        raise _unauthorized("Akun tidak ditemukan atau belum diaktifkan.")
    user["role"] = str(user["role"])
    return user


def require_role(*roles: str) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Dependency: user yang sedang masuk, dan rolenya harus salah satu dari `roles` (403 bila tidak)."""

    async def checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Peran akun Anda tidak diizinkan untuk tindakan ini.")
        return user

    return checker


async def can_view_session(conn: asyncpg.Connection, session: dict[str, Any], user: dict[str, Any]) -> bool:
    role = user.get("role")
    if role == "student":
        return session.get("student_id") == user.get("id")
    if role == "lecturer":
        # Sesi mandiri (class_id NULL) tidak pernah terlihat oleh dosen.
        return bool(session.get("class_id")) and await lecturer_manages_session(conn, session["id"], user["id"])
    return False  # admin dan role lain: tidak membuka sesi (BRD 7.1 no. 16, BRD 5)


async def ensure_can_view_session(conn: asyncpg.Connection, session: dict[str, Any], user: dict[str, Any]) -> None:
    """Untuk MEMBACA sesi (detail, transkrip, topik, evaluasi, audio klien). 403 bila tidak berhak."""
    if not await can_view_session(conn, session, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_FORBIDDEN_SESSION)


def ensure_session_owner(session: dict[str, Any], user: dict[str, Any]) -> None:
    """Untuk MENGUBAH sesi (kirim giliran, transkripsi, akhiri, minta evaluasi): hanya mahasiswa pemiliknya."""
    if user.get("role") != "student" or session.get("student_id") != user.get("id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_FORBIDDEN_SESSION)


def is_reviewer(user: dict[str, Any]) -> bool:
    """Dosen yang sudah lolos load_session_for_viewer boleh melihat semua topik (termasuk yang kosong)."""
    return user.get("role") == "lecturer"
