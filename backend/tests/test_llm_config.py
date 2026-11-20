from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import errors as genai_errors

from core.config import Settings
from core.errors import LLMServiceError
from schemas.client_state import ClientState
from services.llm.gemini_client import GeminiAsyncClient, LLMConfigRejected, validate_llm_configs
from services.simulation.notes_updater import NotesUpdateResult, update_topic_notes_llm
from services.simulation.responder import generate_client_response_llm
from services.simulation.state_updater import update_client_state_llm
from tests.base import BaseTestCase


def fake_response(text: str):
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = MagicMock()
    return resp


def client_error(code: int = 400):
    return genai_errors.ClientError(code, {"error": {"code": code, "message": "invalid argument", "status": "INVALID_ARGUMENT"}})


class TestThinkingConfigSettings(unittest.TestCase):
    def test_defaults_per_role(self):
        s = Settings(_env_file=None, DATABASE_URL="", GEMINI_API_KEY="k")
        self.assertEqual(
            (s.GEMINI_MODEL_STATE, s.GEMINI_THINKING_BUDGET_STATE),
            ("gemini-3.8-flash", 0),
        )
        # Peran B dan C memakai model murah; Peran A tetap 3.8-flash (hasil uji replay)
        self.assertEqual(
            (s.GEMINI_MODEL_RESPONDER, s.GEMINI_THINKING_BUDGET_RESPONDER),
            ("gemini-3.1-flash-lite", None),
        )
        self.assertEqual(
            (s.GEMINI_MODEL_NOTES, s.GEMINI_THINKING_BUDGET_NOTES),
            ("gemini-3.1-flash-lite", None),
        )
        self.assertTrue(s.GEMINI_VALIDATE_ON_STARTUP)

    def test_only_deprecated_models_are_upgraded(self):
        s = Settings(
            _env_file=None,
            GEMINI_MODEL_STATE="gemini-2.5-flash",
            GEMINI_MODEL_RESPONDER="gemini-2.5-pro",
            GEMINI_MODEL_NOTES="gemini-2.5-flash-lite",
        )
        self.assertEqual(s.GEMINI_MODEL_STATE, "gemini-3.8-flash")
        self.assertEqual(s.GEMINI_MODEL_RESPONDER, "gemini-3.8-flash")
        self.assertEqual(s.GEMINI_MODEL_NOTES, "gemini-2.5-flash-lite")

    def test_budget_can_be_unset_or_custom(self):
        s = Settings(
            GEMINI_THINKING_BUDGET_STATE="none",
            GEMINI_THINKING_BUDGET_RESPONDER="",
            GEMINI_THINKING_BUDGET_NOTES="256",
            GEMINI_MODEL_NOTES="gemini-3.5-flash-lite",
        )
        self.assertIsNone(s.GEMINI_THINKING_BUDGET_STATE)
        self.assertIsNone(s.GEMINI_THINKING_BUDGET_RESPONDER)
        self.assertEqual(s.GEMINI_THINKING_BUDGET_NOTES, 256)
        self.assertEqual(s.GEMINI_MODEL_NOTES, "gemini-3.5-flash-lite")


class TestGeminiClientThinking(unittest.IsolatedAsyncioTestCase):
    def make_client(self, side_effect):
        client = GeminiAsyncClient(api_key="test")
        sdk = MagicMock()
        sdk.aio.models.generate_content = AsyncMock(side_effect=side_effect)
        client._client = sdk
        return client, sdk.aio.models.generate_content

    async def test_budget_sent_as_thinking_config(self):
        client, gen = self.make_client([fake_response("halo")])
        await client.generate_text("m", "sys", "prompt", thinking_budget=0)
        self.assertEqual(gen.await_args.kwargs["config"].thinking_config.thinking_budget, 0)

    async def test_none_budget_omits_thinking_config(self):
        client, gen = self.make_client([fake_response("halo")])
        await client.generate_text("m", "sys", "prompt", thinking_budget=None)
        self.assertIsNone(gen.await_args.kwargs["config"].thinking_config)

    async def test_rejected_budget_raises_clear_error_without_retry(self):
        client, gen = self.make_client([client_error(400), fake_response("halo")])
        with self.assertRaises(LLMConfigRejected) as ctx:
            await client.generate_text("gemini-3.5-flash-lite", "sys", "prompt", thinking_budget=0, role="C")
        msg = str(ctx.exception)
        self.assertIn("Peran C", msg)
        self.assertIn("gemini-3.5-flash-lite", msg)
        self.assertIn("thinking_budget=0", msg)
        self.assertEqual(gen.await_count, 1)  # tidak ada fallback tanpa thinking_config

    async def test_rejected_in_generate_json_is_not_wrapped(self):
        client, gen = self.make_client([client_error(404)])
        with self.assertRaises(LLMConfigRejected) as ctx:
            await client.generate_json("model-tidak-ada", "sys", "prompt", ClientState, thinking_budget=None, role="A")
        self.assertIn("Peran A", str(ctx.exception))
        self.assertIn("default model", str(ctx.exception))
        self.assertEqual(gen.await_count, 1)

    async def test_invalid_json_does_not_trigger_second_call(self):
        client, gen = self.make_client([fake_response("{invalid json")])
        with self.assertLogs("safesesi.llm", level="ERROR"), self.assertRaises(LLMServiceError):
            await client.generate_json("m", "sys", "prompt", ClientState, thinking_budget=0)
        self.assertEqual(gen.await_count, 1)

    async def test_other_errors_not_retried(self):
        client, gen = self.make_client([client_error(429)])
        with self.assertLogs("safesesi.llm", level="ERROR"), self.assertRaises(LLMServiceError) as ctx:
            await client.generate_text("m", "sys", "prompt", thinking_budget=0)
        self.assertNotIsInstance(ctx.exception, LLMConfigRejected)
        self.assertEqual(gen.await_count, 1)


class TestStartupValidation(unittest.IsolatedAsyncioTestCase):
    def settings(self, notes_model="gemini-3.5-flash-lite", notes_budget=None):
        s = MagicMock()
        s.GEMINI_MODEL_STATE, s.GEMINI_THINKING_BUDGET_STATE = "gemini-3.8-flash", 0
        s.GEMINI_MODEL_RESPONDER, s.GEMINI_THINKING_BUDGET_RESPONDER = "gemini-3.8-flash", 0
        s.GEMINI_MODEL_NOTES, s.GEMINI_THINKING_BUDGET_NOTES = notes_model, notes_budget
        for role in ("BEHAVIOR_CODING", "GLOBAL_SCORING", "PROCESS_OBSERVATION", "FEEDBACK"):
            setattr(s, f"GEMINI_MODEL_{role}", "gemini-3.8-flash")
            setattr(s, f"GEMINI_THINKING_BUDGET_{role}", 0)
        return s

    async def test_probes_each_distinct_combo_once(self):
        llm = MagicMock()
        llm.probe = AsyncMock()
        await validate_llm_configs(self.settings(), client=llm)
        probed = sorted((c.args[0], c.args[1]) for c in llm.probe.await_args_list)
        self.assertEqual(probed, [("gemini-3.5-flash-lite", None), ("gemini-3.8-flash", 0)])

    async def test_evaluator_agents_validated_at_startup(self):
        s = self.settings()
        s.GEMINI_THINKING_BUDGET_FEEDBACK = None  # kombinasi baru: gemini-3.8-flash + budget bawaan
        llm = MagicMock()
        llm.probe = AsyncMock()
        await validate_llm_configs(s, client=llm)
        probed = {(c.args[0], c.args[1]): c.kwargs["role"] for c in llm.probe.await_args_list}
        self.assertEqual(probed[("gemini-3.8-flash", None)], "feedback")

    async def test_rejected_combo_fails_startup(self):
        llm = MagicMock()

        async def probe(model, budget, role=None):
            if model == "gemini-3.5-flash-lite":
                raise LLMConfigRejected(role, model, budget, "INVALID_ARGUMENT")

        llm.probe = AsyncMock(side_effect=probe)
        with self.assertRaises(LLMConfigRejected) as ctx:
            await validate_llm_configs(self.settings(notes_budget=0), client=llm)
        self.assertIn("Peran C", str(ctx.exception))
        self.assertIn("thinking_budget=0", str(ctx.exception))

    async def test_transient_error_only_warns(self):
        llm = MagicMock()
        llm.probe = AsyncMock(side_effect=ConnectionError("jaringan putus"))
        with self.assertLogs("safesesi.llm", level="WARNING"):
            await validate_llm_configs(self.settings(), client=llm)

    async def test_lifespan_skips_validation_when_disabled(self):
        import main

        cfg = MagicMock()
        cfg.GEMINI_VALIDATE_ON_STARTUP = False
        cfg.GEMINI_API_KEY = "k"
        cfg.DATABASE_URL = ""
        cfg.NOTES_TIMEOUT_S = 1.0
        cfg.TURN_LOCK_TIMEOUT_S = 1.0
        with patch("main.get_settings", return_value=cfg), patch(
            "main.validate_llm_configs", AsyncMock()
        ) as mock_validate:
            async with main.lifespan(MagicMock()):
                pass
        mock_validate.assert_not_awaited()

    async def test_lifespan_fails_when_config_rejected(self):
        import main

        cfg = MagicMock()
        cfg.GEMINI_VALIDATE_ON_STARTUP = True
        cfg.GEMINI_API_KEY = "k"
        cfg.DATABASE_URL = ""
        rejected = LLMConfigRejected("A", "gemini-x", 0, "INVALID_ARGUMENT")
        with patch("main.get_settings", return_value=cfg), patch(
            "main.validate_llm_configs", AsyncMock(side_effect=rejected)
        ):
            with self.assertRaises(LLMConfigRejected):
                async with main.lifespan(MagicMock()):
                    pass


class TestRoleConfigForwarding(BaseTestCase):
    """Model & thinking budget per peran diteruskan dari config."""

    def settings(self):
        s = MagicMock()
        s.GEMINI_MODEL_STATE, s.GEMINI_THINKING_BUDGET_STATE = "model-a", 0
        s.GEMINI_MODEL_RESPONDER, s.GEMINI_THINKING_BUDGET_RESPONDER = "model-b", None
        s.GEMINI_MODEL_NOTES, s.GEMINI_THINKING_BUDGET_NOTES = "model-c", 128
        return s

    def test_each_role_uses_its_own_model_and_budget(self):
        snap = self.get_sample_snapshot()
        llm = AsyncMock()
        llm.generate_json.side_effect = [
            ClientState(emotion_type="Cemas", disclosure_level="guarded", ambivalence_lean="both"),
            NotesUpdateResult(),
        ]
        llm.generate_text.return_value = "Iya Kak."
        cfg = self.settings()
        with patch("services.simulation.state_updater.get_settings", return_value=cfg), patch(
            "services.simulation.responder.get_settings", return_value=cfg
        ), patch("services.simulation.notes_updater.get_settings", return_value=cfg), patch(
            "services.simulation.state_updater.get_gemini_client", return_value=llm
        ), patch("services.simulation.responder.get_gemini_client", return_value=llm), patch(
            "services.simulation.notes_updater.get_gemini_client", return_value=llm
        ):
            self.run_async(update_client_state_llm("Halo", snap["initial_state"], snap["persona"], snap["case"], []))
            self.run_async(generate_client_response_llm(snap["persona"], snap["case"], snap["initial_state"], [], [], "Halo", []))
            self.run_async(update_topic_notes_llm([], "Halo", "Iya Kak."))

        a_call, c_call = llm.generate_json.await_args_list
        b_call = llm.generate_text.await_args
        for call, expected in ((a_call, ("model-a", 0, "A")), (b_call, ("model-b", None, "B")), (c_call, ("model-c", 128, "C"))):
            self.assertEqual(
                (call.kwargs["model"], call.kwargs["thinking_budget"], call.kwargs["role"]), expected
            )

    def test_config_rejection_is_not_retried_by_role(self):
        snap = self.get_sample_snapshot()
        llm = AsyncMock()
        llm.generate_json.side_effect = LLMConfigRejected("A", "model-a", 0, "INVALID_ARGUMENT")
        with patch("services.simulation.state_updater.get_settings", return_value=self.settings()), patch(
            "services.simulation.state_updater.get_gemini_client", return_value=llm
        ):
            with self.assertRaises(LLMConfigRejected):
                self.run_async(update_client_state_llm("Halo", snap["initial_state"], snap["persona"], snap["case"], []))
        self.assertEqual(llm.generate_json.await_count, 1)

    def test_responder_prompt_static_first_history_last(self):
        snap = self.get_sample_snapshot()
        llm = AsyncMock()
        llm.generate_text.return_value = "Iya Kak."
        history = [{"speaker": "counselor", "content": "RIWAYAT-PERTAMA"}]
        with patch("services.simulation.responder.get_gemini_client", return_value=llm):
            self.run_async(
                generate_client_response_llm(
                    snap["persona"], snap["case"], snap["initial_state"], [], history, "UCAPAN-TERKINI", []
                )
            )
        prompt = llm.generate_text.await_args.kwargs["user_prompt"]
        order = [
            prompt.index("### Profil Persona Anda"),
            prompt.index("### Kasus & Masalah Anda"),
            prompt.index("### Petunjuk Menanggapi"),
            prompt.index("### Informasi Tersembunyi"),
            prompt.index("### Kondisi Emosi"),
            prompt.index("RIWAYAT-PERTAMA"),
            prompt.index("UCAPAN-TERKINI"),
        ]
        self.assertEqual(order, sorted(order))
