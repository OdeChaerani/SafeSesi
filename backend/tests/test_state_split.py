from __future__ import annotations

import asyncio
import itertools
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from api.sessions import end_active_session, send_counselor_turn
from core.errors import LLMServiceError
from schemas.client_state import ClientState, StateDecision, StateDetail
from schemas.session import CreateTurnRequest
from services.llm.gemini_client import _record_usage, role_llm_configs, track_usage
from services.simulation.notes_updater import TopicNoteUpdate
from services.simulation.responder import generate_client_response_llm
from services.simulation.state_updater import (
    provisional_state,
    update_client_state_decision,
    update_client_state_detail,
)
from tests.base import BaseTestCase
from tests.test_background_notes import FakeDbLocks, settle

_session_ids = itertools.count(9500)


def decision(level: str = "medium", discord: bool = False) -> StateDecision:
    return StateDecision(
        disclosure_reason="Merasa dipahami setelah refleksi",
        disclosure_level=level,
        discord_reason="Konselor mengarahkan sepihak" if discord else "Hubungan selaras",
        discord_present=discord,
        ambivalence_reason="Dua sisi sama kuat",
        ambivalence_lean="both",
        emotion_short="Lega tapi ragu",
    )


DETAIL = StateDetail(
    emotion_type="Lega namun masih ragu",
    emotion_cause="Konselor memahami bebannya",
    disclosure_trigger="Refleksi konselor",
    reasons_to_change="Ingin lebih tenang",
    reasons_to_maintain="Takut mengecewakan",
)


class TestSplitPipeline(unittest.IsolatedAsyncioTestCase):
    """Mode split: B menunggu State Decision Agent; State Detail Agent dan Peran C setelah respons."""

    def setUp(self) -> None:
        self.session_id = next(_session_ids)
        base = BaseTestCase()
        self.user = base.get_sample_user(user_id=10)
        self.session = base.get_sample_session(session_id=self.session_id, student_id=10)
        self.initial_state = self.session["scenario_snapshot"]["initial_state"]
        self.conn = base.create_mock_connection()

        self.events: list[str] = []
        self.locks = FakeDbLocks(self.events)
        self.detail_gate = asyncio.Event()
        self.c_gate = asyncio.Event()
        self.detail_error: Exception | None = None
        turn_numbers = itertools.count(1, 2)

        self.settings = MagicMock()
        self.settings.STATE_UPDATE_MODE = "split"
        self.settings.NOTES_UPDATE_MODE = "background"
        self.settings.GREETING_SHORTCUT_ENABLED = False
        self.settings.DEBUG_INCLUDE_INTERNAL = False
        self.settings.NOTES_TIMEOUT_S = 5.0

        async def fake_decision(**kwargs: Any) -> StateDecision:
            self.events.append("decision_started")
            await asyncio.sleep(0)
            self.events.append("decision_done")
            return decision()

        async def fake_role_b(**kwargs: Any) -> str:
            self.events.append("b_called")
            self.b_kwargs = kwargs
            return "Iya, rasanya lebih lega."

        async def fake_detail(**kwargs: Any) -> StateDetail:
            self.events.append("detail_started")
            await self.detail_gate.wait()
            if self.detail_error:
                self.events.append("detail_failed")
                raise self.detail_error
            self.events.append("detail_done")
            return DETAIL

        async def fake_notes_llm(**kwargs: Any) -> list[TopicNoteUpdate]:
            self.events.append("c_started")
            await self.c_gate.wait()
            self.events.append("c_done")
            return [TopicNoteUpdate(topic_name="Permasalahan utama", description="Catatan baru")]

        async def fake_load_state(conn: Any, session_id: int) -> dict[str, Any]:
            self.events.append("load_state")
            return dict(self.initial_state)

        async def fake_update_details(conn: Any, state_id: int, details: dict[str, Any]) -> None:
            self.events.append("detail_saved")
            self.saved_details = (state_id, details)

        self.mock_save_state = AsyncMock(return_value=77)
        self.mock_combined = AsyncMock()
        patches = [
            patch("api.sessions.acquire_turn_lock", side_effect=self.locks.acquire),
            patch("api.sessions.get_session_by_id", AsyncMock(return_value=self.session)),
            patch(
                "api.sessions.end_session",
                AsyncMock(side_effect=lambda *a: self.events.append("end_session") or {"id": self.session_id, "status": "completed", "duration_seconds": 60, "ended_at": "2026-11-15T10:00:00Z"}),
            ),
            patch("services.simulation.orchestrator.get_settings", return_value=self.settings),
            patch("services.simulation.orchestrator.get_latest_client_state", side_effect=fake_load_state),
            patch("services.simulation.orchestrator.get_latest_topic_notes", AsyncMock(return_value=[{"session_topic_id": 1, "topic_name": "Permasalahan utama", "description": ""}])),
            patch("services.simulation.orchestrator.get_session_turns", AsyncMock(return_value=[])),
            patch("services.simulation.orchestrator.get_next_turn_no", side_effect=lambda *a, **k: next(turn_numbers)),
            patch("services.simulation.orchestrator.save_turn", AsyncMock(return_value=1)),
            patch("services.simulation.orchestrator.save_client_state", self.mock_save_state),
            patch("services.simulation.orchestrator.save_topic_note", AsyncMock(side_effect=lambda *a, **k: self.events.append("note_saved"))),
            patch("services.simulation.orchestrator.update_client_state_llm", self.mock_combined),
            patch("services.simulation.orchestrator.update_client_state_decision", side_effect=fake_decision),
            patch("services.simulation.orchestrator.update_client_state_detail", side_effect=fake_detail),
            patch("services.simulation.orchestrator.update_client_state_details", side_effect=fake_update_details),
            patch("services.simulation.orchestrator.generate_client_response_llm", side_effect=fake_role_b),
            patch("services.simulation.orchestrator.update_topic_notes_llm", side_effect=fake_notes_llm),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def turn(self, text: str = "Kedengarannya berat sekali, ya."):
        return send_counselor_turn(session_id=self.session_id, payload=CreateTurnRequest(content=text), user=self.user, conn=self.conn)

    async def test_b_waits_for_decision_and_detail_runs_after_response(self):
        res = await asyncio.wait_for(self.turn(), timeout=2)
        await settle()

        self.assertEqual(res.content, "Iya, rasanya lebih lega.")
        self.assertLess(self.events.index("decision_done"), self.events.index("b_called"))
        self.assertTrue(self.b_kwargs["decision_only"])
        self.mock_combined.assert_not_awaited()
        # State Detail Agent dan Peran C sudah jalan bersamaan, lock masih dipegang
        self.assertIn("detail_started", self.events)
        self.assertIn("c_started", self.events)
        self.assertNotIn("lock_released", self.events)

        self.detail_gate.set()
        self.c_gate.set()
        await settle()
        self.assertIn("detail_saved", self.events)
        self.assertIn("note_saved", self.events)
        self.assertEqual(self.events[-1], "lock_released")
        self.assertEqual(self.locks.releases, [True])
        self.assertEqual(self.saved_details[0], 77)  # UPDATE baris state giliran ini

    async def test_provisional_row_holds_decision(self):
        self.detail_gate.set()
        self.c_gate.set()
        await self.turn()
        saved = self.mock_save_state.await_args.kwargs["state"]
        self.assertEqual(saved["disclosure_level"], "medium")
        self.assertEqual(saved["emotion_type"], "Lega tapi ragu")
        self.assertEqual(saved["disclosure_trigger"], "Merasa dipahami setelah refleksi")
        self.assertIsNone(saved["discord_context"])  # discord tidak tampak
        self.assertEqual(saved["reasons_to_change"], self.initial_state["reasons_to_change"])

    async def test_detail_failure_does_not_fail_turn(self):
        self.detail_error = LLMServiceError("Gemini tidak tersedia")
        self.detail_gate.set()
        self.c_gate.set()
        with self.assertLogs("safesesi.simulation.orchestrator", level="ERROR") as logs:
            res = await asyncio.wait_for(self.turn(), timeout=2)
            await settle()

        self.assertEqual(res.content, "Iya, rasanya lebih lega.")
        self.assertNotIn("detail_saved", self.events)
        self.assertIn("note_saved", self.events)  # Peran C tetap tersimpan
        self.assertEqual(self.locks.releases, [True])
        self.assertTrue(any("State Detail Agent background gagal" in line for line in logs.output))

    async def test_detail_timeout_does_not_fail_turn(self):
        self.settings.NOTES_TIMEOUT_S = 0.05
        self.c_gate.set()
        with self.assertLogs("safesesi.simulation.orchestrator", level="ERROR") as logs:
            await asyncio.wait_for(self.turn(), timeout=2)
            await asyncio.sleep(0.2)
        self.assertNotIn("detail_saved", self.events)
        self.assertIn("lock_released", self.events)
        self.assertTrue(any("timeout" in line for line in logs.output))

    async def test_next_turn_and_end_session_wait_for_detail(self):
        self.c_gate.set()
        await self.turn("Giliran pertama")
        second = asyncio.create_task(self.turn("Giliran kedua"))
        await settle()
        self.assertEqual(self.events.count("load_state"), 1)
        self.assertFalse(second.done())

        self.detail_gate.set()
        await asyncio.wait_for(second, timeout=2)
        second_load = [i for i, e in enumerate(self.events) if e == "load_state"][1]
        self.assertLess(self.events.index("detail_saved"), second_load)

        await settle()
        end_task = asyncio.create_task(end_active_session(session_id=self.session_id, user=self.user, conn=self.conn))
        await asyncio.wait_for(end_task, timeout=2)
        last_detail = max(i for i, e in enumerate(self.events) if e == "detail_saved")
        self.assertLess(last_detail, self.events.index("end_session"))

    async def test_combined_mode_unchanged(self):
        self.settings.STATE_UPDATE_MODE = "combined"
        self.mock_combined.return_value = ClientState(emotion_type="Cemas", disclosure_level="medium", ambivalence_lean="both")
        self.c_gate.set()
        await self.turn()
        await settle()
        self.mock_combined.assert_awaited_once()
        self.assertNotIn("decision_started", self.events)
        self.assertNotIn("detail_started", self.events)
        self.assertFalse(self.b_kwargs["decision_only"])
        self.assertEqual(self.events[-1], "lock_released")


class TestStateAgents(BaseTestCase):
    def setUp(self):
        self.snap = self.get_sample_snapshot()
        self.cfg = MagicMock()
        self.cfg.GEMINI_MODEL_STATE_DECISION, self.cfg.GEMINI_THINKING_BUDGET_STATE_DECISION = "model-d", 0
        self.cfg.GEMINI_MODEL_STATE_DETAIL, self.cfg.GEMINI_THINKING_BUDGET_STATE_DETAIL = "model-r", 64

    def run_decision(self, result: StateDecision, previous_level: str = "medium"):
        llm = AsyncMock()
        llm.generate_json.return_value = result
        state = {**self.snap["initial_state"], "disclosure_level": previous_level}
        with patch("services.simulation.state_updater.get_settings", return_value=self.cfg), patch(
            "services.simulation.state_updater.get_gemini_client", return_value=llm
        ):
            out = self.run_async(update_client_state_decision("Halo", state, self.snap["persona"], self.snap["case"], []))
        return out, llm.generate_json.await_args.kwargs

    def test_decision_never_lowers_disclosure(self):
        out, kwargs = self.run_decision(decision("guarded"), previous_level="medium")
        self.assertEqual(out.disclosure_level, "medium")
        self.assertEqual((kwargs["model"], kwargs["thinking_budget"], kwargs["role"]), ("model-d", 0, "state_decision"))

    def test_decision_freezes_disclosure_on_discord(self):
        out, _ = self.run_decision(decision("high", discord=True), previous_level="medium")
        self.assertEqual(out.disclosure_level, "medium")

    def test_reason_fields_come_before_decisions(self):
        fields = list(StateDecision.model_fields)
        for reason, decided in (("disclosure_reason", "disclosure_level"), ("discord_reason", "discord_present"), ("ambivalence_reason", "ambivalence_lean")):
            self.assertLess(fields.index(reason), fields.index(decided))

    def test_detail_schema_cannot_carry_decisions(self):
        for name in ("disclosure_level", "discord_present", "ambivalence_lean"):
            self.assertNotIn(name, StateDetail.model_fields)

    def test_detail_clears_discord_fields_without_discord(self):
        llm = AsyncMock()
        llm.generate_json.return_value = DETAIL.model_copy(update={"discord_context": "x", "discord_response": "y"})
        decided = provisional_state(self.snap["initial_state"], decision())
        with patch("services.simulation.state_updater.get_settings", return_value=self.cfg), patch(
            "services.simulation.state_updater.get_gemini_client", return_value=llm
        ):
            out = self.run_async(
                update_client_state_detail("Halo", "Iya.", self.snap["initial_state"], decided, self.snap["persona"], self.snap["case"], [])
            )
        self.assertIsNone(out.discord_context)
        self.assertIsNone(out.discord_response)
        self.assertIn('Klien: "Iya."', llm.generate_json.await_args.kwargs["user_prompt"])

    def test_responder_split_prompt_and_facts_filter(self):
        llm = AsyncMock()
        llm.generate_text.return_value = "Iya."
        state = provisional_state(self.snap["initial_state"], decision("guarded", discord=True))
        facts = [{"code": "H1", "description": "Fakta sensitif", "min_disclosure_level": "medium"}]
        with patch("services.simulation.responder.get_gemini_client", return_value=llm):
            self.run_async(generate_client_response_llm(self.snap["persona"], self.snap["case"], state, [], [], "Halo", facts, decision_only=True))
            split_prompt = llm.generate_text.await_args.kwargs["user_prompt"]
            self.run_async(generate_client_response_llm(self.snap["persona"], self.snap["case"], self.snap["initial_state"], [], [], "Halo", []))
            combined_prompt = llm.generate_text.await_args.kwargs["user_prompt"]
        self.assertIn("- Emosi: Lega tapi ragu\n", split_prompt)
        self.assertIn("Konselor mengarahkan sepihak", split_prompt)  # discord_reason sebagai catatan Discord
        self.assertNotIn("Fakta sensitif", split_prompt)
        self.assertIn("(Tenggat kuliah dan kegiatan organisasi bertumpuk)", combined_prompt)


class TestUsageAndConfig(unittest.TestCase):
    def test_usage_recorded_per_role(self):
        sink: dict[str, dict[str, int]] = {}
        track_usage(sink)
        usage = MagicMock(prompt_token_count=120, candidates_token_count=30)
        _record_usage("state_decision", usage)
        _record_usage("state_decision", usage)
        _record_usage("B", MagicMock(prompt_token_count=None, candidates_token_count=5))
        self.assertEqual(sink["state_decision"]["input"], 240)
        self.assertEqual(sink["state_decision"]["output"], 60)
        self.assertEqual(sink["state_decision"]["calls"], 2)
        self.assertEqual((sink["B"]["input"], sink["B"]["output"], sink["B"]["calls"]), (0, 5, 1))

    def test_only_active_mode_roles_validated(self):
        s = MagicMock()
        s.STATE_UPDATE_MODE = "split"
        self.assertEqual(sorted(role_llm_configs(s)), ["B", "C", "state_decision", "state_detail"])
        s.STATE_UPDATE_MODE = "combined"
        self.assertEqual(sorted(role_llm_configs(s)), ["A", "B", "C"])
