from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["student", "lecturer", "admin"]


def _normalize_email(v: str) -> str:
    v = v.strip()
    # shortcut: pemeriksaan bentuk dasar saja (tanpa paket email-validator); validasi penuh saat pengiriman email ditambahkan.
    local, sep, domain = v.partition("@")
    if not sep or not local or "." not in domain or " " in v:
        raise ValueError("Format email tidak valid.")
    return v


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _normalize_email(v)


class ActivateRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., max_length=128)  # aturan lengkap di password_problem (sama dengan aktivasi)


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=254)
    role: Role
    # Isian profil menurut role; aturan dan normalisasinya di repositories/profiles.py.
    npm: str | None = None
    asal_institusi: str | None = None
    nip: str | None = None

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _normalize_email(v)


class AuthUser(BaseModel):
    id: int
    name: str
    email: str
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(..., description="Umur access token dalam detik")
    user: AuthUser
