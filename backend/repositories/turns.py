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


async def get_timeline(conn: asyncpg.Connection, session_id: int) -> dict[str, int]:
    """Garis waktu sesi (ms sejak simulasi dimulai).

    end_ms: akhir giliran terakhir yang tersimpan. wall_ms: waktu nyata sejak sesi dibuat, batas atas
    garis waktu aktif (jeda saat mahasiswa pergi tidak masuk garis waktu, jadi aktif <= nyata).
    """
    row = await conn.fetchrow(
        """
        SELECT COALESCE((SELECT max(t.end_ms) FROM turns t WHERE t.session_id = s.id), 0) AS end_ms,
               GREATEST(0, floor(EXTRACT(EPOCH FROM (now() - s.started_at)) * 1000))::bigint AS wall_ms
        FROM sessions s
        WHERE s.id = $1
        """,
        session_id,
    )
    return {"end_ms": int(row["end_ms"]), "wall_ms": int(row["wall_ms"])}


async def get_spoken_counselor_turns(conn: asyncpg.Connection, session_id: int) -> list[dict[str, Any]]:
    """Satu-satunya sumber giliran untuk pengamatan vokal (Rubrik 2.6): hanya ucapan.

    Giliran ketikan (word_timestamps NULL) tidak punya durasi bicara, jadi tidak ikut.
    """
    rows = await conn.fetch(
        """
        SELECT id, turn_no, content, start_ms, end_ms, word_timestamps
        FROM turns
        WHERE session_id = $1 AND speaker = 'counselor' AND word_timestamps IS NOT NULL
        ORDER BY turn_no ASC
        """,
        session_id,
    )
    return [dict(r) for r in rows]


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
    """Menyimpan satu giliran percakapan ke tabel turns.

    word_timestamps None = giliran diketik (atau giliran klien); list, walau kosong = diucapkan.
    """
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
        None if word_timestamps is None else json.dumps(word_timestamps),
    )
    return int(turn_id)


async def get_session_turns(conn: asyncpg.Connection, session_id: int) -> list[dict[str, Any]]:
    """Mengambil riwayat percakapan sesi konseling secara berurutan."""
    rows = await conn.fetch(
        """
        SELECT id, session_id, turn_no, speaker, content, start_ms, end_ms, created_at,
               CASE WHEN speaker = 'counselor'
                    THEN CASE WHEN word_timestamps IS NULL THEN 'text' ELSE 'voice' END
               END AS input_mode
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
