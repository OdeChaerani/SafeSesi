from __future__ import annotations

import time
from typing import Any
import asyncpg
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import ensure_can_view_session, ensure_session_owner, get_current_user, get_db, is_reviewer, require_role
from core.errors import LLMServiceError
from repositories.client_state import get_latest_client_state, save_client_state
from repositories.scenarios import (
    build_scenario_snapshot,
    get_scenario_by_id,
    validate_class_access,
)
from repositories.classes import get_class
from repositories.evaluations import get_evaluation_by_session
from repositories.sessions import create_session, end_session, get_session_by_id, list_student_sessions
from repositories.topics import (
    copy_topic_notes_from_parent,
    create_session_topics_from_snapshot,
    get_latest_topic_notes,
    save_topic_note,
)
from repositories.turns import get_session_turns, get_timeline
from schemas.scenario import PublicScenarioInfo
from schemas.student import SessionHistoryResponse, TranscriptResponse
from schemas.session import (
    CreateSessionRequest,
    CreateTurnRequest,
    EndSessionRequest,
    EndSessionResponse,
    SessionResponse,
    TurnResponse,
)
from services.simulation.orchestrator import get_session_lock, process_turn
from services.simulation.turn_lock import (
    DbTurnLock,
    NullTurnLock,
    TurnLockTimeout,
    acquire_turn_lock,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def student_visible_topics(topic_notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Topik yang boleh dilihat mahasiswa: hanya yang deskripsi terakhirnya tidak kosong.

    Topik kosong dibuang seluruhnya karena namanya bisa membocorkan judul fakta tersembunyi.
    """
    return [
        {"name": note.get("topic_name"), "description": note.get("description")}
        for note in topic_notes
        if (note.get("description") or "").strip()
    ]


async def topics_for_viewer(
    conn: asyncpg.Connection, session_id: int, user: dict[str, Any]
) -> list[dict[str, Any]]:
    notes = await get_latest_topic_notes(conn, session_id)
    return notes if is_reviewer(user) else student_visible_topics(notes)


async def _acquire_turn_lock_or_409(session_id: int) -> DbTurnLock | NullTurnLock:
    try:
        return await acquire_turn_lock(session_id)
    except TurnLockTimeout as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Giliran sebelumnya masih diproses. Silakan coba lagi sebentar lagi.",
        ) from exc


def to_public_session(session: dict[str, Any]) -> dict[str, Any]:
    """Data sesi untuk frontend: scenario_snapshot diganti ringkasan publik skenario."""
    public = {k: v for k, v in session.items() if k != "scenario_snapshot"}
    public["scenario"] = PublicScenarioInfo.from_snapshot(
        session.get("scenario_snapshot") or {}, scenario_id=session.get("scenario_id")
    ).model_dump()
    return public


async def _load_source_session(
    conn: asyncpg.Connection,
    session_id: int,
    user: dict[str, Any],
    scenario_id: int,
    *,
    need_completed: bool,
    label: str,
) -> dict[str, Any]:
    """Sesi sumber untuk melanjutkan/mengulang: harus ada, milik mahasiswa itu, skenario sama
    (dan sudah selesai untuk melanjutkan)."""
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi sebelumnya tidak ditemukan.")
    if session["student_id"] != user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{label} harus milik Anda sendiri.")
    if session["scenario_id"] != scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skenario pada sesi lanjutan harus identik dengan sesi sebelumnya.",
        )
    if need_completed and session["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi sebelumnya belum selesai. Akhiri sesi itu terlebih dahulu sebelum melanjutkannya.",
        )
    return session


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(
    payload: CreateSessionRequest,
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Membuat sesi simulasi konseling baru (new, repeat, atau continue) dalam SATU transaksi atomik."""
    async with conn.transaction():
        # 1. Validasi Keberadaan Skenario
        scenario = await get_scenario_by_id(conn, payload.scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skenario dengan ID {payload.scenario_id} tidak ditemukan.",
            )

        # 1a. Sesi sumber: induk (continue) atau sesi asal (repeat). class_id selalu mengikuti sesi
        # sumber, bukan permintaan, supaya latihan kelas tidak berpindah jenis diam-diam.
        source: dict[str, Any] | None = None
        if payload.mode == "continue":
            if not payload.parent_session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="parent_session_id wajib disertakan untuk mode continue.",
                )
            source = await _load_source_session(
                conn, payload.parent_session_id, user, payload.scenario_id, need_completed=True, label="Sesi lanjutan"
            )
        elif payload.mode == "repeat" and payload.repeat_of_session_id:
            source = await _load_source_session(
                conn, payload.repeat_of_session_id, user, payload.scenario_id, need_completed=False, label="Sesi yang diulang"
            )
        if source is not None:
            class_id = source["class_id"]
            if payload.class_id is not None and payload.class_id != class_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="class_id harus sama dengan sesi sebelumnya.",
                )
        else:
            class_id = payload.class_id

        # 1b. Validasi akses: latihan mandiri hanya skenario katalog; latihan kelas hanya untuk anggota
        # aktif kelas dengan skenario yang ditetapkan ke kelas itu (juga saat mengulang/melanjutkan).
        if class_id is None:
            if scenario["visibility"] != "catalog":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Latihan mandiri hanya diizinkan untuk skenario yang tersedia di katalog umum.",
                )
        elif not await validate_class_access(conn, payload.scenario_id, class_id, user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak memiliki izin untuk mengakses skenario pada kelas ini.",
            )

        # 2. Snapshot skenario. Sesi lanjutan memakai snapshot sesi induk (versi skenario saat sesi
        # pertama), jadi perubahan skenario oleh dosen hanya berlaku untuk sesi baru.
        snapshot = source["scenario_snapshot"] if payload.mode == "continue" else await build_scenario_snapshot(conn, payload.scenario_id)
        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gagal menyusun snapshot skenario dari database.",
            )

        # 3. Buat Rekaman Sesi Baru
        parent_id = source["id"] if payload.mode == "continue" and source else None
        session_record = await create_session(
            conn=conn,
            student_id=user["id"],
            scenario_id=payload.scenario_id,
            scenario_snapshot=snapshot,
            class_id=class_id,
            parent_session_id=parent_id,
        )
        new_session_id = session_record["id"]

        # 4. Inisialisasi Topik Pembahasan (session_topics)
        created_topics = await create_session_topics_from_snapshot(
            conn, new_session_id, snapshot
        )

        # 5. Isi State Awal dan Catatan Topik Awal
        if payload.mode in ("new", "repeat"):
            initial_state = snapshot["initial_state"]
            await save_client_state(conn, new_session_id, turn_id=None, state=initial_state)
            for topic in created_topics:
                await save_topic_note(conn, topic["id"], turn_id=None, description="")
        elif payload.mode == "continue":
            assert payload.parent_session_id is not None
            # Salin state akhir milik parent session
            parent_latest_state = await get_latest_client_state(conn, payload.parent_session_id)
            if not parent_latest_state:
                parent_latest_state = snapshot["initial_state"]
            await save_client_state(conn, new_session_id, turn_id=None, state=parent_latest_state)

            # Salin catatan topik terakhir dari parent session
            await copy_topic_notes_from_parent(conn, payload.parent_session_id, new_session_id)

        return to_public_session(session_record)


@router.get("", response_model=SessionHistoryResponse)
async def list_my_sessions(
    kind: Literal["all", "independent", "class"] = Query(default="all", alias="type", description="Jenis latihan"),
    scenario_id: int | None = Query(default=None, description="Saring berdasarkan skenario"),
    session_status: Literal["completed", "in_progress"] | None = Query(default=None, alias="status", description="Saring status sesi"),
    limit: int = Query(default=100, ge=1, le=100, description="Jumlah maksimum baris (tanpa paginasi)"),
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Riwayat sesi milik mahasiswa yang sedang masuk, terbaru dulu, beserta hitungan untuk beranda."""
    return await list_student_sessions(
        conn, user["id"], kind=kind, scenario_id=scenario_id, status=session_status, limit=limit
    )


@router.get("/{session_id}/transcript", response_model=TranscriptResponse)
async def get_session_transcript(
    session_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Transkrip sesi: pembicara dan isi tiap giliran saja. Client State dan data internal tidak dikirim.

    Aturan akses sama dengan detail sesi: mahasiswa pemilik, atau dosen kelas yang mengelola sesi itu.
    """
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi dengan ID {session_id} tidak ditemukan.",
        )
    await ensure_can_view_session(conn, session, user)

    class_info = await get_class(conn, session["class_id"]) if session.get("class_id") else None
    turns = await get_session_turns(conn, session_id)
    return {
        "session": {
            "id": session["id"],
            "status": session["status"],
            "kind": "class" if session.get("class_id") else "independent",
            "class_id": session.get("class_id"),
            "class_name": class_info["name"] if class_info else None,
            "parent_session_id": session.get("parent_session_id"),
            "started_at": session["started_at"],
            "ended_at": session.get("ended_at"),
            "duration_seconds": session.get("duration_seconds"),
            "scenario": PublicScenarioInfo.from_snapshot(
                session.get("scenario_snapshot") or {}, scenario_id=session.get("scenario_id")
            ),
        },
        "turns": [{"turn_no": t["turn_no"], "speaker": t["speaker"], "content": t["content"]} for t in turns],
    }


@router.get("/{session_id}")
async def get_session_detail(
    session_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Mengambil detail sesi konseling dan riwayat turns.

    - topics (topik sesi ini, memuat judul hidden facts): hanya untuk dosen kelas sesi itu.
    - previous_topics: catatan topik sesi induk untuk sesi lanjutan (BRD 6.1.2).
      Mahasiswa hanya menerima topik berdeskripsi; sesi tanpa induk -> [].
    """
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi dengan ID {session_id} tidak ditemukan.",
        )

    await ensure_can_view_session(conn, session, user)

    detail = to_public_session(session)
    detail["turns"] = await get_session_turns(conn, session_id)
    if is_reviewer(user):
        detail["topics"] = await get_latest_topic_notes(conn, session_id)

    parent_id = session.get("parent_session_id")
    detail["previous_topics"] = (
        await topics_for_viewer(conn, parent_id, user) if parent_id else []
    )
    return detail


@router.get("/{session_id}/briefing-topics")
async def get_briefing_topics(
    session_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Catatan topik sesi yang akan dilanjutkan, untuk halaman briefing mode continue.

    Dipanggil sebelum sesi lanjutan dibuat; session_id adalah calon parent_session_id.
    Mahasiswa hanya menerima topik yang deskripsi terakhirnya tidak kosong.
    """
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi dengan ID {session_id} tidak ditemukan.",
        )

    await ensure_can_view_session(conn, session, user)

    evaluation = await get_evaluation_by_session(conn, session_id)
    return {
        "session_id": session_id,
        "topics": await topics_for_viewer(conn, session_id, user),
        "evaluation_status": evaluation["status"] if evaluation else "none",
    }


# Kelonggaran batas atas garis waktu terhadap jam database (pembulatan dan latensi).
_TIMELINE_TOLERANCE_MS = 5000


async def _check_turn_timing(conn: asyncpg.Connection, session_id: int, payload: CreateTurnRequest) -> None:
    """Server adalah sumber kebenaran garis waktu: tidak boleh mundur atau melampaui waktu nyata."""
    timeline = await get_timeline(conn, session_id)
    if payload.start_ms < timeline["end_ms"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Waktu giliran ini mendahului giliran sebelumnya. Muat ulang halaman, lalu ulangi.",
        )
    if payload.sent_ms > timeline["wall_ms"] + _TIMELINE_TOLERANCE_MS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Waktu giliran melampaui lama sesi sejak dimulai.",
        )


@router.post("/{session_id}/turns", response_model=TurnResponse)
async def send_counselor_turn(
    session_id: int,
    payload: CreateTurnRequest,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Mengirim giliran ucapan konselor dan menerima respons klien virtual."""
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi dengan ID {session_id} tidak ditemukan.",
        )

    ensure_session_owner(session, user)

    if session["status"] == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi latihan ini sudah selesai dan tidak dapat menerima giliran percakapan baru.",
        )

    # asyncio.Lock: antrean murah di dalam satu proses (tanpa memakai koneksi DB tambahan).
    # Lock DB (advisory): menunggu giliran/Peran C sebelumnya, juga dari worker lain.
    lock = await get_session_lock(session_id)
    async with lock:
        t_lock = time.perf_counter()
        turn_lock = await _acquire_turn_lock_or_409(session_id)
        lock_wait_ms = round((time.perf_counter() - t_lock) * 1000, 1)
        try:
            # Validasi ulang status sesi setelah memperoleh lock
            current_session = await get_session_by_id(conn, session_id)
            if current_session and current_session["status"] == "completed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sesi latihan ini sudah selesai dan tidak dapat menerima giliran percakapan baru.",
                )
            await _check_turn_timing(conn, session_id, payload)
        except BaseException:
            await turn_lock.release(commit=False)
            raise

        try:
            # process_turn mengambil alih turn_lock (melepas atau menyerahkannya ke Peran C)
            return await process_turn(
                conn=conn,
                session=session,
                counselor_utterance=payload.content,
                start_ms=payload.start_ms,
                end_ms=payload.end_ms,
                turn_lock=turn_lock,
                lock_wait_ms=lock_wait_ms,
                word_timestamps=None if payload.words is None else [w.model_dump() for w in payload.words],
                sent_ms=payload.sent_ms,
            )
        except LLMServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Layanan simulasi sedang mengalami kendala teknis: {exc}",
            ) from exc


@router.post("/{session_id}/end", response_model=EndSessionResponse)
async def end_active_session(
    session_id: int,
    payload: EndSessionRequest | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Mengakhiri sesi konseling (status='completed', mencatat ended_at dan duration_seconds)."""
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sesi dengan ID {session_id} tidak ditemukan.",
        )

    ensure_session_owner(session, user)

    if session["status"] == "completed":
        return {
            "id": session["id"],
            "status": session["status"],
            "duration_seconds": session["duration_seconds"],
            "ended_at": session["ended_at"] or session["started_at"],
        }

    # Tunggu Peran C terakhir: catatan topik akhir dipakai sesi lanjutan
    turn_lock = await _acquire_turn_lock_or_409(session_id)
    try:
        updated = await end_session(conn, session_id, payload.ended_ms if payload else 0)
    finally:
        await turn_lock.release()

    if not updated:
        # Bisa terjadi jika sesi diakhiri request lain saat menunggu lock
        current = await get_session_by_id(conn, session_id)
        if current and current["status"] == "completed":
            return {
                "id": current["id"],
                "status": current["status"],
                "duration_seconds": current["duration_seconds"],
                "ended_at": current["ended_at"] or current["started_at"],
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui status sesi menjadi selesai.",
        )

    return {
        "id": updated["id"],
        "status": updated["status"],
        "duration_seconds": updated["duration_seconds"],
        "ended_at": updated["ended_at"],
    }
