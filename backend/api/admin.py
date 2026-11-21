"""Pengelolaan akun oleh admin (BRD 3.3: akun disediakan Admin). Halaman admin menyusul."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_db, require_role
from core.config import get_settings
from core.security import hash_token, new_opaque_token
from repositories.auth import create_user_with_activation
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
