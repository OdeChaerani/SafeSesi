from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

from api.sessions import create_new_session, send_counselor_turn
from repositories.scenarios import get_catalog_scenarios
from schemas.client_state import ClientState
from schemas.scenario import CatalogScenarioResponse
from schemas.session import CreateSessionRequest, CreateTurnRequest, SessionResponse
from services.simulation.disclosure import (
    enforce_disclosure_floor,
    filter_hidden_facts,
    resolve_disclosure,
    revealed_fact_codes,
)
from services.simulation.responder import generate_client_response_llm
from services.simulation.state_updater import update_client_state_llm
from tests.base import BaseTestCase

FACT_MEDIUM = {
    "code": "H1",
    "short_title": "Penilaian teman",
    "fact": "FAKTA-MEDIUM: khawatir dinilai teman bila membatasi tugas",
    "min_disclosure_level": "medium",
}
FACT_HIGH = {
    "code": "H4",
    "short_title": "Pengalaman bersama orang tua",
    "fact": "FAKTA-HIGH: pengalaman bersama orang tua soal tanggung jawab",
    "min_disclosure_level": "high",
}
FACT_MEDIUM_UNREVEALED = {
    "code": "H2",
    "short_title": "Komentar kurang kompak",
    "fact": "FAKTA-MEDIUM-BARU: pernah disebut kurang kompak",
    "min_disclosure_level": "medium",
}


def make_state(level: str, discord: bool = False) -> ClientState:
    return ClientState(
        emotion_type="Cemas",
        disclosure_level=level,
        ambivalence_lean="both",
        discord_present=discord,
    )


def make_fake_llm(state: ClientState | None = None, reply: str = "Iya, begitu.") -> AsyncMock:
    """LLM palsu: generate_json -> ClientState (Peran A), generate_text -> ucapan klien (Peran B)."""
    fake = AsyncMock()
    fake.generate_json.return_value = state
    fake.generate_text.return_value = reply
    return fake


def rina_snapshot() -> dict[str, Any]:
    """Skenario dengan disclosure awal 'medium' seperti Bu Rina (SS-RIN-01)."""
    return {
        "scenario": {
            "id": 3,
            "title": "Rina Kusumawati",
            "change_target": "Memulai aktivitas berjalan kaki secara bertahap",
        },
        "persona": {
            "name": "Rina Kusumawati",
            "age": 36,
            "gender": "Perempuan",
            "occupation": "Karyawan dan ibu",
            "personality": "Hangat tetapi mudah lelah",
            "communication_style": "Terbuka dan runtut",
        },
        "case": {
            "main_problem": "KASUS-1: ingin lebih aktif tetapi waktu terbatas",
            "history_impact": "KASUS-2: pola mulai lalu berhenti",
            "expectation_change_context": "KASUS-3: berjalan kaki bertahap",
            "health_condition": None,
            "initial_summary": "Bu Rina ingin lebih aktif bergerak di sela pekerjaan dan keluarga.",
        },
        "initial_state": {
            "emotion_type": "Berharap tetapi ragu",
            "disclosure_level": "medium",
            "ambivalence_lean": "both",
            "discord_present": False,
        },
        "hidden_facts": [
            {
                "code": "H1",
                "short_title": "Berjalan bersama anak",
                "fact": "RINA-H1: pernah berjalan santai bersama anak di akhir pekan",
                "min_disclosure_level": "medium",
            },
            {
                "code": "H3",
                "short_title": "Kecewa pola mulai-berhenti",
                "fact": "RINA-H3: rasa kecewa karena pola mulai lalu berhenti",
                "min_disclosure_level": "high",
            },
        ],
    }


class TestDisclosureFilterPure(BaseTestCase):
    """Fungsi murni filter fakta tersembunyi dan lantai disclosure."""

    def test_high_fact_excluded_at_medium_included_at_high(self):
        facts = [FACT_MEDIUM, FACT_HIGH]
        at_medium = filter_hidden_facts(facts, "medium", False, [])
        at_high = filter_hidden_facts(facts, "high", False, [])

        self.assertEqual([f["code"] for f in at_medium], ["H1"])
        self.assertEqual([f["code"] for f in at_high], ["H1", "H4"])

    def test_guarded_only_allows_guarded_facts(self):
        guarded_fact = {**FACT_MEDIUM, "code": "H0", "min_disclosure_level": "guarded"}
        result = filter_hidden_facts([guarded_fact, FACT_MEDIUM], "guarded", False, [])
        self.assertEqual([f["code"] for f in result], ["H0"])

    def test_missing_min_level_defaults_to_medium(self):
        legacy_fact = {"code": "H1", "fact": "fakta snapshot lama"}
        self.assertEqual(filter_hidden_facts([legacy_fact], "guarded", False, []), [])
        self.assertEqual(len(filter_hidden_facts([legacy_fact], "medium", False, [])), 1)

    def test_unknown_levels_fail_closed(self):
        self.assertEqual(filter_hidden_facts([FACT_MEDIUM], "sangat_terbuka", False, []), [])
        odd_fact = {**FACT_MEDIUM, "min_disclosure_level": "???"}
        self.assertEqual(filter_hidden_facts([odd_fact], "high", False, []), [])

    def test_discord_only_keeps_revealed_facts(self):
        notes = [
            {"hidden_fact_code": "H1", "description": "Klien menyebut takut dinilai teman."},
            {"hidden_fact_code": "H2", "description": "   "},
            {"hidden_fact_code": None, "description": "Catatan permasalahan utama"},
        ]
        self.assertEqual(revealed_fact_codes(notes), {"H1"})

        result = filter_hidden_facts(
            [FACT_MEDIUM, FACT_MEDIUM_UNREVEALED], "medium", True, notes
        )
        self.assertEqual([f["code"] for f in result], ["H1"])

        without_discord = filter_hidden_facts(
            [FACT_MEDIUM, FACT_MEDIUM_UNREVEALED], "medium", False, notes
        )
        self.assertEqual([f["code"] for f in without_discord], ["H1", "H2"])

    def test_enforce_disclosure_floor(self):
        self.assertEqual(enforce_disclosure_floor("medium", "guarded"), "medium")
        self.assertEqual(enforce_disclosure_floor("medium", "high"), "high")
        self.assertEqual(enforce_disclosure_floor("high", "high"), "high")
        self.assertEqual(enforce_disclosure_floor("medium", "tidak-valid"), "medium")

    def test_resolve_disclosure_locks_level_during_discord(self):
        self.assertEqual(resolve_disclosure("medium", "high", discord_present=True), "medium")
        self.assertEqual(resolve_disclosure("medium", "guarded", discord_present=True), "medium")
        self.assertEqual(resolve_disclosure("medium", "high", discord_present=False), "high")
        self.assertEqual(resolve_disclosure("high", "guarded", discord_present=False), "high")


class TestResponderHiddenFacts(BaseTestCase):
    """Peran B: isi prompt mengikuti filter fakta tersembunyi."""

    def _prompt_for(self, state: ClientState, facts, topic_notes=None) -> str:
        snapshot = self.get_sample_snapshot()
        fake_llm = make_fake_llm()
        with patch("services.simulation.responder.get_gemini_client", return_value=fake_llm):
            self.run_async(
                generate_client_response_llm(
                    persona=snapshot["persona"],
                    case_data=snapshot["case"],
                    new_state=state,
                    topic_notes=topic_notes or [],
                    transcript_history=[],
                    counselor_utterance="Apa lagi yang membuatmu ragu?",
                    hidden_facts=facts,
                )
            )
        return fake_llm.generate_text.call_args.kwargs["user_prompt"]

    def test_high_fact_not_in_prompt_at_medium(self):
        prompt = self._prompt_for(make_state("medium"), [FACT_MEDIUM, FACT_HIGH])
        self.assertIn("FAKTA-MEDIUM", prompt)
        self.assertNotIn("FAKTA-HIGH", prompt)
        self.assertNotIn("min_disclosure_level", prompt)

    def test_high_fact_in_prompt_at_high(self):
        prompt = self._prompt_for(make_state("high"), [FACT_MEDIUM, FACT_HIGH])
        self.assertIn("FAKTA-MEDIUM", prompt)
        self.assertIn("FAKTA-HIGH", prompt)

    def test_discord_blocks_unrevealed_fact_but_keeps_revealed(self):
        notes = [
            {
                "session_topic_id": 1,
                "topic_name": "Penilaian teman",
                "hidden_fact_code": "H1",
                "description": "Klien menyebut takut dinilai teman.",
            },
            {
                "session_topic_id": 2,
                "topic_name": "Komentar kurang kompak",
                "hidden_fact_code": "H2",
                "description": "",
            },
        ]
        prompt = self._prompt_for(
            make_state("high", discord=True),
            [FACT_MEDIUM, FACT_MEDIUM_UNREVEALED],
            topic_notes=notes,
        )
        self.assertIn("FAKTA-MEDIUM:", prompt)
        self.assertNotIn("FAKTA-MEDIUM-BARU", prompt)


class TestStateUpdaterDisclosureFloor(BaseTestCase):
    """Peran A: disclosure tidak turun walau LLM mengembalikan tingkat lebih rendah."""

    def _run(self, previous: str, llm_level: str, discord: bool = False) -> ClientState:
        snapshot = self.get_sample_snapshot()
        current = {**snapshot["initial_state"], "disclosure_level": previous}
        fake_llm = make_fake_llm(state=make_state(llm_level, discord=discord))
        with patch("services.simulation.state_updater.get_gemini_client", return_value=fake_llm):
            return self.run_async(
                update_client_state_llm(
                    counselor_utterance="Kamu harus keluar dari kepanitiaan.",
                    current_state=current,
                    persona=snapshot["persona"],
                    case_data=snapshot["case"],
                    transcript_history=[],
                )
            )

    def test_disclosure_not_lowered_and_warns(self):
        with self.assertLogs("safesesi.simulation.state", level="WARNING") as logs:
            result = self._run(previous="medium", llm_level="guarded")
        self.assertEqual(result.disclosure_level, "medium")
        self.assertEqual(result.emotion_type, "Cemas")  # field lain dari LLM tetap dipakai
        self.assertTrue(any("guarded" in line for line in logs.output))

    def test_disclosure_can_rise(self):
        result = self._run(previous="medium", llm_level="high")
        self.assertEqual(result.disclosure_level, "high")

    def test_discord_does_not_raise_disclosure(self):
        with self.assertLogs("safesesi.simulation.state", level="WARNING") as logs:
            result = self._run(previous="medium", llm_level="high", discord=True)
        self.assertEqual(result.disclosure_level, "medium")
        self.assertTrue(result.discord_present)
        self.assertTrue(any("Discord" in line for line in logs.output))

    def test_discord_does_not_lower_disclosure(self):
        result = self._run(previous="medium", llm_level="guarded", discord=True)
        self.assertEqual(result.disclosure_level, "medium")

    def test_discord_keeps_same_level_without_warning(self):
        with patch("services.simulation.state_updater.logger") as mock_logger:
            result = self._run(previous="high", llm_level="high", discord=True)
        self.assertEqual(result.disclosure_level, "high")
        mock_logger.warning.assert_not_called()


class TestFirstTurnMediumScenario(BaseTestCase):
    """Skenario dengan disclosure awal 'medium' (Bu Rina) tidak membocorkan fakta 'high' di giliran pertama."""

    @patch("services.simulation.orchestrator.update_topic_notes_llm")
    @patch("services.simulation.orchestrator.get_latest_client_state")
    @patch("services.simulation.orchestrator.get_latest_topic_notes")
    @patch("services.simulation.orchestrator.get_session_turns")
    @patch("services.simulation.orchestrator.save_turn")
    @patch("services.simulation.orchestrator.save_client_state")
    @patch("services.simulation.orchestrator.save_topic_note")
    @patch("services.simulation.orchestrator.get_next_turn_no")
    def test_rina_first_turn_no_high_fact(
        self,
        mock_next_no,
        mock_save_note,
        mock_save_state,
        mock_save_turn,
        mock_get_turns,
        mock_get_notes,
        mock_get_state,
        mock_notes_llm,
    ):
        snapshot = rina_snapshot()
        session = {**self.get_sample_session(session_id=300), "scenario_id": 3, "scenario_snapshot": snapshot}
        conn = self.create_mock_connection()
        conn.fetchrow.return_value = session

        mock_get_state.return_value = snapshot["initial_state"]
        mock_get_notes.return_value = [
            {"session_topic_id": 1, "topic_name": "Berjalan bersama anak", "hidden_fact_code": "H1", "description": ""},
            {"session_topic_id": 2, "topic_name": "Kecewa pola mulai-berhenti", "hidden_fact_code": "H3", "description": ""},
        ]
        mock_get_turns.return_value = []
        mock_next_no.return_value = 1
        mock_save_turn.side_effect = [10, 11]
        mock_notes_llm.return_value = []

        # LLM palsu mempertahankan 'medium' pada giliran pertama
        fake_llm = make_fake_llm(state=make_state("medium"), reply="Iya, saya ingin lebih aktif.")
        with patch("services.simulation.state_updater.get_gemini_client", return_value=fake_llm), patch(
            "services.simulation.responder.get_gemini_client", return_value=fake_llm
        ):
            res = self.run_async(
                send_counselor_turn(
                    session_id=300,
                    payload=CreateTurnRequest(content="Apa yang membuat Ibu ingin mulai bergerak lagi?"),
                    user=self.get_sample_user(user_id=10),
                    conn=conn,
                )
            )

        prompt_b = fake_llm.generate_text.call_args.kwargs["user_prompt"]
        self.assertIn("RINA-H1", prompt_b)
        self.assertNotIn("RINA-H3", prompt_b)
        self.assertEqual(res.content, "Iya, saya ingin lebih aktif.")
        self.assertIsNone(res.internal_state)


class TestPublicResponses(BaseTestCase):
    """Katalog/briefing dan respons sesi memuat initial_summary tanpa data internal."""

    INTERNAL_MARKERS = ("RINA-H1", "RINA-H3", "KASUS-1", "KASUS-2", "KASUS-3", "Hangat tetapi mudah lelah")

    def _assert_no_internal(self, payload: dict[str, Any]) -> None:
        dumped = json.dumps(payload, default=str)
        for key in ("hidden_facts", "persona", "case", "initial_state", "scenario_snapshot", "main_problem"):
            self.assertNotIn(f'"{key}"', dumped)
        for marker in self.INTERNAL_MARKERS:
            self.assertNotIn(marker, dumped)

    def test_catalog_briefing_has_initial_summary_without_hidden_facts(self):
        conn = self.create_mock_connection()
        conn.fetch.return_value = [
            {
                "id": 3,
                "title": "Rina Kusumawati",
                "change_target": "Memulai aktivitas berjalan kaki secara bertahap",
                "client_name": "Rina Kusumawati",
                "client_age": 36,
                "client_gender": "Perempuan",
                "client_role": "Karyawan dan ibu",
                "initial_summary": rina_snapshot()["case"]["initial_summary"],
                "total_attempts": 0,
                "attempt_status": "unattempted",
                "last_completed_session_id": None,
                "active_session_id": None,
            }
        ]
        raw = self.run_async(get_catalog_scenarios(conn, student_id=10, search="aktif bergerak"))
        sql = conn.fetch.call_args.args[0]
        self.assertIn("c.initial_summary", sql)
        self.assertNotIn("c.main_problem", sql)

        body = CatalogScenarioResponse.model_validate(raw).model_dump(mode="json")
        self.assertEqual(len(body["items"]), 1)  # pencarian bekerja via initial_summary
        self.assertEqual(
            body["items"][0]["initial_summary"],
            "Bu Rina ingin lebih aktif bergerak di sela pekerjaan dan keluarga.",
        )
        self._assert_no_internal(body)

    @patch("api.sessions.get_scenario_by_id")
    @patch("api.sessions.build_scenario_snapshot")
    @patch("api.sessions.create_session")
    @patch("api.sessions.create_session_topics_from_snapshot")
    @patch("api.sessions.save_client_state")
    @patch("api.sessions.save_topic_note")
    def test_create_session_response_hides_snapshot(
        self, mock_save_note, mock_save_state, mock_topics, mock_create, mock_snap, mock_get_scen
    ):
        snapshot = rina_snapshot()
        mock_get_scen.return_value = {"id": 3, "visibility": "catalog"}
        mock_snap.return_value = snapshot
        mock_create.return_value = {
            "id": 301,
            "student_id": 10,
            "scenario_id": 3,
            "class_id": None,
            "parent_session_id": None,
            "scenario_snapshot": snapshot,
            "status": "in_progress",
            "started_at": "2026-11-12T10:00:00Z",
            "ended_at": None,
            "duration_seconds": None,
        }
        mock_topics.return_value = []

        raw = self.run_async(
            create_new_session(
                payload=CreateSessionRequest(scenario_id=3, mode="new"),
                user=self.get_sample_user(user_id=10),
                conn=self.create_mock_connection(),
            )
        )
        body = SessionResponse.model_validate(raw).model_dump(mode="json")
        self.assertEqual(body["scenario"]["initial_summary"], snapshot["case"]["initial_summary"])
        self.assertEqual(body["scenario"]["client_name"], "Rina Kusumawati")
        self._assert_no_internal(body)
