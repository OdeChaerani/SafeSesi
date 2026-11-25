"""Catatan audit tindakan admin (tabel admin_audit_log). Tidak pernah menerima token, hash token, atau tautan."""
from __future__ import annotations

import asyncpg


async def log_admin_action(
    conn: asyncpg.Connection, actor_id: int, target_user_id: int, action: str, ip: str | None
) -> None:
    await conn.execute(
        "INSERT INTO admin_audit_log (actor_id, target_user_id, action, ip) VALUES ($1, $2, $3, $4)",
        actor_id,
        target_user_id,
        action,
        ip,
    )
