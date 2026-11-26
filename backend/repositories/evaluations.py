from __future__ import annotations

import json
from typing import Any
import asyncpg

# Evaluasi 'running' yang tidak berubah selama ini dianggap macet (mis. server restart) dan boleh diulang.
STALE_RUNNING_MINUTES = 15

EVAL_COLUMNS = (
    "id, session_id, status, guideline_version, model_version, assessed_duration_seconds, "
    "limitation_notes, error_message, coding_debug, completed_at, created_at, updated_at"
)


def _row(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if not row:
        return None
    res = dict(row)
    if isinstance(res.get("coding_debug"), str):
        res["coding_debug"] = json.loads(res["coding_debug"])
    return res


async def get_evaluation_by_session(conn: asyncpg.Connection, session_id: int) -> dict[str, Any] | None:
    return _row(await conn.fetchrow(f"SELECT {EVAL_COLUMNS} FROM evaluations WHERE session_id = $1", session_id))


async def claim_evaluation(
    conn: asyncpg.Connection, session_id: int, guideline_version: str, model_version: str
) -> tuple[dict[str, Any], bool]:
    """Buat evaluasi 'running', atau ambil alih evaluasi 'failed'/macet. (baris, perlu_dijalankan)."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO evaluations (session_id, status, guideline_version, model_version)
        VALUES ($1, 'running', $2, $3)
        ON CONFLICT (session_id) DO NOTHING
        RETURNING {EVAL_COLUMNS}
        """,
        session_id,
        guideline_version,
        model_version,
    )
    if row:
        return _row(row), True
    # Atomik: hanya satu request yang berhasil mengambil alih evaluasi gagal/macet.
    row = await conn.fetchrow(
        f"""
        UPDATE evaluations
        SET status = 'running', error_message = NULL, guideline_version = $2, model_version = $3,
            completed_at = NULL
        WHERE session_id = $1
          AND (status = 'failed'
               OR (status = 'running' AND updated_at < now() - make_interval(mins => {STALE_RUNNING_MINUTES})))
        RETURNING {EVAL_COLUMNS}
        """,
        session_id,
        guideline_version,
        model_version,
    )
    if row:
        return _row(row), True
    return await get_evaluation_by_session(conn, session_id), False


async def save_evaluation_results(
    conn: asyncpg.Connection,
    evaluation_id: int,
    result: Any,  # services.evaluation.miti_evaluator.EvaluationResult
    turn_ids: dict[int, int],  # turn_no -> turns.id
    assessed_duration_seconds: int | None,
) -> None:
    """Simpan semua hasil dalam satu transaksi; hasil lama (jika evaluasi diulang) dihapus di transaksi yang sama."""
    async with conn.transaction():
        for table in ("miti_codes", "miti_globals", "process_observations", "feedback_items"):
            await conn.execute(f"DELETE FROM {table} WHERE evaluation_id = $1", evaluation_id)
        if result.codes:
            await conn.executemany(
                """
                INSERT INTO miti_codes (evaluation_id, turn_id, unit_no, code, excerpt, reason, uncertainty_note)
                VALUES ($1, $2, $3, $4::miti_code, $5, $6, $7)
                """,
                [
                    (evaluation_id, turn_ids[c.turn_no], c.unit_no, c.code, c.excerpt, c.reason, c.uncertainty_note)
                    for c in result.codes
                ],
            )
        if result.globals:
            await conn.executemany(
                """
                INSERT INTO miti_globals (evaluation_id, dimension, score, reason, evidence_turn_nos)
                VALUES ($1, $2::global_dimension, $3, $4, $5)
                """,
                [
                    (evaluation_id, dim, g["score"], g["reason"], g["evidence_turn_nos"])
                    for dim, g in result.globals.items()
                ],
            )
        if result.processes:
            await conn.executemany(
                """
                INSERT INTO process_observations (evaluation_id, process, start_turn_no, end_turn_no, excerpt, reason)
                VALUES ($1, $2::mi_process, $3, $4, $5, $6)
                """,
                [
                    (evaluation_id, p["process"], p["start_turn_no"], p["end_turn_no"], p["excerpt"], p["reason"])
                    for p in result.processes
                ],
            )
        if result.feedback:
            await conn.executemany(
                """
                INSERT INTO feedback_items
                    (evaluation_id, kind, turn_id, content, sort_order, excerpt, evidence_turn_nos, explanation)
                VALUES ($1, $2::feedback_kind, $3, $4, $5, $6, $7, $8)
                """,
                [
                    (
                        evaluation_id, f["kind"], turn_ids.get(f["turn_no"]), f["content"], i, f["excerpt"],
                        f["evidence_turn_nos"],
                        # Jenis lain: penjelasan sudah ada di content.
                        f.get("explanation") if f["kind"] == "alternative_response" else None,
                    )
                    for i, f in enumerate(result.feedback)
                ],
            )
        await conn.execute(
            """
            UPDATE evaluations
            SET status = 'completed', completed_at = now(), error_message = NULL,
                model_version = $2, assessed_duration_seconds = $3, limitation_notes = $4, coding_debug = $5::jsonb
            WHERE id = $1
            """,
            evaluation_id,
            result.model_version,
            assessed_duration_seconds,
            "\n".join(result.limitation_notes) or None,
            json.dumps(result.debug, ensure_ascii=False),
        )


async def mark_evaluation_failed(
    conn: asyncpg.Connection, evaluation_id: int, message: str, debug: dict[str, Any] | None = None
) -> None:
    await conn.execute(
        """
        UPDATE evaluations
        SET status = 'failed', error_message = $2, coding_debug = COALESCE($3::jsonb, coding_debug)
        WHERE id = $1
        """,
        evaluation_id,
        message[:2000],
        json.dumps(debug, ensure_ascii=False) if debug else None,
    )


async def get_evaluation_details(conn: asyncpg.Connection, evaluation_id: int) -> dict[str, list[dict[str, Any]]]:
    codes = await conn.fetch(
        """
        SELECT t.turn_no, m.unit_no, m.code::text AS code, m.excerpt, m.reason, m.uncertainty_note
        FROM miti_codes m JOIN turns t ON t.id = m.turn_id
        WHERE m.evaluation_id = $1
        ORDER BY t.turn_no, m.unit_no
        """,
        evaluation_id,
    )
    globals_ = await conn.fetch(
        "SELECT dimension::text AS dimension, score, reason, evidence_turn_nos FROM miti_globals WHERE evaluation_id = $1",
        evaluation_id,
    )
    processes = await conn.fetch(
        """
        SELECT process::text AS process, start_turn_no, end_turn_no, excerpt, reason
        FROM process_observations WHERE evaluation_id = $1 ORDER BY id
        """,
        evaluation_id,
    )
    feedback = await conn.fetch(
        """
        SELECT f.kind::text AS kind, t.turn_no, f.excerpt, f.content, f.explanation, f.evidence_turn_nos
        FROM feedback_items f LEFT JOIN turns t ON t.id = f.turn_id
        WHERE f.evaluation_id = $1 ORDER BY f.sort_order
        """,
        evaluation_id,
    )
    return {
        "codes": [dict(r) for r in codes],
        "globals": [dict(r) for r in globals_],
        "processes": [dict(r) for r in processes],
        "feedback": [dict(r) for r in feedback],
    }


async def lecturer_manages_session(conn: asyncpg.Connection, session_id: int, lecturer_id: int) -> bool:
    """Dosen hanya boleh melihat sesi kelas yang dikelolanya (view v_sessions_for_lecturer)."""
    return bool(
        await conn.fetchval(
            # View belum menyaring classes.deleted_at, jadi disaring di sini.
            """
            SELECT EXISTS (
                SELECT 1 FROM v_sessions_for_lecturer v
                JOIN classes c ON c.id = v.class_id AND c.deleted_at IS NULL
                WHERE v.id = $1 AND v.lecturer_id = $2
            )
            """,
            session_id,
            lecturer_id,
        )
    )
