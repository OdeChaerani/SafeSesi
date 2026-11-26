from __future__ import annotations

import json
from typing import Any
import asyncpg

from repositories.turns import get_timeline


async def create_session(
    conn: asyncpg.Connection,
    student_id: int,
    scenario_id: int,
    scenario_snapshot: dict[str, Any] | str,
    class_id: int | None = None,
    parent_session_id: int | None = None,
) -> dict[str, Any]:
    """Menyimpan sesi konseling baru ke tabel sessions."""
    snapshot_json = (
        scenario_snapshot
        if isinstance(scenario_snapshot, str)
        else json.dumps(scenario_snapshot)
    )

    row = await conn.fetchrow(
        """
        INSERT INTO sessions (
            student_id, scenario_id, class_id, parent_session_id, scenario_snapshot, status, started_at
        ) VALUES (
            $1, $2, $3, $4, $5::jsonb, 'in_progress', now()
        )
        RETURNING id, student_id, scenario_id, class_id, parent_session_id, scenario_snapshot, status, started_at, ended_at, duration_seconds
        """,
        student_id,
        scenario_id,
        class_id,
        parent_session_id,
        snapshot_json,
    )
    result = dict(row)
    if isinstance(result["scenario_snapshot"], str):
        result["scenario_snapshot"] = json.loads(result["scenario_snapshot"])
    return result


async def get_session_by_id(conn: asyncpg.Connection, session_id: int) -> dict[str, Any] | None:
    """Mengambil sesi yang belum dihapus berdasarkan ID."""
    row = await conn.fetchrow(
        """
        SELECT id, student_id, scenario_id, class_id, parent_session_id, scenario_snapshot, status, started_at, ended_at, duration_seconds
        FROM sessions
        WHERE id = $1 AND deleted_at IS NULL
        """,
        session_id,
    )
    if not row:
        return None
    res = dict(row)
    if isinstance(res["scenario_snapshot"], str):
        res["scenario_snapshot"] = json.loads(res["scenario_snapshot"])
    return res


def active_duration_seconds(last_turn_end_ms: int, ended_ms: int, wall_ms: int) -> int:
    """Durasi sesi = titik akhir garis waktu aktif, bukan ended_at - started_at.

    ended_ms: posisi garis waktu saat sesi diakhiri (0 bila tidak dikirim). Dibatasi waktu nyata,
    dan tidak pernah lebih pendek daripada akhir giliran terakhir.
    """
    return max(last_turn_end_ms, min(ended_ms, wall_ms)) // 1000


async def end_session(conn: asyncpg.Connection, session_id: int, ended_ms: int = 0) -> dict[str, Any] | None:
    """Mengakhiri sesi konseling: status='completed', ended_at=now(), simpan durasi garis waktu aktif.

    Dipanggil sambil memegang lock giliran, jadi tidak ada giliran baru di antara baca dan tulis.
    """
    timeline = await get_timeline(conn, session_id)
    duration = active_duration_seconds(timeline["end_ms"], ended_ms, timeline["wall_ms"])
    row = await conn.fetchrow(
        """
        UPDATE sessions
        SET status = 'completed',
            ended_at = now(),
            duration_seconds = $2
        WHERE id = $1 AND status = 'in_progress'
        RETURNING id, student_id, scenario_id, class_id, parent_session_id, scenario_snapshot, status, started_at, ended_at, duration_seconds
        """,
        session_id,
        duration,
    )
    if not row:
        return None
    res = dict(row)
    if isinstance(res["scenario_snapshot"], str):
        res["scenario_snapshot"] = json.loads(res["scenario_snapshot"])
    return res


# Status evaluasi terbaru sebuah sesi (LATERAL: aman bila suatu saat ada lebih dari satu baris).
_LATEST_EVALUATION = """
    LEFT JOIN LATERAL (
        SELECT e.status::text AS status FROM evaluations e
        WHERE e.session_id = s.id ORDER BY e.id DESC LIMIT 1
    ) ev ON TRUE
"""


async def list_student_sessions(
    conn: asyncpg.Connection,
    student_id: int,
    *,
    kind: str = "all",
    scenario_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Riwayat sesi milik mahasiswa (terbaru dulu) beserta hitungan untuk ringkasan beranda.

    Hanya field publik yang diambil dari snapshot (judul skenario dan nama klien); persona lengkap,
    kasus, hidden facts, dan kondisi klien tidak ikut dibaca.
    """
    args: list[Any] = [student_id]
    conditions = ["s.student_id = $1", "s.deleted_at IS NULL"]
    if kind == "independent":
        conditions.append("s.class_id IS NULL")
    elif kind == "class":
        conditions.append("s.class_id IS NOT NULL")
    if scenario_id is not None:
        args.append(scenario_id)
        conditions.append(f"s.scenario_id = ${len(args)}")
    if status is not None:
        args.append(status)
        conditions.append(f"s.status::text = ${len(args)}")
    args.append(limit)

    rows = await conn.fetch(
        f"""
        SELECT s.id, s.scenario_id, s.class_id, s.parent_session_id, s.status::text AS status,
               s.started_at, s.ended_at, s.duration_seconds,
               s.scenario_snapshot #>> '{{scenario,title}}' AS scenario_title,
               s.scenario_snapshot #>> '{{persona,name}}' AS client_name,
               cl.name AS class_name,
               COALESCE(ev.status, 'none') AS evaluation_status,
               COUNT(*) OVER () AS total_count
        FROM sessions s
        LEFT JOIN classes cl ON cl.id = s.class_id AND cl.deleted_at IS NULL
        {_LATEST_EVALUATION}
        WHERE {" AND ".join(conditions)}
        ORDER BY s.started_at DESC, s.id DESC
        LIMIT ${len(args)}
        """,
        *args,
    )
    counts = await conn.fetchrow(
        f"""
        SELECT count(*) AS total_sessions,
               count(*) FILTER (WHERE s.status = 'completed') AS completed_sessions,
               count(*) FILTER (WHERE s.status = 'completed' AND ev.status IS NULL) AS awaiting_evaluation,
               count(*) FILTER (WHERE s.status = 'completed' AND ev.status = 'failed') AS evaluation_failed,
               COALESCE(sum(s.duration_seconds) FILTER (WHERE s.status = 'completed'), 0) AS total_duration_seconds
        FROM sessions s
        {_LATEST_EVALUATION}
        WHERE s.student_id = $1 AND s.deleted_at IS NULL
        """,
        student_id,
    )
    items = []
    for r in rows:
        item = dict(r)
        item.pop("total_count", None)
        item["kind"] = "class" if item["class_id"] is not None else "independent"
        item["scenario_title"] = item["scenario_title"] or ""
        item["client_name"] = item["client_name"] or ""
        items.append(item)
    return {
        "items": items,
        "total": rows[0]["total_count"] if rows else 0,
        **dict(counts),
    }
