"""Login, refresh (rotasi), logout, dan aktivasi akun (BRD 3.3 no. 1).

Refresh token disimpan di cookie httpOnly (tidak terbaca JavaScript) dan di tabel refresh_tokens
sebagai hash. Setiap refresh memutar token dalam family yang sama; token yang sudah diganti lalu
dipakai lagi dianggap dicuri sehingga seluruh family dicabut.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from api.deps import get_current_user, get_db
from core.config import Settings, get_settings
from core.rate_limit import client_ip, enforce, get_store
from core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    password_problem,
    verify_password,
)
from repositories.auth import (
    activate_user,
    get_password_hash_for_update,
    get_refresh_token_for_update,
    get_user_by_activation_hash,
    get_user_for_login,
    insert_refresh_token,
    mark_refresh_token_replaced,
    revoke_all_refresh_families,
    revoke_refresh_family,
    set_password_hash,
)
from repositories.classes import list_user_classes
from repositories.profiles import get_profile
from schemas.auth import ActivateRequest, ChangePasswordRequest, LoginRequest, TokenResponse
from schemas.profile import AdminMe, LecturerMe, StudentMe

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "safesesi_refresh"
# Cookie hanya dikirim ke endpoint auth, bukan ke setiap permintaan API.
REFRESH_COOKIE_PATH = "/api/v1/auth"
_LOGIN_FAILED = "Email atau kata sandi salah."
_REFRESH_FAILED = "Sesi masuk sudah berakhir. Silakan masuk lagi."
_CURRENT_PASSWORD_WRONG = "Kata sandi saat ini salah."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_DAYS * 86400,
        httponly=True,
        # Lax: tidak terkirim pada POST lintas situs (melindungi dari CSRF). Di production dengan
        # frontend & API beda situs, ubah ke SameSite=None (wajib Secure) atau satukan domainnya.
        samesite="lax",
        secure=not settings.is_development,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, samesite="lax", secure=not settings.is_development
    )


def _token_response(user: dict[str, Any], settings: Settings) -> dict[str, Any]:
    return {
        "access_token": create_access_token(user, settings),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_MINUTES * 60,
        "user": {k: user[k] for k in ("id", "name", "email", "role")},
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, response: Response, request: Request, conn: asyncpg.Connection = Depends(get_db)
) -> Any:
    settings = get_settings()
    # Dua lapis: semua percobaan per IP (longgar), dan percobaan per IP + email. Kunci memuat IP
    # sehingga orang lain tidak bisa mengunci akun korban. Percobaan dicatat SEBELUM verifikasi
    # (tahan terhadap permintaan paralel) dan dihapus saat login berhasil, jadi yang tersisa hanya yang gagal.
    pair_key = None
    if settings.RATE_LIMIT_ENABLED:
        store, ip = get_store(settings), client_ip(request, settings)
        enforce(store, f"login:ip:{ip}", "login_ip")
        pair_key = f"login:ip-email:{ip}|{payload.email.strip().lower()}"
        enforce(store, pair_key, "login_pair")
    user = await get_user_for_login(conn, payload.email)
    # Verifikasi tetap dijalankan walau email tidak ada / akun belum aktif (waktu respons sama),
    # dan pesannya selalu sama agar keberadaan akun tidak bisa ditebak.
    ok = verify_password(payload.password, user.get("password_hash") if user else None)
    if not user or not ok or not user.get("activated_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_LOGIN_FAILED)
    if pair_key:
        get_store(settings).clear(pair_key)

    refresh = new_opaque_token()
    async with conn.transaction():
        await insert_refresh_token(
            conn, user["id"], hash_token(refresh), _now() + timedelta(days=settings.REFRESH_TOKEN_DAYS)
        )
    _set_refresh_cookie(response, refresh, settings)
    return _token_response(user, settings)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_session(
    response: Response,
    request: Request,
    conn: asyncpg.Connection = Depends(get_db),
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> Any:
    settings = get_settings()
    if settings.RATE_LIMIT_ENABLED:
        enforce(get_store(settings), f"refresh:ip:{client_ip(request, settings)}", "refresh")
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_REFRESH_FAILED)

    new_refresh = new_opaque_token()
    user: dict[str, Any] | None = None
    # Keputusan diambil di dalam transaksi; error dilempar SETELAH commit agar pencabutan family
    # (saat token lama dipakai ulang) tetap tersimpan, tidak ikut di-rollback.
    async with conn.transaction():
        row = await get_refresh_token_for_update(conn, hash_token(refresh_cookie))
        if row is None or row["expires_at"] <= _now():
            pass
        elif (
            row["revoked_at"] is not None
            or row.get("replaced_by") is not None
            or row.get("deleted_at") is not None
            or not row.get("activated_at")
        ):
            # Token yang sudah diganti dipakai lagi (indikasi dicuri) atau akun tidak aktif: cabut semua.
            await revoke_refresh_family(conn, row["family_id"])
        else:
            new_id = await insert_refresh_token(
                conn,
                row["user_id"],
                hash_token(new_refresh),
                _now() + timedelta(days=settings.REFRESH_TOKEN_DAYS),
                family_id=row["family_id"],
            )
            await mark_refresh_token_replaced(conn, row["id"], new_id)
            user = {"id": row["user_id"], "name": row["name"], "email": row["email"], "role": row["role"]}

    if user is None:
        # JSONResponse (bukan HTTPException) agar cookie yang sudah tidak berlaku ikut dihapus.
        failed = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": _REFRESH_FAILED})
        _clear_refresh_cookie(failed, settings)
        return failed
    _set_refresh_cookie(response, new_refresh, settings)
    return _token_response(user, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    refresh_cookie: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> Response:
    """Mencabut family refresh token perangkat ini (access token habis sendiri dalam beberapa menit)."""
    settings = get_settings()
    if refresh_cookie:
        async with conn.transaction():
            row = await get_refresh_token_for_update(conn, hash_token(refresh_cookie))
            if row is not None:
                await revoke_refresh_family(conn, row["family_id"])
    response.status_code = status.HTTP_204_NO_CONTENT
    _clear_refresh_cookie(response, settings)
    return response


@router.post("/activate")
async def activate_account(
    payload: ActivateRequest, request: Request, conn: asyncpg.Connection = Depends(get_db)
) -> dict[str, str]:
    """Aktivasi akun baru ATAU atur ulang kata sandi lewat tautan dari admin (token sekali pakai, ada masa berlaku).

    Satu endpoint untuk keduanya: pencarian token, kunci baris, kedaluwarsa, aturan password, dan pembatasan
    percobaan identik; yang berbeda hanya tujuan token (activation_token_purpose) dan pencabutan sesi lama.
    """
    settings = get_settings()
    if settings.RATE_LIMIT_ENABLED:
        enforce(get_store(settings), f"activate:ip:{client_ip(request, settings)}", "activate")
    problem = password_problem(payload.password)
    if problem:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=problem)

    async with conn.transaction():
        user = await get_user_by_activation_hash(conn, hash_token(payload.token))
        expires = user.get("activation_token_expires_at") if user else None
        is_reset = bool(user) and user["activation_token_purpose"] == "reset"
        # Token reset hanya untuk akun yang sudah aktif, token aktivasi hanya untuk yang belum: tidak boleh saling dipakai.
        if user is not None and is_reset != (user["activated_at"] is not None):
            user = None
        if user is None:
            # Token tidak dikenal, sudah dipakai (hash dihapus saat berhasil), atau tujuannya tidak cocok dengan akun.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tautan aktivasi tidak valid atau sudah dipakai. Minta tautan baru kepada admin.",
            )
        if expires is None or expires <= _now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tautan aktivasi sudah kedaluwarsa. Minta tautan baru kepada admin.",
            )
        await activate_user(conn, user["id"], hash_password(payload.password))
        if is_reset:
            await revoke_all_refresh_families(conn, user["id"])
    if is_reset:
        return {"message": "Kata sandi berhasil diatur ulang. Silakan masuk dengan kata sandi baru."}
    return {"message": "Akun berhasil diaktifkan. Silakan masuk dengan kata sandi baru."}


@router.get("/me", response_model=StudentMe | LecturerMe | AdminMe)
async def me(
    user: dict[str, Any] = Depends(get_current_user), conn: asyncpg.Connection = Depends(get_db)
) -> Any:
    """Data akun pengguna yang sedang masuk, dibaca dari database (get_current_user), bukan dari token.

    Tidak menerima parameter id: hanya data milik sendiri. Baris profil yang belum ada menjadi nilai kosong.
    """
    # status selalu "active": akun yang belum aktif atau dihapus sudah ditolak get_current_user.
    base = {k: user[k] for k in ("id", "name", "email", "role", "created_at", "activated_at")} | {"status": "active"}
    if user["role"] == "admin":
        return AdminMe(**base)
    profile = await get_profile(conn, user["id"], user["role"])
    classes = await list_user_classes(conn, user["id"])
    if user["role"] == "student":
        return StudentMe(
            **base,
            npm=getattr(profile, "npm", None),
            asal_institusi=getattr(profile, "asal_institusi", None),
            classes=classes,
        )
    return LecturerMe(**base, nip=getattr(profile, "nip", None), classes=classes)


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Ganti kata sandi pengguna yang sedang masuk.

    Semua sesi di semua perangkat dicabut, lalu perangkat ini langsung diberi sesi baru agar tidak
    terlempar ke login. Kegagalan memakai status 400 (bukan 401) karena frontend menganggap 401
    sebagai access token kedaluwarsa dan mencoba refresh.
    """
    settings = get_settings()
    # Pemeriksaan yang tidak menyentuh kata sandi lama dilakukan dulu, agar salah ketik tidak menghabiskan jatah percobaan.
    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=problem)
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Kata sandi baru tidak boleh sama dengan kata sandi saat ini.",
        )
    pair_key = None
    if settings.RATE_LIMIT_ENABLED:
        pair_key = f"change-password:{user['id']}|{client_ip(request, settings)}"
        enforce(get_store(settings), pair_key, "change_password")  # dicatat dulu, dihapus saat berhasil

    refresh = new_opaque_token()
    async with conn.transaction():
        current_hash = await get_password_hash_for_update(conn, user["id"])
        if not verify_password(payload.current_password, current_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_CURRENT_PASSWORD_WRONG)
        await set_password_hash(conn, user["id"], hash_password(payload.new_password))
        await revoke_all_refresh_families(conn, user["id"])
        await insert_refresh_token(
            conn, user["id"], hash_token(refresh), _now() + timedelta(days=settings.REFRESH_TOKEN_DAYS)
        )
    if pair_key:
        get_store(settings).clear(pair_key)
    _set_refresh_cookie(response, refresh, settings)
    return _token_response(user, settings)
