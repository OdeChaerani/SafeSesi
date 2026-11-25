"""Respons pengelolaan akun untuk admin. Kolom eksplisit: hash dan token tidak pernah ikut terkirim."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from schemas.auth import Role

AccountStatus = Literal["aktif", "menunggu", "kedaluwarsa"]


class AdminUserRow(BaseModel):
    id: int
    name: str
    email: str
    role: Role
    npm: str | None
    asal_institusi: str | None
    nip: str | None
    status: AccountStatus
    classes: list[str]


class AdminUserList(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int
