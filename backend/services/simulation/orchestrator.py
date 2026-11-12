from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
import asyncpg
from core.config import get_settings
from core.errors import LLMServiceError
from repositories.client_state import get_latest_client_state, save_client_state
from repositories.topics import get_latest_topic_notes, save_topic_note
from repositories.turns import get_next_turn_no, get_session_turns, save_turn
from schemas.client_state import ClientState
from schemas.session import TurnResponse
from services.simulation.intent import classify_greeting, generate_greeting_response
from services.simulation.notes_updater import update_topic_notes_llm
from services.simulation.responder import generate_client_response_llm
from services.simulation.state_updater import update_client_state_llm

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


async def process_turn(
    conn: asyncpg.Connection,
    session: dict[str, Any],
    counselor_utterance: str,
    start_ms: int = 0,
    end_ms: int = 0,
) -> TurnResponse:
    """Mengorkestrasi satu siklus giliran dialog konseling:

    1. Membaca konteks sesi, snapshot skenario, state klien terkini, dan topik.
    2. Deteksi shortcut sapaan (greeting bypass).
    3. Peran A: State Updater (evaluasi respons konselor -> ClientState).
    4. Peran B: Client Responder (pembatasan kode hidden facts -> ucapan klien).
    5. Persistensi atomik giliran konselor, giliran klien, dan client_state_log.
    6. Peran C: Notes Updater (inline / background).
    7. Mengembalikan TurnResponse tanpa membocorkan internal state (kecuali debug).
    """
    t_turn_start = time.perf_counter()
    session_id = session["id"]
    settings = get_settings()

    # 1. Ekstraksi Snapshot Skenario yang Dibekukan
    t_fetch_start = time.perf_counter()
    snapshot = session.get("scenario_snapshot", {})
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)

    persona = snapshot.get("persona", {})
    case_data = snapshot.get("case", {})
    initial_state = snapshot.get("initial_state", {})
    hidden_facts = snapshot.get("hidden_facts", [])

    # 2. Ambil Kondisi Klien Terkini dan Catatan Topik
    latest_state = await get_latest_client_state(conn, session_id)
    if not latest_state:
        latest_state = initial_state

    latest_topic_notes = await get_latest_topic_notes(conn, session_id)

    # 3. Ambil Riwayat Percakapan (Sesi Aktif + Parent Sesi jika Mode Continue)
    current_turns = await get_session_turns(conn, session_id)
    parent_session_id = session.get("parent_session_id")
    if parent_session_id:
        parent_turns = await get_session_turns(conn, parent_session_id)
        transcript_history = parent_turns + current_turns
    else:
        transcript_history = current_turns

    t_fetch = time.perf_counter() - t_fetch_start

    # 4. Shortcut Sapaan (Greeting Bypass - hanya di turn pertama jika diaktifkan)
    if (
        settings.GREETING_SHORTCUT_ENABLED
        and not transcript_history
        and classify_greeting(counselor_utterance)
    ):
        client_reply = generate_greeting_response(persona.get("name", "Klien"))

        async with conn.transaction():
            c_turn_no = await get_next_turn_no(conn, session_id)
            c_turn_id = await save_turn(
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
            # Salin state sebelumnya untuk giliran klien sapaan
            await save_client_state(
                conn, session_id=session_id, turn_id=cl_turn_id, state=latest_state
            )

        t_total = time.perf_counter() - t_turn_start
        logger.info(
            "⏱️ [Sesi #%s Turn #%d] Total: %.2fs (Shortcut Sapaan) -> 🗣️ Klien: \"%s\"",
            session_id,
            cl_turn_no,
            t_total,
            client_reply,
        )

        internal_st = (
            ClientState.model_validate(latest_state)
            if settings.DEBUG_INCLUDE_INTERNAL
            else None
        )
        return TurnResponse(
            turn_no=cl_turn_no,
            content=client_reply,
            internal_state=internal_st,
        )

    # 5. Pemrosesan Substantif: Peran A (State Updater)
    t_state_start = time.perf_counter()
    new_state = await update_client_state_llm(
        counselor_utterance=counselor_utterance,
        current_state=latest_state,
        persona=persona,
        case_data=case_data,
        transcript_history=transcript_history,
        topic_notes=latest_topic_notes,
    )
    t_state = time.perf_counter() - t_state_start

    # 6. Pemrosesan Substantif: Peran B (Client Responder)
    t_resp_start = time.perf_counter()
    client_reply = await generate_client_response_llm(
        persona=persona,
        case_data=case_data,
        new_state=new_state,
        topic_notes=latest_topic_notes,
        transcript_history=transcript_history,
        counselor_utterance=counselor_utterance,
        hidden_facts=hidden_facts,
    )
    t_resp = time.perf_counter() - t_resp_start

    # 7. Persistensi Atomik Transaksi Turn Konselor + Turn Klien + State Klien
    t_db_start = time.perf_counter()
    async with conn.transaction():
        c_turn_no = await get_next_turn_no(conn, session_id)
        c_turn_id = await save_turn(
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
        await save_client_state(
            conn,
            session_id=session_id,
            turn_id=cl_turn_id,
            state=new_state.model_dump(),
        )
    t_db = time.perf_counter() - t_db_start

    # 8. Peran C: Notes Updater (Pembaruan Catatan Perkembangan Topik)
    t_notes = 0.0
    if settings.NOTES_UPDATE_MODE == "inline":
        t_notes_start = time.perf_counter()
        try:
            updated_topics = await update_topic_notes_llm(
                current_topic_notes=latest_topic_notes,
                counselor_utterance=counselor_utterance,
                actual_client_response=client_reply,
            )
            # Petakan topic_name ke session_topic_id
            name_to_id = {
                t["topic_name"].strip().lower(): t["session_topic_id"]
                for t in latest_topic_notes
            }
            for ut in updated_topics:
                matched_id = name_to_id.get(ut.topic_name.strip().lower())
                if matched_id:
                    await save_topic_note(
                        conn,
                        session_topic_id=matched_id,
                        turn_id=cl_turn_id,
                        description=ut.description,
                    )
            t_notes = time.perf_counter() - t_notes_start
        except Exception as exc:
            t_notes = time.perf_counter() - t_notes_start
            logger.warning("Pembaruan catatan topik Peran C inline gagal (non-fatal): %s", exc)

    t_total = time.perf_counter() - t_turn_start
    reply_snippet = client_reply.replace("\n", " ")
    if len(reply_snippet) > 80:
        reply_snippet = reply_snippet[:80] + "..."

    logger.info(
        "⏱️ [Sesi #%s Turn #%d] Total: %.2fs (State: %.2fs | Klien: %.2fs | Notes: %.2fs | DB: %dms) -> 🗣️ Klien: \"%s\"",
        session_id,
        cl_turn_no,
        t_total,
        t_state,
        t_resp,
        t_notes,
        int((t_fetch + t_db) * 1000),
        reply_snippet,
    )

    internal_st = new_state if settings.DEBUG_INCLUDE_INTERNAL else None
    return TurnResponse(
        turn_no=cl_turn_no,
        content=client_reply,
        internal_state=internal_st,
    )
