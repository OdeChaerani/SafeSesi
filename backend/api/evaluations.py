from __future__ import annotations

import logging
from typing import Any
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.deps import get_current_user, get_db
from core.config import get_settings
from repositories.evaluations import (
    claim_evaluation,
    get_evaluation_by_session,
    get_evaluation_details,
    lecturer_manages_session,
    mark_evaluation_failed,
    save_evaluation_results,
)
from repositories.sessions import get_session_by_id
from repositories.turns import get_session_turns
from schemas.evaluation import GLOBAL_DIMENSIONS, MITI_CODES
from services.evaluation.miti_evaluator import (
    GUIDELINE_VERSION,
    EvaluationInput,
    agents_to_run,
    model_version_string,
    run_evaluation,
)
from services.evaluation.summary import summary_measures
from services.llm.gemini_client import evaluator_llm_configs
from services.simulation.turn_lock import spawn_background

logger = logging.getLogger("safesesi.evaluation")

router = APIRouter(prefix="/sessions", tags=["evaluations"])


def build_input(session: dict[str, Any], turns: list[dict[str, Any]]) -> EvaluationInput:
    """Hanya transkrip, target perubahan, dan ringkasan publik yang dikirim ke evaluator."""
    snapshot = session.get("scenario_snapshot") or {}
    return EvaluationInput(
        turns=[{"turn_no": t["turn_no"], "speaker": t["speaker"], "content": t["content"]} for t in turns],
        change_target=(snapshot.get("scenario") or {}).get("change_target") or "",
        initial_summary=(snapshot.get("case") or {}).get("initial_summary"),
        duration_seconds=session.get("duration_seconds"),
        label=f"sesi {session['id']}",
    )


async def run_evaluation_job(pool: asyncpg.Pool, session: dict[str, Any], evaluation_id: int) -> None:
    """Tugas background: koneksi DB tidak ditahan selama agen LLM berjalan."""
    try:
        async with pool.acquire() as conn:
            turns = await get_session_turns(conn, session["id"])
        result = await run_evaluation(build_input(session, turns))
        async with pool.acquire() as conn:
            await save_evaluation_results(
                conn, evaluation_id, result, {t["turn_no"]: t["id"] for t in turns}, session.get("duration_seconds")
            )
        logger.info("Evaluasi sesi %s selesai (evaluasi %s).", session["id"], evaluation_id)
    except Exception as exc:  # status 'failed' + pesan; tidak ada hasil parsial yang tersimpan
        logger.exception("Evaluasi sesi %s gagal: %s", session["id"], exc)
        message = getattr(exc, "message", None) or f"{type(exc).__name__}: {exc}"
        async with pool.acquire() as conn:
            await mark_evaluation_failed(conn, evaluation_id, message)


def status_payload(evaluation: dict[str, Any]) -> dict[str, Any]:
    return {
        "evaluation_id": evaluation["id"],
        "session_id": evaluation["session_id"],
        "status": evaluation["status"],
        "error_message": evaluation.get("error_message"),
        "guideline_version": evaluation["guideline_version"],
        "model_version": evaluation.get("model_version"),
        "assessed_duration_seconds": evaluation.get("assessed_duration_seconds"),
        "limitation_notes": [n for n in (evaluation.get("limitation_notes") or "").split("\n") if n],
        "completed_at": evaluation.get("completed_at"),
    }


async def _load_session(conn: asyncpg.Connection, session_id: int) -> dict[str, Any]:
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sesi {session_id} tidak ditemukan.")
    return session


@router.post("/{session_id}/evaluation")
async def start_evaluation(
    session_id: int,
    request: Request,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Mulai evaluasi sesi milik pemanggil yang sudah selesai; evaluasi yang ada dikembalikan."""
    session = await _load_session(conn, session_id)
    if session["student_id"] != user.get("id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evaluasi hanya dapat dimulai oleh pemilik sesi.")
    if session["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sesi belum selesai; akhiri sesi sebelum dievaluasi.")

    settings = get_settings()
    agents, _ = agents_to_run(session.get("duration_seconds"))
    evaluation, should_run = await claim_evaluation(
        conn, session_id, GUIDELINE_VERSION, model_version_string(evaluator_llm_configs(settings), agents)
    )
    if should_run:
        spawn_background(run_evaluation_job(request.app.state.db_pool, session, evaluation["id"]), name=f"evaluation-{session_id}")
        response.status_code = status.HTTP_202_ACCEPTED
    return status_payload(evaluation)


async def _authorize_view(conn: asyncpg.Connection, session: dict[str, Any], user: dict[str, Any]) -> bool:
    """Mahasiswa: sesi sendiri. Dosen: sesi kelas yang dikelolanya. Admin: semua. Return: is_reviewer."""
    role = user.get("role")
    if role == "admin":
        return True
    if role == "lecturer":
        if session.get("class_id") and await lecturer_manages_session(conn, session["id"], user["id"]):
            return True
    elif session["student_id"] == user.get("id"):
        return False
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Anda tidak memiliki izin melihat evaluasi sesi ini.")


@router.get("/{session_id}/evaluation")
async def get_evaluation(
    session_id: int,
    conn: asyncpg.Connection = Depends(get_db),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    session = await _load_session(conn, session_id)
    is_reviewer = await _authorize_view(conn, session, user)
    evaluation = await get_evaluation_by_session(conn, session_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluasi untuk sesi ini belum dibuat.")
    payload = status_payload(evaluation)
    if evaluation["status"] != "completed":
        return payload

    details = await get_evaluation_details(conn, evaluation["id"])
    frequencies = {c: 0 for c in MITI_CODES}
    codes_by_turn: dict[int, list[dict[str, Any]]] = {}
    for c in details["codes"]:
        frequencies[c["code"]] += 1
        codes_by_turn.setdefault(c["turn_no"], []).append(
            {k: c[k] for k in ("unit_no", "code", "excerpt", "reason", "uncertainty_note")}
        )
    globals_by_dim = {g["dimension"]: g for g in details["globals"]}
    global_scores = {d: globals_by_dim[d]["score"] for d in GLOBAL_DIMENSIONS if d in globals_by_dim} or None
    payload.update(
        codes_by_turn=[{"turn_no": n, "codes": codes} for n, codes in sorted(codes_by_turn.items())],
        frequencies=frequencies,
        global_scores=[globals_by_dim[d] for d in GLOBAL_DIMENSIONS if d in globals_by_dim],
        summary_measures=summary_measures(frequencies, global_scores),
        processes=[{**p, "evidence_found": p["start_turn_no"] is not None} for p in details["processes"]],
        feedback=details["feedback"],
    )
    if is_reviewer:
        payload["coding_debug"] = evaluation.get("coding_debug")
    return payload
