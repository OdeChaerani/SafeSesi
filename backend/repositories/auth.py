"""Query autentikasi: akun, refresh token (rotasi per family), dan token aktivasi."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg

_USER_COLUMNS = "id, name, email, role::text AS role, password_hash, activated_at"


async def get_user_for_login(conn: asyncpg.Connection, email: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        f"SELECT {_USER_COLUMNS} FROM users WHERE lower(email) = lower($1) AND deleted_at IS NULL",
        email.strip(),
    )
    return dict(row) if row else None


async def create_user_with_activation(
    conn: asyncpg.Connection, name: str, email: str, role: str, token_hash: str, expires_at: datetime
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        INSERT INTO users (name, email, role, activation_token_hash, activation_token_expires_at)
        VALUES ($1, $2, $3::user_role, $4, $5)
        RETURNING id, name, email, role::text AS role
        """,
        name.strip(),
        email.strip(),
        role,
        token_hash,
        expires_at,
    )
    return dict(row)


async def get_user_by_activation_hash(conn: asyncpg.Connection, token_hash: str) -> dict[str, Any] | None:
    """Dikunci (FOR UPDATE) agar token yang sama tidak bisa dipakai dua permintaan sekaligus."""
    row = await conn.fetchrow(
        """
        SELECT id, activation_token_expires_at, activated_at
        FROM users
        WHERE activation_token_hash = $1 AND deleted_at IS NULL
        FOR UPDATE
        """,
        token_hash,
    )
    return dict(row) if row else None


async def activate_user(conn: asyncpg.Connection, user_id: int, password_hash: str) -> None:
    """Menetapkan password dan menghapus token aktivasi: token hanya bisa dipakai sekali."""
    await conn.execute(
        """
        UPDATE users
        SET password_hash = $2, activated_at = now(),
            activation_token_hash = NULL, activation_token_expires_at = NULL
        WHERE id = $1
        """,
        user_id,
        password_hash,
    )


async def insert_refresh_token(
    conn: asyncpg.Connection, user_id: int, token_hash: str, expires_at: datetime, family_id: int | None = None
) -> int:
    """Token baru. Tanpa family_id: token pertama sebuah login, family_id = id-nya sendiri."""
    token_id = await conn.fetchval(
        """
        INSERT INTO refresh_tokens (user_id, family_id, token_hash, expires_at)
        VALUES ($1, COALESCE($4, 0), $2, $3)
        RETURNING id
        """,
        user_id,
        token_hash,
        expires_at,
        family_id,
    )
    if family_id is None:
        await conn.execute("UPDATE refresh_tokens SET family_id = id WHERE id = $1", token_id)
    return token_id


async def get_refresh_token_for_update(conn: asyncpg.Connection, token_hash: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT rt.id, rt.user_id, rt.family_id, rt.expires_at, rt.revoked_at, rt.replaced_by,
               u.name, u.email, u.role::text AS role, u.activated_at, u.deleted_at
        FROM refresh_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token_hash = $1
        FOR UPDATE OF rt
        """,
        token_hash,
    )
    return dict(row) if row else None


async def mark_refresh_token_replaced(conn: asyncpg.Connection, token_id: int, replaced_by: int) -> None:
    await conn.execute(
        "UPDATE refresh_tokens SET revoked_at = now(), replaced_by = $2 WHERE id = $1",
        token_id,
        replaced_by,
    )


async def revoke_refresh_family(conn: asyncpg.Connection, family_id: int) -> None:
    await conn.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE family_id = $1 AND revoked_at IS NULL",
        family_id,
    )
