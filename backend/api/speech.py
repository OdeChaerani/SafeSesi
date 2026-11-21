"""Endpoint suara: transkripsi ucapan konselor (STT) dan audio ucapan klien (TTS)."""
from __future__ import annotations

import base64
import json
import time
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.deps import get_current_user, get_db, verify_session_ownership
from core.config import get_settings
from repositories.sessions import get_session_by_id
from repositories.turns import get_turn
from services.simulation.timing import log_speech_timing
from services.speech.stt import MAX_AUDIO_BYTES, SpeechServiceError, UnusableAudioError, transcribe
from services.speech.tts import synthesize

router = APIRouter(prefix="/sessions", tags=["speech"])


async def _load_owned_session(conn: asyncpg.Connection, session_id: int, user: dict[str, Any]) -> dict[str, Any]:
    session = await get_session_by_id(conn, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sesi dengan ID {session_id} tidak ditemukan.")
    verify_session_ownership(session, user)
    return session


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


@router.post("/{session_id}/transcribe")
async def transcribe_counselor_audio(
    session_id: int,
    request: Request,
    preview: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Body = audio mentah (mis. audio/webm). Hasilnya ditinjau mahasiswa sebelum dikirim sebagai giliran.

    Audio hanya ada di memori selama permintaan ini dan tidak disimpan (BRD 7.1 no. 7).
    """
    session = await _load_owned_session(conn, session_id, user)
    if session["status"] == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sesi latihan ini sudah selesai.")
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Kirim rekaman sebagai audio (mis. audio/webm).")
    if int(request.headers.get("content-length") or 0) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Rekaman terlalu panjang.")

    audio = await request.body()
    t0 = time.perf_counter()
    try:
        transcript = await transcribe(audio, content_type, get_settings())
    except UnusableAudioError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except SpeechServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Layanan pengenalan suara bermasalah: {exc}") from exc
    finally:
        # preview = teks sementara selama merekam (dikirim berkala), bukan transkrip giliran.
        kind = "stt_preview" if preview else "stt"
        log_speech_timing(kind, session_id, _elapsed_ms(t0), audio_kb=round(len(audio) / 1024, 1))
        del audio
    return {"text": transcript.text, "words": transcript.words, "duration_ms": transcript.duration_ms}


@router.get("/{session_id}/turns/{turn_no}/audio")
async def client_turn_audio(
    session_id: int,
    turn_no: int,
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Response:
    """Audio ucapan klien (mp3 base64) + cue viseme untuk lip-sync + waktu per huruf untuk subtitle.

    Hanya teks giliran klien yang tersimpan yang disintesis, bukan teks bebas.
    """
    session = await _load_owned_session(conn, session_id, user)
    turn = await get_turn(conn, session_id, turn_no)
    if not turn or turn["speaker"] != "client":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Giliran klien tidak ditemukan.")
    snapshot = session.get("scenario_snapshot") or {}
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)

    t0 = time.perf_counter()
    try:
        speech = await synthesize(turn["content"], (snapshot.get("persona") or {}).get("gender"), get_settings())
    except SpeechServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Suara klien tidak tersedia: {exc}") from exc
    finally:
        log_speech_timing("tts", session_id, _elapsed_ms(t0), turn_no=turn_no, chars=len(turn["content"]))
    body = {
        "audio_base64": base64.b64encode(speech.audio).decode("ascii"),
        "visemes": speech.visemes,
        "char_end_ms": speech.char_end_ms,
    }
    return Response(content=json.dumps(body), media_type="application/json", headers={"Cache-Control": "private, max-age=3600"})
