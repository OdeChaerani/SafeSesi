"""Text-to-speech ucapan klien dengan ElevenLabs, beserta cue viseme untuk lip-sync avatar.

Endpoint: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps. Voice dipilih
dari gender persona klien (ELEVEN_LABS_VOICES di core/config.py), model dari ELEVEN_LABS_TTS_MODEL.
Waktu per huruf dari ElevenLabs dipetakan ke viseme Ready Player Me; ejaan bahasa Indonesia hampir
fonetis (satu huruf kira-kira satu bunyi), jadi pemetaan huruf cukup akurat tanpa pengenal fonem.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import ELEVEN_LABS_VOICES, Settings
from services.speech.stt import SpeechServiceError

ELEVEN_LABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
OUTPUT_FORMAT = "mp3_44100_128"

# Gabungan huruf yang satu bunyi, diperiksa sebelum huruf tunggal.
_DIGRAPHS = {"ng": "viseme_nn", "ny": "viseme_nn", "kh": "viseme_kk", "sy": "viseme_SS"}
_LETTERS = {
    "a": "viseme_aa", "e": "viseme_E", "i": "viseme_I", "o": "viseme_O", "u": "viseme_U",
    "p": "viseme_PP", "b": "viseme_PP", "m": "viseme_PP",
    "f": "viseme_FF", "v": "viseme_FF",
    "t": "viseme_DD", "d": "viseme_DD",
    "k": "viseme_kk", "g": "viseme_kk", "q": "viseme_kk", "x": "viseme_kk", "h": "viseme_kk",
    "c": "viseme_CH", "j": "viseme_CH",
    "s": "viseme_SS", "z": "viseme_SS",
    "n": "viseme_nn", "l": "viseme_nn",
    "r": "viseme_RR", "w": "viseme_U", "y": "viseme_I",
}


@dataclass
class Speech:
    audio: bytes
    visemes: list[dict[str, Any]] = field(default_factory=list)  # [{"viseme", "start_ms", "end_ms"}]
    char_end_ms: list[int] = field(default_factory=list)  # waktu selesai tiap huruf teks asli, untuk subtitle


def voice_for_gender(gender: str | None) -> str:
    g = (gender or "").strip().lower()
    if g.startswith(("laki", "pria", "male")):
        return ELEVEN_LABS_VOICES["male"]
    if g.startswith(("perempuan", "wanita", "female")):
        return ELEVEN_LABS_VOICES["female"]
    raise SpeechServiceError(f"Gender klien {gender!r} tidak dikenali, suara klien tidak dapat dipilih.")


def char_end_times(text: str, alignment: dict[str, Any] | None) -> list[int]:
    """Waktu selesai (ms) tiap huruf `text`; kosong bila alignment tidak cocok persis dengan teks."""
    if not alignment or "".join(alignment.get("characters") or []) != text:
        return []
    ends = alignment.get("character_end_times_seconds") or []
    return [round(e * 1000) for e in ends] if len(ends) == len(text) else []


def viseme_cues(alignment: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Waktu per huruf (detik) -> cue viseme (ms). Spasi/tanda baca = jeda (tanpa cue); cue sama yang bersambung digabung."""
    if not alignment:
        return []
    chars = [c.lower() for c in alignment.get("characters") or []]
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    n = min(len(chars), len(starts), len(ends))
    cues: list[dict[str, Any]] = []
    i = 0
    while i < n:
        pair = "".join(chars[i:i + 2])
        if i + 1 < n and pair in _DIGRAPHS:
            viseme, last = _DIGRAPHS[pair], i + 1
        else:
            viseme, last = _LETTERS.get(chars[i]), i
        if viseme:
            start, end = round(starts[i] * 1000), round(ends[last] * 1000)
            if cues and cues[-1]["viseme"] == viseme and cues[-1]["end_ms"] >= start:
                cues[-1]["end_ms"] = end
            else:
                cues.append({"viseme": viseme, "start_ms": start, "end_ms": end})
        i = last + 1
    return cues


async def synthesize(text: str, gender: str | None, settings: Settings, client: httpx.AsyncClient | None = None) -> Speech:
    if not settings.ELEVEN_LABS_API_KEY:
        raise SpeechServiceError("ELEVEN_LABS_API_KEY belum diatur di backend.")
    voice_id = voice_for_gender(gender)
    body: dict[str, str] = {"text": text, "model_id": settings.ELEVEN_LABS_TTS_MODEL}
    # Dokumentasi: language_code tidak didukung model multilingual_v2.
    if not settings.ELEVEN_LABS_TTS_MODEL.startswith("eleven_multilingual"):
        body["language_code"] = "id"

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.SPEECH_TIMEOUT_S)
    try:
        resp = await client.post(
            ELEVEN_LABS_TTS_URL.format(voice_id=voice_id),
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": settings.ELEVEN_LABS_API_KEY},
            json=body,
        )
    except httpx.HTTPError as exc:
        raise SpeechServiceError(f"Tidak dapat menghubungi ElevenLabs: {type(exc).__name__}") from exc
    finally:
        if owns_client:
            await client.aclose()
    if resp.status_code != 200:
        raise SpeechServiceError(f"ElevenLabs menolak permintaan suara ({resp.status_code}): {resp.text[:200]}")
    try:
        data = resp.json()
        audio = base64.b64decode(data["audio_base64"], validate=True)
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise SpeechServiceError("Respons ElevenLabs tidak berisi audio yang valid.") from exc
    # Lip-sync: normalized_alignment mengikuti bunyi yang diucapkan (mis. angka dieja).
    # Subtitle: alignment mengikuti teks asli yang ditampilkan.
    return Speech(
        audio=audio,
        visemes=viseme_cues(data.get("normalized_alignment") or data.get("alignment")),
        char_end_ms=char_end_times(text, data.get("alignment")),
    )
