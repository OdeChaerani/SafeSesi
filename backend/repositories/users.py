from __future__ import annotations

from typing import Any
import asyncpg


async def get_user_by_id(conn: asyncpg.Connection, user_id: int) -> dict[str, Any] | None:
    """Mengambil data pengguna aktif berdasarkan ID."""
    row = await conn.fetchrow(
        """
        SELECT id, name, email, role, activated_at, created_at
        FROM users
        WHERE id = $1 AND deleted_at IS NULL
        """,
        user_id,
    )
    return dict(row) if row else None


# Status akun diturunkan (bukan kolom): punya password = aktif; kalau belum, tergantung masa token aktivasi.
ACCOUNT_STATUS_SQL = """CASE
    WHEN u.password_hash IS NOT NULL THEN 'aktif'
    WHEN u.activation_token_expires_at > now() THEN 'menunggu'
    ELSE 'kedaluwarsa'
END"""

# $1 pola pencarian, $2 role, $3 class_id, $4 status; NULL = tanpa saringan.
_FILTERED_USERS = f"""
    WITH akun AS (
        SELECT u.id, u.name, u.email, u.role::text AS role, s.npm, s.asal_institusi, l.nip,
               {ACCOUNT_STATUS_SQL} AS status
        FROM users u
        LEFT JOIN students s ON s.user_id = u.id
        LEFT JOIN lecturers l ON l.user_id = u.id
        WHERE u.deleted_at IS NULL
          AND ($1::text IS NULL OR u.name ILIKE $1 OR u.email ILIKE $1
               OR s.npm ILIKE replace($1, ' ', '') OR l.nip ILIKE replace($1, ' ', ''))
          AND ($2::text IS NULL OR u.role::text = $2)
          AND ($3::bigint IS NULL OR EXISTS (
                SELECT 1 FROM class_members cm
                JOIN classes c ON c.id = cm.class_id AND c.deleted_at IS NULL
                WHERE cm.user_id = u.id AND cm.class_id = $3 AND cm.deleted_at IS NULL))
    ),
    tersaring AS (SELECT * FROM akun WHERE $4::text IS NULL OR status = $4)
"""


def _like_pattern(q: str | None) -> str | None:
    """Pola ILIKE "mengandung"; karakter % _ \\ dari pengguna dicari apa adanya."""
    q = (q or "").strip()
    if not q:
        return None
    for char in ("\\", "%", "_"):
        q = q.replace(char, "\\" + char)
    return f"%{q}%"


async def list_users(
    conn: asyncpg.Connection,
    *,
    q: str | None,
    role: str | None,
    status: str | None,
    class_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Satu halaman pengguna (terbaru dulu) dan jumlah seluruh hasil. Selalu dua query, berapa pun barisnya."""
    filters = (_like_pattern(q), role, class_id, status)
    total = await conn.fetchval(_FILTERED_USERS + "SELECT count(*) FROM tersaring", *filters)
    rows = await conn.fetch(
        _FILTERED_USERS
        + """
        SELECT t.*, ARRAY(
                   SELECT c.name FROM class_members cm
                   JOIN classes c ON c.id = cm.class_id AND c.deleted_at IS NULL
                   WHERE cm.user_id = t.id AND cm.deleted_at IS NULL
                   ORDER BY c.academic_year DESC, c.name
               ) AS classes
        FROM tersaring t
        ORDER BY t.id DESC
        LIMIT $5 OFFSET $6
        """,
        *filters,
        limit,
        offset,
    )
    return [dict(row) for row in rows], total

