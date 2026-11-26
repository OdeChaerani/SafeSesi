"""Kelas pengguna: daftar kelas yang terhubung dengan akun dan keanggotaannya."""
from __future__ import annotations

from typing import Any

import asyncpg

# Nama dosen = anggota aktif kelas yang berperan lecturer (class_members tidak punya kolom peran).
_LECTURERS = """
    ARRAY(
        SELECT u.name
        FROM class_members lm
        JOIN users u ON u.id = lm.user_id
        WHERE lm.class_id = cl.id AND lm.deleted_at IS NULL
          AND u.role = 'lecturer' AND u.deleted_at IS NULL
        ORDER BY u.name
    )
"""


async def list_user_classes(conn: asyncpg.Connection, user_id: int) -> list[dict[str, Any]]:
    """Kelas aktif tempat pengguna menjadi anggota (mahasiswa: diikuti; dosen: dikelola)."""
    rows = await conn.fetch(
        f"""
        SELECT cl.id, cl.name, cl.academic_year,
               {_LECTURERS} AS lecturers,
               (SELECT count(*) FROM class_scenarios cs
                  JOIN scenarios sc ON sc.id = cs.scenario_id AND sc.deleted_at IS NULL
                 WHERE cs.class_id = cl.id) AS scenario_count
        FROM class_members cm
        JOIN classes cl ON cl.id = cm.class_id AND cl.deleted_at IS NULL
        WHERE cm.user_id = $1 AND cm.deleted_at IS NULL
        ORDER BY cl.academic_year DESC, cl.name ASC
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_class(conn: asyncpg.Connection, class_id: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        f"""
        SELECT cl.id, cl.name, cl.academic_year, {_LECTURERS} AS lecturers
        FROM classes cl
        WHERE cl.id = $1 AND cl.deleted_at IS NULL
        """,
        class_id,
    )
    return dict(row) if row else None


async def is_class_member(conn: asyncpg.Connection, class_id: int, user_id: int) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM class_members WHERE class_id = $1 AND user_id = $2 AND deleted_at IS NULL)",
            class_id,
            user_id,
        )
    )
