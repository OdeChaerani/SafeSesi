from __future__ import annotations

import json
from typing import Any
import asyncpg


async def get_next_turn_no(conn: asyncpg.Connection, session_id: int) -> int:
    """Mengambil nomor urut turn berikutnya untuk session_id."""
    val = await conn.fetchval(
        """
        SELECT COALESCE(MAX(turn_no), 0) + 1
        FROM turns
        WHERE session_id = $1
        """,
        session_id,
    )
    return int(val)


async def save_turn(
    conn: asyncpg.Connection,
    session_id: int,
    turn_no: int,
    speaker: str,  # 'counselor' | 'client'
    content: str,
    start_ms: int = 0,
    end_ms: int = 0,
    word_timestamps: list[dict[str, Any]] | None = None,  # STT: {word, start_ms, end_ms} relatif ke sesi
) -> int:
    """Menyimpan satu giliran percakapan ke tabel turns."""
    turn_id = await conn.fetchval(
        """
        INSERT INTO turns (
            session_id, turn_no, speaker, content, start_ms, end_ms, word_timestamps
        ) VALUES (
            $1, $2, $3::speaker, $4, $5, $6, $7::jsonb
        )
        RETURNING id
        """,
        session_id,
        turn_no,
        speaker,
        content,
        start_ms,
        end_ms,
        json.dumps(word_timestamps) if word_timestamps else None,
    )
    return int(turn_id)


async def get_session_turns(conn: asyncpg.Connection, session_id: int) -> list[dict[str, Any]]:
    """Mengambil riwayat percakapan sesi konseling secara berurutan."""
    rows = await conn.fetch(
        """
        SELECT id, session_id, turn_no, speaker, content, start_ms, end_ms, created_at
        FROM turns
        WHERE session_id = $1
        ORDER BY turn_no ASC
        """,
        session_id,
    )
    return [dict(r) for r in rows]



async def get_turn(conn: asyncpg.Connection, session_id: int, turn_no: int) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT id, turn_no, speaker::text AS speaker, content FROM turns WHERE session_id = $1 AND turn_no = $2",
        session_id,
        turn_no,
    )
    return dict(row) if row else None
