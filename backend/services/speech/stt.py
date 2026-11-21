"""Speech-to-text ucapan konselor dengan Groq (Whisper).

Audio hanya diteruskan ke Groq dan tidak disimpan (BRD 7.1 no. 7).
Parameter mengikuti https://console.groq.com/docs/speech-to-text: penanda waktu per kata
membutuhkan response_format=verbose_json dan timestamp_granularities[]=word.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import Settings

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MIN_AUDIO_BYTES = 1_500  # header webm tanpa isi suara hanya beberapa ratus byte
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # batas unggah Groq (tier gratis)
# Whisper cenderung "mengarang" kalimat pada audio hening; segmen dengan peluang tanpa-ucapan
# setinggi ini dianggap hening.
NO_SPEECH_PROB_MAX = 0.8


class SpeechServiceError(Exception):
    """Layanan suara gagal atau belum dikonfigurasi (masalah sistem, bukan mahasiswa)."""


class UnusableAudioError(ValueError):
    """Rekaman tidak bisa dipakai (terlalu pendek, hening, terlalu besar); pesan untuk mahasiswa."""


@dataclass
class Transcript:
    text: str
    words: list[dict[str, Any]] = field(default_factory=list)  # {word, start_ms, end_ms}, relatif ke awal rekaman
    duration_ms: int | None = None


def parse_transcription(data: dict[str, Any]) -> Transcript:
    text = (data.get("text") or "").strip()
    segments = data.get("segments") or []
    if not text or (segments and all((s.get("no_speech_prob") or 0) > NO_SPEECH_PROB_MAX for s in segments)):
        raise UnusableAudioError("Tidak ada ucapan yang terdengar. Coba rekam ulang lebih dekat ke mikrofon.")
    words = [
        {"word": w["word"].strip(), "start_ms": round(float(w["start"]) * 1000), "end_ms": round(float(w["end"]) * 1000)}
        for w in data.get("words") or []
        if (w.get("word") or "").strip() and w.get("start") is not None and w.get("end") is not None
    ]
    duration = data.get("duration")
    return Transcript(text=text, words=words, duration_ms=round(float(duration) * 1000) if duration is not None else None)


async def transcribe(
    audio: bytes, content_type: str, settings: Settings, client: httpx.AsyncClient | None = None
) -> Transcript:
    if len(audio) < MIN_AUDIO_BYTES:
        raise UnusableAudioError("Rekaman terlalu pendek. Tahan tombol selama kamu berbicara.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise UnusableAudioError("Rekaman terlalu panjang. Bagi ucapanmu menjadi beberapa giliran.")
    if not settings.GROQ_API_KEY:
        raise SpeechServiceError("GROQ_API_KEY belum diatur di backend.")

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.SPEECH_TIMEOUT_S)
    try:
        resp = await client.post(
            GROQ_TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            data={
                "model": settings.GROQ_STT_MODEL,
                "language": "id",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            },
            files={"file": ("ucapan.webm", audio, content_type)},
        )
    except httpx.HTTPError as exc:
        raise SpeechServiceError(f"Tidak dapat menghubungi Groq: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await client.aclose()
    if resp.status_code != 200:
        raise SpeechServiceError(f"Groq menolak permintaan transkripsi ({resp.status_code}): {resp.text[:200]}")
    return parse_transcription(resp.json())
