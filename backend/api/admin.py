"""Pengelolaan akun oleh admin (BRD 3.3: akun disediakan Admin)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from api.deps import get_db, require_role
from core.config import Settings, get_settings
from core.rate_limit import client_ip
from core.security import hash_token, new_opaque_token
from repositories.audit import log_admin_action
from repositories.auth import (
    create_user_with_activation,
    get_user_for_admin_reset,
    issue_activation_token,
    issue_reset_token,
)
from repositories.profiles import ProfileError, insert_profile, normalize_profile
from repositories.users import list_users
from schemas.admin import AccountStatus, AdminUserList
from schemas.auth import CreateUserRequest, Role

router = APIRouter(prefix="/admin", tags=["admin"])

# Nama indeks unik di database -> (isian, pesan). Selain ini dianggap email ganda.
_DUPLICATES = {
    "uq_students_npm": ("npm", "NPM sudah dipakai oleh akun lain."),
    "uq_lecturers_nip": ("nip", "NIP sudah dipakai oleh akun lain."),
}
_DUPLICATE_EMAIL = ("email", "Email ini sudah dipakai akun lain.")


def _field_error(status_code: int, field: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "field": field})


def _new_activation(settings: Settings) -> tuple[str, datetime]:
    """Token aktivasi baru dan masa berlakunya (sama untuk akun baru dan kirim ulang)."""
    return new_opaque_token(), datetime.now(timezone.utc) + timedelta(hours=settings.ACTIVATION_TOKEN_HOURS)


def _activation_response(user: dict[str, Any], token: str, expires_at: datetime, settings: Settings) -> dict[str, Any]:
    # Token ada di fragmen (#) agar tidak terkirim ke server atau tercatat di log saat tautan dibuka.
    url = f"{settings.FRONTEND_URL.rstrip('/')}/aktivasi#token={token}"
    return {"user": user, "activation_url": url, "expires_at": expires_at}


@router.get("/users", response_model=AdminUserList)
async def get_users(
    page: int = Query(1, ge=1, le=100_000),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    role: Role | None = None,
    account_status: AccountStatus | None = Query(None, alias="status"),
    class_id: int | None = Query(None, ge=1, le=2**63 - 1),
    _admin: dict[str, Any] = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Daftar akun yang belum dihapus: pencarian nama/email/NPM/NIP, saringan role, status, dan kelas."""
    items, total = await list_users(
        conn,
        q=q,
        role=role,
        status=account_status,
        class_id=class_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    admin: dict[str, Any] = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Membuat akun belum aktif, baris profilnya, dan tautan aktivasi dalam satu transaksi.

    Tautan hanya ditampilkan sekali di respons ini (yang tersimpan hanya hash token); admin
    menyampaikannya sendiri ke pengguna karena pengiriman email belum tersedia.
    """
    try:
        profile = normalize_profile(payload.role, payload.npm, payload.asal_institusi, payload.nip)
    except ProfileError as exc:
        return _field_error(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.field, str(exc))
    settings = get_settings()
    token, expires_at = _new_activation(settings)
    try:
        async with conn.transaction():  # profil gagal = pengguna dan token ikut dibatalkan
            user = await create_user_with_activation(
                conn, payload.name, payload.email, payload.role, hash_token(token), expires_at
            )
            if profile is not None:
                await insert_profile(conn, user["id"], profile)
            await log_admin_action(conn, admin["id"], user["id"], "create_user", None)
    except asyncpg.UniqueViolationError as exc:
        field, detail = _DUPLICATES.get(getattr(exc, "constraint_name", None), _DUPLICATE_EMAIL)
        return _field_error(status.HTTP_409_CONFLICT, field, detail)
    return _activation_response(user, token, expires_at, settings)


@router.post("/users/{user_id}/resend-activation")
async def resend_activation(
    user_id: int,
    admin: dict[str, Any] = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Menerbitkan tautan aktivasi baru (tampil sekali) untuk akun yang belum aktif; tautan lama batal."""
    target = await get_user_for_admin_reset(conn, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Akun tidak ditemukan.")
    if target["role"] == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tautan aktivasi akun admin tidak bisa diterbitkan lewat jalur ini.",
        )
    already_active = HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Akun ini sudah aktif. Gunakan reset kata sandi bila pengguna lupa kata sandinya.",
    )
    if target["activated_at"] is not None:
        raise already_active
    settings = get_settings()
    token, expires_at = _new_activation(settings)
    async with conn.transaction():  # token dan catatan audit tersimpan bersama atau tidak sama sekali
        user = await issue_activation_token(conn, user_id, hash_token(token), expires_at)
        if user is not None:
            await log_admin_action(conn, admin["id"], user_id, "resend_activation", None)
    if user is None:  # berubah di antara pemeriksaan dan penerbitan (mis. baru saja diaktifkan)
        raise already_active
    return _activation_response(user, token, expires_at, settings)


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
