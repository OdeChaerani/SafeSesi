"""Password, access token (JWT), dan token acak untuk refresh/aktivasi.

- Password: argon2id (argon2-cffi), parameter bawaan library (rekomendasi OWASP).
- Access token: JWT HS256 berumur pendek, berisi sub (id user), role, type=access.
- Refresh & aktivasi: token acak; yang disimpan di database hanya hash SHA-256-nya, sehingga
  kebocoran tabel tidak memberi token yang bisa dipakai.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from core.config import Settings

_hasher = PasswordHasher()
# Hash pembanding untuk email yang tidak terdaftar: verifikasi tetap berjalan agar waktu respons
# login sama, sehingga keberadaan email tidak bisa ditebak dari lamanya respons.
_DUMMY_HASH = _hasher.hash("dummy-password-untuk-waktu-konstan")

JWT_ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """True bila cocok. Hash kosong (akun belum aktif) tetap diverifikasi terhadap hash pembanding."""
    try:
        return _hasher.verify(hashed_password or _DUMMY_HASH, plain_password) and bool(hashed_password)
    except (VerificationError, InvalidHashError):
        return False


def password_problem(password: str) -> str | None:
    """Pesan bila password tidak memenuhi aturan, atau None bila sudah sesuai."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Kata sandi minimal {MIN_PASSWORD_LENGTH} karakter."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Kata sandi maksimal {MAX_PASSWORD_LENGTH} karakter."
    return None


def create_access_token(user: dict[str, Any], settings: Settings, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "role": str(user["role"]),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any] | None:
    """Payload bila token sah, belum kedaluwarsa, dan bertipe access; None bila tidak."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "access" else None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
