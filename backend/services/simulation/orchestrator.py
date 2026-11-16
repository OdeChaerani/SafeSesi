from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Coroutine
import asyncpg
from core.config import get_settings
from core.errors import LLMServiceError
from repositories.client_state import (
    get_latest_client_state,
    save_client_state,
    update_client_state_details,
)
from repositories.topics import get_latest_topic_notes, save_topic_note
from repositories.turns import get_next_turn_no, get_session_turns, save_turn
from schemas.client_state import ClientState, StateDetail
from schemas.session import TurnResponse
from services.llm.gemini_client import track_usage
from services.simulation.intent import classify_greeting, generate_greeting_response
from services.simulation.notes_updater import update_topic_notes_llm
from services.simulation.responder import generate_client_response_llm
from services.simulation.state_updater import (
    provisional_state,
    update_client_state_decision,
    update_client_state_detail,
    update_client_state_llm,
)
from services.simulation.timing import TurnTimings
from services.simulation.turn_lock import DbTurnLock, NullTurnLock, spawn_background

logger = logging.getLogger("safesesi.simulation.orchestrator")

# Registry lock per sesi untuk serialisasi pemrosesan turn dalam satu sesi
_SESSION_LOCKS: dict[int, asyncio.Lock] = {}
_GLOBAL_LOCK = asyncio.Lock()


async def get_session_lock(session_id: int) -> asyncio.Lock:
    """Mengembalikan asyncio.Lock untuk session_id guna mencegah pemrosesan turn konkuren dalam sesi yang sama."""
    async with _GLOBAL_LOCK:
        if session_id not in _SESSION_LOCKS:
            _SESSION_LOCKS[session_id] = asyncio.Lock()
        return _SESSION_LOCKS[session_id]


async def _save_turn_pair(
    conn: asyncpg.Connection,
    session_id: int,
    counselor_utterance: str,
    client_reply: str,
    state: dict[str, Any],
    start_ms: int,
    end_ms: int,
) -> tuple[int, int, int]:
    """Persistensi atomik: turn konselor + turn klien + client_state_log.

    Mengembalikan (turn_no klien, turn_id klien, id baris client_state_log).
    """
    async with conn.transaction():
        c_turn_no = await get_next_turn_no(conn, session_id)
        await save_turn(
            conn,
            session_id=session_id,
            turn_no=c_turn_no,
            speaker="counselor",
            content=counselor_utterance,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        cl_turn_no = c_turn_no + 1
        cl_turn_id = await save_turn(
            conn,
            session_id=session_id,
            turn_no=cl_turn_no,
            speaker="client",
            content=client_reply,
            start_ms=0,
            end_ms=0,
        )
        state_id = await save_client_state(conn, session_id=session_id, turn_id=cl_turn_id, state=state)
    return cl_turn_no, cl_turn_id, state_id


async def _run_notes_updater(
    conn: asyncpg.Connection,
    latest_topic_notes: list[dict[str, Any]],
    counselor_utterance: str,
    client_reply: str,
    client_turn_id: int,
) -> None:
    """Peran C: memperbarui catatan topik dan menyimpannya ke topic_notes_log."""
    updated_topics = await update_topic_notes_llm(
        current_topic_notes=latest_topic_notes,
        counselor_utterance=counselor_utterance,
        actual_client_response=client_reply,
    )
    await _save_notes(conn, latest_topic_notes, updated_topics, client_turn_id)


async def _save_notes(
    conn: asyncpg.Connection,
    latest_topic_notes: list[dict[str, Any]],
    updated_topics: list[Any],
    client_turn_id: int,
) -> None:
    name_to_id = {
        t["topic_name"].strip().lower(): t["session_topic_id"] for t in latest_topic_notes
    }
    for ut in updated_topics:
        matched_id = name_to_id.get(ut.topic_name.strip().lower())
        if matched_id:
            await save_topic_note(
                conn,
                session_topic_id=matched_id,
                turn_id=client_turn_id,
                description=ut.description,
            )


async def _post_response_in_background(
    turn_lock: DbTurnLock | NullTurnLock,
    timings: TurnTimings,
    session_id: int,
    turn_no: int,
    latest_topic_notes: list[dict[str, Any]],
    counselor_utterance: str,
    client_reply: str,
    client_turn_id: int,
    timeout_s: float,
    state_mode: str,
    detail_llm: Coroutine[Any, Any, StateDetail] | None = None,
    state_id: int | None = None,
) -> None:
    """Tahap setelah respons terkirim: Peran C, dan State Detail Agent pada mode split.

    Panggilan LLM berjalan bersamaan; penulisan DB berurutan di koneksi lock, masing-masing di
    savepoint sendiri, sehingga kegagalan satu tahap tidak membatalkan tahap lain. Gagal/timeout
    tidak memengaruhi respons: error dicatat, dan lock tetap dilepas agar giliran berikutnya jalan.
    State Detail Agent gagal -> baris state tetap berisi keputusan + salinan state sebelumnya.
    """
    conn = turn_lock.conn

    async def timed(stage: str, coro: Coroutine[Any, Any, Any]) -> Any:
        with timings.stage(stage):
            return await asyncio.wait_for(coro, timeout=timeout_s)

    # (tahap timing, kunci status, label log, coroutine LLM, penulis DB)
    jobs: list[tuple[str, str, str, Coroutine[Any, Any, Any], Callable[[Any], Awaitable[None]]]] = [
        (
            "role_c",
            "notes_status",
            "Peran C",
            update_topic_notes_llm(
                current_topic_notes=latest_topic_notes,
                counselor_utterance=counselor_utterance,
                actual_client_response=client_reply,
            ),
            lambda topics: _save_notes(conn, latest_topic_notes, topics, client_turn_id),
        )
    ]
    if detail_llm is not None:
        jobs.append(
            (
                "state_detail",
                "detail_status",
                "State Detail Agent",
                detail_llm,
                lambda detail: update_client_state_details(conn, state_id, detail.model_dump()),
            )
        )

    statuses: dict[str, str] = {}
    try:
        results = await asyncio.gather(
            *(timed(stage, coro) for stage, _, _, coro, _ in jobs), return_exceptions=True
        )
        for (_, key, label, _, write), result in zip(jobs, results):
            status = "ok"
            try:
                if isinstance(result, BaseException):
                    raise result
                async with conn.transaction():  # savepoint di dalam transaksi lock
                    await write(result)
            except Exception as exc:
                status = "timeout" if isinstance(exc, asyncio.TimeoutError) else "error"
                logger.error(
                    "%s background gagal (sesi #%s turn #%s, %s): %r",
                    label,
                    session_id,
                    turn_no,
                    status,
                    exc,
                )
            statuses[key] = status
    finally:
        try:
            await turn_lock.release(commit="ok" in statuses.values())
        except Exception:
            logger.exception("Gagal melepas lock giliran sesi #%s", session_id)
        timings.emit(
            session_id,
            turn_no,
            path="substantive",
            state_update_mode=state_mode,
            notes_mode="background",
            **statuses,
        )


async def process_turn(
    conn: asyncpg.Connection,
    session: dict[str, Any],
    counselor_utterance: str,
    start_ms: int = 0,
    end_ms: int = 0,
    turn_lock: DbTurnLock | NullTurnLock | None = None,
    lock_wait_ms: float | None = None,
) -> TurnResponse:
    """Memproses satu giliran. Mengambil alih turn_lock: lock selalu dilepas di sini,
    atau diserahkan ke tugas Peran C background yang melepasnya setelah selesai.
    lock_wait_ms: lama menunggu lock giliran sebelumnya (dicatat di log timing).
    """
    lock = turn_lock or NullTurnLock()
    handed_off = False
    succeeded = False
    try:
        response, handed_off = await _process_turn_locked(
            conn, session, counselor_utterance, start_ms, end_ms, lock, lock_wait_ms
        )
        succeeded = True
        return response
    finally:
        if not handed_off:
            await lock.release(commit=succeeded)


async def _process_turn_locked(
    conn: asyncpg.Connection,
    session: dict[str, Any],
    counselor_utterance: str,
    start_ms: int,
    end_ms: int,
    turn_lock: DbTurnLock | NullTurnLock,
    lock_wait_ms: float | None = None,
) -> tuple[TurnResponse, bool]:
    """Mengorkestrasi satu siklus giliran dialog konseling:

    1. Membaca konteks sesi, snapshot skenario, state klien terkini, dan topik.
    2. Deteksi shortcut sapaan (greeting bypass).
    3. Peran A: State Updater (evaluasi respons konselor -> ClientState).
    4. Peran B: Client Responder (pembatasan kode hidden facts -> ucapan klien).
    5. Persistensi atomik giliran konselor, giliran klien, dan client_state_log.
    6. Peran C: Notes Updater (background setelah respons, atau inline).
    7. Mengembalikan TurnResponse tanpa membocorkan internal state (kecuali debug).

    Dipanggil sambil memegang lock giliran sesi. Mengembalikan (respons, lock_diserahkan).
    Durasi tiap tahap dicatat sebagai satu baris JSON per giliran (logger safesesi.timing).
    """
    timings = TurnTimings()
    track_usage(timings.tokens)
    if lock_wait_ms is not None:
        timings.stages["lock_wait"] = lock_wait_ms
    session_id = session["id"]
    settings = get_settings()

    # 1-3. Muat snapshot, state terkini, catatan topik, dan riwayat percakapan
    with timings.stage("load"):
        snapshot = session.get("scenario_snapshot", {})
        if isinstance(snapshot, str):
            snapshot = json.loads(snapshot)

        persona = snapshot.get("persona", {})
        case_data = snapshot.get("case", {})
        initial_state = snapshot.get("initial_state", {})
        hidden_facts = snapshot.get("hidden_facts", [])

        latest_state = await get_latest_client_state(conn, session_id)
        if not latest_state:
            latest_state = initial_state

        latest_topic_notes = await get_latest_topic_notes(conn, session_id)

        # Riwayat sesi aktif + sesi induk jika mode continue
        current_turns = await get_session_turns(conn, session_id)
        parent_session_id = session.get("parent_session_id")
        if parent_session_id:
            parent_turns = await get_session_turns(conn, parent_session_id)
            transcript_history = parent_turns + current_turns
        else:
            transcript_history = current_turns

    # 4. Shortcut Sapaan (Greeting Bypass - hanya di turn pertama jika diaktifkan)
    if (
        settings.GREETING_SHORTCUT_ENABLED
        and not transcript_history
        and classify_greeting(counselor_utterance)
    ):
        client_reply = generate_greeting_response(persona.get("name", "Klien"))
        with timings.stage("save"):
            # Salin state sebelumnya untuk giliran klien sapaan
            cl_turn_no, _, _ = await _save_turn_pair(
                conn, session_id, counselor_utterance, client_reply, latest_state, start_ms, end_ms
            )
        timings.emit(session_id, cl_turn_no, path="greeting_shortcut")

        internal_st = (
            ClientState.model_validate(latest_state)
            if settings.DEBUG_INCLUDE_INTERNAL
            else None
        )
        response = TurnResponse(turn_no=cl_turn_no, content=client_reply, internal_state=internal_st)
        return response, False

    # 5. Peran A. combined: State Updater penuh. split: State Decision Agent saja (keputusan
    # yang dibutuhkan Peran B); field deskriptif diisi State Detail Agent setelah respons.
    split = settings.STATE_UPDATE_MODE == "split"
    state_mode = "split" if split else "combined"
    if split:
        with timings.stage("state_decision"):
            decision = await update_client_state_decision(
                counselor_utterance=counselor_utterance,
                current_state=latest_state,
                persona=persona,
                case_data=case_data,
                transcript_history=transcript_history,
            )
        new_state = provisional_state(latest_state, decision)
    else:
        with timings.stage("role_a"):
            new_state = await update_client_state_llm(
                counselor_utterance=counselor_utterance,
                current_state=latest_state,
                persona=persona,
                case_data=case_data,
                transcript_history=transcript_history,
                topic_notes=latest_topic_notes,
            )

    # 6. Peran B (Client Responder)
    with timings.stage("role_b"):
        client_reply = await generate_client_response_llm(
            persona=persona,
            case_data=case_data,
            new_state=new_state,
            topic_notes=latest_topic_notes,
            transcript_history=transcript_history,
            counselor_utterance=counselor_utterance,
            hidden_facts=hidden_facts,
            decision_only=split,
        )

    def detail_llm() -> Coroutine[Any, Any, StateDetail]:
        return update_client_state_detail(
            counselor_utterance=counselor_utterance,
            client_reply=client_reply,
            previous_state=latest_state,
            decided_state=new_state,
            persona=persona,
            case_data=case_data,
            transcript_history=transcript_history,
        )

    # 7. Persistensi atomik turn konselor + turn klien + state klien
    with timings.stage("save"):
        cl_turn_no, cl_turn_id, state_id = await _save_turn_pair(
            conn,
            session_id,
            counselor_utterance,
            client_reply,
            new_state.model_dump(),
            start_ms,
            end_ms,
        )

    internal_st = new_state if settings.DEBUG_INCLUDE_INTERNAL else None
    response = TurnResponse(turn_no=cl_turn_no, content=client_reply, internal_state=internal_st)

    # 8. Peran C (Notes Updater), dan State Detail Agent pada mode split. Background hanya jika
    # ada koneksi lock khusus: tugas background tidak boleh memakai koneksi request yang
    # dikembalikan ke pool setelah respons.
    if settings.NOTES_UPDATE_MODE == "background" and turn_lock.conn is not None:
        timings.mark_response_ready()
        spawn_background(
            _post_response_in_background(
                turn_lock,
                timings,
                session_id,
                cl_turn_no,
                latest_topic_notes,
                counselor_utterance,
                client_reply,
                cl_turn_id,
                settings.NOTES_TIMEOUT_S,
                state_mode,
                detail_llm() if split else None,
                state_id,
            ),
            name=f"notes-session-{session_id}-turn-{cl_turn_no}",
        )
        return response, True

    extra: dict[str, Any] = {}
    if split:
        # Tanpa koneksi lock: State Detail Agent inline sebelum respons, sama seperti Peran C.
        extra["detail_status"] = "ok"
        with timings.stage("state_detail"):
            try:
                detail = await detail_llm()
                await update_client_state_details(turn_lock.conn or conn, state_id, detail.model_dump())
            except Exception as exc:
                extra["detail_status"] = "error"
                logger.warning("State Detail Agent inline gagal (non-fatal): %s", exc)

    notes_status = "ok"
    with timings.stage("role_c"):
        try:
            await _run_notes_updater(
                turn_lock.conn or conn,
                latest_topic_notes,
                counselor_utterance,
                client_reply,
                cl_turn_id,
            )
        except Exception as exc:
            notes_status = "error"
            logger.warning("Pembaruan catatan topik Peran C inline gagal (non-fatal): %s", exc)

    timings.emit(
        session_id,
        cl_turn_no,
        path="substantive",
        state_update_mode=state_mode,
        notes_mode="inline",
        notes_status=notes_status,
        **extra,
    )
    return response, False
