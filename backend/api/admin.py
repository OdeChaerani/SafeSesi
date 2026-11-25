"""Pengelolaan akun oleh admin (BRD 3.3: akun disediakan Admin). Halaman admin menyusul."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.deps import get_db, require_role
from core.config import get_settings
from core.rate_limit import client_ip
from core.security import hash_token, new_opaque_token
from repositories.audit import log_admin_action
from repositories.auth import create_user_with_activation, get_user_for_admin_reset, issue_reset_token
from schemas.auth import CreateUserRequest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    _admin: dict[str, Any] = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Membuat akun belum aktif beserta tautan aktivasi.

    Tautan hanya ditampilkan sekali di respons ini (yang tersimpan hanya hash token); admin
    menyampaikannya sendiri ke pengguna karena pengiriman email belum tersedia. Token ada di
    fragmen (#) agar tidak terkirim ke server atau tercatat di log saat tautan dibuka.
    """
    settings = get_settings()
    token = new_opaque_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_HOURS)
    try:
        user = await create_user_with_activation(conn, payload.name, payload.email, payload.role, hash_token(token), expires_at)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ini sudah dipakai akun lain.") from exc
    return {
        "user": user,
        "activation_url": f"{settings.FRONTEND_URL.rstrip('/')}/aktivasi#token={token}",
        "expires_at": expires_at,
    }


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: Request,
    admin: dict[str, Any] = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Menerbitkan tautan atur ulang kata sandi sekali pakai untuk akun yang sudah aktif.

    Admin tidak pernah melihat atau menetapkan kata sandi; pengguna memilihnya sendiri lewat tautan.
    Tautan hanya tampil sekali di respons ini. Tautan reset sebelumnya milik pengguna itu otomatis batal.
    Akun admin tidak bisa diatur ulang lewat sini (agar satu admin tidak bisa mengambil alih admin lain);
    pemulihannya lewat skrip di server. Setiap penerbitan dicatat di admin_audit_log (tanpa token).
    """
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Akun sendiri tidak bisa diatur ulang lewat jalur ini. Gunakan fitur ganti kata sandi.",
        )
    target = await get_user_for_admin_reset(conn, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    if target["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun admin tidak bisa diatur ulang lewat jalur ini. Gunakan skrip pemulihan di server.",
        )
    if target["activated_at"] is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Akun ini belum diaktifkan. Buat ulang akun untuk mendapat tautan aktivasi.",
        )
    settings = get_settings()
    token = new_opaque_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_MINUTES)
    async with conn.transaction():  # token dan catatan audit tersimpan bersama atau tidak sama sekali
        user = await issue_reset_token(conn, user_id, hash_token(token), expires_at)
        if user is not None:
            await log_admin_action(conn, admin["id"], user_id, "issue_reset_token", client_ip(request, settings))
    if user is None:  # berubah di antara pemeriksaan dan penerbitan (mis. baru dihapus)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    return {
        "user": user,
        "reset_url": f"{settings.FRONTEND_URL.rstrip('/')}/reset-password#token={token}",
        "expires_at": expires_at,
    }
