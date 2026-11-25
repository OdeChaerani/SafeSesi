"""STT (Groq) dan TTS (ElevenLabs): layanan eksternal dipalsukan dengan httpx.MockTransport."""
from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException

from api.speech import client_turn_audio, transcribe_counselor_audio
from core.config import ELEVEN_LABS_VOICES, Settings
from services.simulation.orchestrator import _save_turn_pair
from services.speech.stt import (
    GROQ_TRANSCRIPTION_URL,
    SpeechServiceError,
    UnusableAudioError,
    parse_transcription,
    transcribe,
)
from services.speech.tts import Speech, char_end_times, synthesize, viseme_cues, voice_for_gender
from tests.base import BaseTestCase

AUDIO = b"\x1aE\xdf\xa3" + b"x" * 4000  # cukup besar untuk lolos batas minimum

def tts_json(audio: bytes = b"ID3mp3", **extra: Any) -> dict[str, Any]:
    return {"audio_base64": base64.b64encode(audio).decode(), **extra}


VERBOSE = {
    "text": " Apa yang paling kamu khawatirkan?",
    "duration": 2.4,
    "segments": [{"start": 0.0, "end": 2.4, "no_speech_prob": 0.01}],
    "words": [{"word": " Apa", "start": 0.1, "end": 0.35}, {"word": "yang", "start": 0.35, "end": 0.6}],
}


def settings(**kw: Any) -> Settings:
    base = {"GROQ_API_KEY": "gk", "ELEVEN_LABS_API_KEY": "ek", "GEMINI_VALIDATE_ON_STARTUP": False}
    return Settings(_env_file=None, **{**base, **kw})


def mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestTranscription(BaseTestCase):
    def test_parse_words_to_ms(self):
        t = parse_transcription(VERBOSE)
        self.assertEqual(t.text, "Apa yang paling kamu khawatirkan?")
        self.assertEqual(t.words[0], {"word": "Apa", "start_ms": 100, "end_ms": 350})
        self.assertEqual(t.duration_ms, 2400)

    def test_silence_rejected(self):
        with self.assertRaises(UnusableAudioError):
            parse_transcription({"text": "Terima kasih.", "segments": [{"no_speech_prob": 0.95}]})
        with self.assertRaises(UnusableAudioError):
            parse_transcription({"text": "  "})

    def test_too_short_rejected_without_calling_groq(self):
        def handler(_req):
            raise AssertionError("Groq tidak boleh dipanggil")
        with self.assertRaises(UnusableAudioError):
            self.run_async(transcribe(b"x" * 100, "audio/webm", settings(), mock_client(handler)))

    def test_request_fields(self):
        seen: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], req.content
            return httpx.Response(200, json=VERBOSE)

        t = self.run_async(transcribe(AUDIO, "audio/webm", settings(), mock_client(handler)))
        self.assertEqual(seen["url"], GROQ_TRANSCRIPTION_URL)
        self.assertEqual(seen["auth"], "Bearer gk")
        for field in (b'name="model"\r\n\r\nwhisper-large-v3-turbo', b'name="language"\r\n\r\nid',
                      b'name="response_format"\r\n\r\nverbose_json', b'name="timestamp_granularities[]"\r\n\r\nword'):
            self.assertIn(field, seen["body"])
        self.assertEqual(len(t.words), 2)

    def test_groq_error_is_service_error(self):
        with self.assertRaises(SpeechServiceError):
            self.run_async(transcribe(AUDIO, "audio/webm", settings(), mock_client(lambda r: httpx.Response(401, text="bad key"))))

    def test_missing_key(self):
        with self.assertRaises(SpeechServiceError):
            self.run_async(transcribe(AUDIO, "audio/webm", settings(GROQ_API_KEY="")))


class TestSynthesis(BaseTestCase):
    def test_voice_by_gender(self):
        self.assertEqual(voice_for_gender("Perempuan"), ELEVEN_LABS_VOICES["female"])
        self.assertEqual(voice_for_gender("Laki-laki"), ELEVEN_LABS_VOICES["male"])
        with self.assertRaises(SpeechServiceError):
            voice_for_gender("")

    def test_request_fields(self):
        seen: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            seen["req"] = req
            return httpx.Response(200, json=tts_json(alignment={
                "characters": list("Ma"), "character_start_times_seconds": [0.0, 0.1], "character_end_times_seconds": [0.1, 0.25],
            }))

        speech = self.run_async(synthesize("Halo, Kak.", "Laki-laki", settings(), mock_client(handler)))
        req = seen["req"]
        self.assertEqual(speech.audio, b"ID3mp3")
        self.assertEqual([c["viseme"] for c in speech.visemes], ["viseme_PP", "viseme_aa"])
        self.assertEqual(speech.char_end_ms, [])  # alignment "Ma" tidak cocok dengan teks "Halo, Kak."
        self.assertTrue(req.url.path.endswith(f"{ELEVEN_LABS_VOICES['male']}/with-timestamps"))
        self.assertEqual(req.headers["xi-api-key"], "ek")
        self.assertEqual(req.url.params["output_format"], "mp3_44100_128")
        self.assertEqual(json.loads(req.content), {"text": "Halo, Kak.", "model_id": "eleven_flash_v2_5", "language_code": "id"})

    def test_multilingual_v2_without_language_code(self):
        seen: dict[str, Any] = {}

        def handler(req):
            seen["body"] = json.loads(req.content)
            return httpx.Response(200, json=tts_json())

        self.run_async(synthesize("Halo", "Perempuan", settings(ELEVEN_LABS_TTS_MODEL="eleven_multilingual_v2"), mock_client(handler)))
        self.assertNotIn("language_code", seen["body"])

    def test_error_is_service_error(self):
        with self.assertRaises(SpeechServiceError):
            self.run_async(synthesize("Halo", "Perempuan", settings(), mock_client(lambda r: httpx.Response(429, text="quota"))))

    def test_invalid_audio_is_service_error(self):
        with self.assertRaises(SpeechServiceError):
            self.run_async(synthesize("Halo", "Perempuan", settings(), mock_client(lambda r: httpx.Response(200, json={"audio_base64": "%%"}))))

    def test_prefers_normalized_alignment(self):
        def handler(req):
            return httpx.Response(200, json=tts_json(
                alignment={"characters": ["2"], "character_start_times_seconds": [0], "character_end_times_seconds": [0.3]},
                normalized_alignment={"characters": list("du"), "character_start_times_seconds": [0, 0.1], "character_end_times_seconds": [0.1, 0.3]},
            ))

        speech = self.run_async(synthesize("2", "Perempuan", settings(), mock_client(handler)))
        self.assertEqual([c["viseme"] for c in speech.visemes], ["viseme_DD", "viseme_U"])


class TestCharEndTimes(BaseTestCase):
    def test_matching_alignment(self):
        alignment = {"characters": list("Iya"), "character_end_times_seconds": [0.1, 0.25, 0.4]}
        self.assertEqual(char_end_times("Iya", alignment), [100, 250, 400])

    def test_mismatch_or_missing(self):
        self.assertEqual(char_end_times("Iya", {"characters": list("Iy"), "character_end_times_seconds": [0.1, 0.2]}), [])
        self.assertEqual(char_end_times("Iya", None), [])


class TestVisemeCues(BaseTestCase):
    @staticmethod
    def align(text: str, step: float = 0.1) -> dict[str, Any]:
        return {
            "characters": list(text),
            "character_start_times_seconds": [i * step for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(text))],
        }

    def test_letters_digraphs_and_pauses(self):
        cues = viseme_cues(self.align("Nyanyi, ya"))
        self.assertEqual(
            [c["viseme"] for c in cues],
            ["viseme_nn", "viseme_aa", "viseme_nn", "viseme_I", "viseme_I", "viseme_aa"],
        )
        self.assertEqual(cues[0], {"viseme": "viseme_nn", "start_ms": 0, "end_ms": 200})  # "Ny" satu cue
        self.assertEqual(cues[4]["start_ms"], 800)  # koma dan spasi = jeda, cue "y" tidak digabung ke "i"

    def test_repeated_viseme_merged(self):
        self.assertEqual(viseme_cues(self.align("mb")), [{"viseme": "viseme_PP", "start_ms": 0, "end_ms": 200}])

    def test_missing_alignment(self):
        self.assertEqual(viseme_cues(None), [])
        self.assertEqual(viseme_cues({"characters": ["a"]}), [])


class TestSpeechApi(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.user = self.get_sample_user(user_id=10)
        self.session = {"id": 5, "student_id": 10, "status": "in_progress", "scenario_snapshot": {"persona": {"gender": "Perempuan"}}}

    def request(self, body: bytes, content_type: str = "audio/webm") -> MagicMock:
        req = MagicMock()
        req.headers = {"content-type": content_type, "content-length": str(len(body))}
        req.body = AsyncMock(return_value=body)
        return req

    def transcribe_call(self, req, preview: bool = False):
        with patch("api.speech.get_session_by_id", AsyncMock(return_value=self.session)), \
             patch("api.speech.get_settings", return_value=settings()):
            return self.run_async(transcribe_counselor_audio(5, req, preview=preview, user=self.user, conn=self.conn))

    @patch("api.speech.log_speech_timing")
    @patch("api.speech.transcribe", new_callable=AsyncMock)
    def test_preview_logged_separately(self, stt, log):
        stt.return_value = parse_transcription(VERBOSE)
        self.transcribe_call(self.request(AUDIO), preview=True)
        self.assertEqual(log.call_args.args[0], "stt_preview")

    @patch("api.speech.transcribe", new_callable=AsyncMock)
    def test_transcribe_returns_words(self, stt):
        stt.return_value = parse_transcription(VERBOSE)
        res = self.transcribe_call(self.request(AUDIO))
        self.assertEqual(res["text"], "Apa yang paling kamu khawatirkan?")
        self.assertEqual(res["words"][1]["start_ms"], 350)

    @patch("api.speech.transcribe", new_callable=AsyncMock)
    def test_unusable_audio_is_422_with_message(self, stt):
        stt.side_effect = UnusableAudioError("Tidak ada ucapan yang terdengar.")
        with self.assertRaises(HTTPException) as ctx:
            self.transcribe_call(self.request(AUDIO))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("terdengar", ctx.exception.detail)

    def test_non_audio_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            self.transcribe_call(self.request(b"{}", "application/json"))
        self.assertEqual(ctx.exception.status_code, 415)

    def test_other_students_session_forbidden(self):
        with self.assertRaises(HTTPException) as ctx:
            self.session["student_id"] = 99
            self.transcribe_call(self.request(AUDIO))
        self.assertEqual(ctx.exception.status_code, 403)

    def audio_call(self, turn):
        with patch("api.speech.get_session_by_id", AsyncMock(return_value=self.session)), \
             patch("api.speech.get_turn", AsyncMock(return_value=turn)), \
             patch("api.speech.get_settings", return_value=settings()):
            return self.run_async(client_turn_audio(5, 2, user=self.user, conn=self.conn))

    @patch("api.speech.synthesize", new_callable=AsyncMock)
    def test_client_turn_audio(self, tts):
        cues = [{"viseme": "viseme_I", "start_ms": 0, "end_ms": 90}]
        tts.return_value = Speech(audio=b"ID3mp3", visemes=cues, char_end_ms=[50, 90])
        res = self.audio_call({"id": 1, "turn_no": 2, "speaker": "client", "content": "Iya, Kak."})
        body = json.loads(res.body)
        self.assertEqual(base64.b64decode(body["audio_base64"]), b"ID3mp3")
        self.assertEqual(body["visemes"], cues)
        self.assertEqual(body["char_end_ms"], [50, 90])
        self.assertEqual(res.media_type, "application/json")
        self.assertEqual(tts.call_args.args[:2], ("Iya, Kak.", "Perempuan"))

    @patch("api.speech.synthesize", new_callable=AsyncMock)
    def test_counselor_turn_not_synthesized(self, tts):
        with self.assertRaises(HTTPException) as ctx:
            self.audio_call({"id": 1, "turn_no": 1, "speaker": "counselor", "content": "Halo"})
        self.assertEqual(ctx.exception.status_code, 404)
        tts.assert_not_called()


class TestWordTimestampsSaved(BaseTestCase):
    @patch("services.simulation.orchestrator.save_client_state", new_callable=AsyncMock, return_value=9)
    @patch("services.simulation.orchestrator.save_turn", new_callable=AsyncMock, side_effect=[1, 2])
    @patch("services.simulation.orchestrator.get_next_turn_no", new_callable=AsyncMock, return_value=3)
    def test_only_counselor_turn_gets_words(self, _next, save_turn, _state):
        words = [{"word": "Halo", "start_ms": 1000, "end_ms": 1300}]
        self.run_async(_save_turn_pair(self.create_mock_connection(), 5, "Halo", "Iya", {}, 1000, 1300, words))
        counselor, client = save_turn.call_args_list
        self.assertEqual(counselor.kwargs["word_timestamps"], words)
        self.assertNotIn("word_timestamps", client.kwargs)
