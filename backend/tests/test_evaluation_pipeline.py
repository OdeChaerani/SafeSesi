"""Pipeline evaluasi MITI dengan Gemini di-mock (tidak ada panggilan Gemini sungguhan).

Memakai fixture kecil buatan sendiri (tests/fixtures/miti_small_session.json), bukan fixture
Ilustrasi/CASAA di backend/evals/.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from api.evaluations import build_input
from repositories.evaluations import save_evaluation_results
from schemas.evaluation import (
    BehaviorCodingOutput,
    FeedbackOutput,
    GlobalScoringOutput,
    ProcessObservationOutput,
)
from services.evaluation.miti_evaluator import EvaluationError, EvaluationInput, excerpt_matches, run_evaluation
from services.llm.gemini_client import _record_usage

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "miti_small_session.json").read_text(encoding="utf-8"))


def settings() -> Any:
    s = MagicMock()
    for role in ("BEHAVIOR_CODING", "GLOBAL_SCORING", "PROCESS_OBSERVATION", "FEEDBACK"):
        setattr(s, f"GEMINI_MODEL_{role}", "gemini-3.8-flash")
        setattr(s, f"GEMINI_THINKING_BUDGET_{role}", None)
    return s


def fixture_input(fx: dict[str, Any], duration: int | None = None) -> EvaluationInput:
    return EvaluationInput(
        turns=[{k: t[k] for k in ("turn_no", "speaker", "content")} for t in fx["turns"]],
        change_target=fx["change_target"],
        initial_summary=fx["initial_summary"],
        duration_seconds=fx["duration_seconds"] if duration is None else duration,
        label=fx["fixture_id"],
    )


def coding_from_expected(fx: dict[str, Any]) -> dict[str, Any]:
    """Keluaran Behavior Coding Agent tiruan: satu unit per kode yang diharapkan."""
    turns = []
    for t in fx["turns"]:
        if t["speaker"] != "counselor":
            continue
        units = [
            {"unit_no": i, "excerpt": t["content"][:30], "reason": "r", "code": c, "alternative_code": None,
             "certain": True, "same_affirmation_as_turn": None, "uncertainty_note": None}
            for i, c in enumerate(t["expected_codes"], start=1)
        ]
        turns.append({"turn_no": t["turn_no"], "volley_reason": "r",
                      "continues_previous_volley": bool(t.get("same_as_previous_volley")), "units": units})
    return {"turns": turns}


def globals_output(score: int = 4, evidence: list[int] | None = None) -> dict[str, Any]:
    rating = {"reason": "alasan", "evidence_turn_nos": evidence or [1], "score": score}
    return {d: rating for d in ("cultivating_change_talk", "softening_sustain_talk", "partnership", "empathy")}


def process_output() -> dict[str, Any]:
    return {"observations": [
        {"process": "engaging", "reason": "r", "evidence_found": True, "start_turn_no": 3, "end_turn_no": 4, "excerpt": "x"},
        {"process": "planning", "reason": "r", "evidence_found": False, "start_turn_no": None, "end_turn_no": None, "excerpt": None},
    ]}


def feedback_item(turn_no: int, excerpt: str, kind: str = "strength", alt: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "turn_no": turn_no, "evidence_turn_nos": [turn_no + 1], "excerpt": excerpt,
            "explanation": "penjelasan", "alternative_text": alt}


K3 = FIXTURE["turns"][2]["content"]


class FakeLLM:
    """generate_json tiruan: jawaban per skema (daftar = jawaban berurutan per panggilan)."""

    def __init__(self, answers: dict[type, Any]):
        self.answers = {k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()}
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, model, system, user, schema, temperature=0.2, thinking_budget=0, role=None):
        self.calls.append({"role": role, "system": system, "user": user, "schema": schema, "budget": thinking_budget})
        _record_usage(role, MagicMock(prompt_token_count=100, candidates_token_count=10, thoughts_token_count=5))
        queue = self.answers[schema]
        data = queue.pop(0) if len(queue) > 1 else queue[0]
        return schema.model_validate(data)

    def roles(self) -> list[str]:
        return [c["role"] for c in self.calls]


def full_llm(feedback: Any = None) -> FakeLLM:
    return FakeLLM({
        BehaviorCodingOutput: coding_from_expected(FIXTURE),
        GlobalScoringOutput: globals_output(),
        ProcessObservationOutput: process_output(),
        FeedbackOutput: feedback or {"items": [
            feedback_item(3, K3[:20]),
            feedback_item(3, K3[:20], "alternative_response", "Coba katakan ini."),
        ]},
    })


async def evaluate(llm: FakeLLM, duration: int | None = None, **kw) -> Any:
    return await run_evaluation(fixture_input(FIXTURE, duration), llm=llm, settings=settings(), **kw)


class TestPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_frequencies_and_facilitative_volley_merge(self):  # E.1.a, E.3
        res = await evaluate(full_llm())
        self.assertEqual(res.frequencies, FIXTURE["expected_frequencies"])
        self.assertIn([5, 7], res.debug["behavior_coding"]["volleys"])
        self.assertEqual(res.agents_run, ["behavior_coding", "global_scoring", "process_observation", "feedback"])

    async def test_hidden_facts_from_session_never_in_prompts(self):  # Rubrik 3.2
        session = {
            "id": 1, "duration_seconds": FIXTURE["duration_seconds"],
            "scenario_snapshot": {
                "scenario": {"change_target": FIXTURE["change_target"]},
                "case": {"initial_summary": FIXTURE["initial_summary"]},
                "hidden_facts": FIXTURE["hidden_facts"],
            },
        }
        inp = build_input(session, [{**t, "id": t["turn_no"]} for t in FIXTURE["turns"]])
        llm = full_llm()
        await run_evaluation(inp, llm=llm, settings=settings())
        prompts = "\n".join(c["system"] + c["user"] for c in llm.calls)
        self.assertNotIn(FIXTURE["hidden_facts"][0]["fact"], prompts)
        self.assertIn(FIXTURE["change_target"], llm.calls[0]["user"])

    async def test_global_scoring_does_not_receive_behavior_codes(self):  # MITI B, D
        llm = full_llm()
        await evaluate(llm)
        gs = next(c for c in llm.calls if c["role"] == "global_scoring")
        self.assertNotIn("behavior_codes_per_turn", gs["user"])
        fb = next(c for c in llm.calls if c["role"] == "feedback")
        self.assertIn("behavior_codes_per_turn", fb["user"])

    async def test_thinking_override_and_metrics(self):
        llm = full_llm()
        res = await evaluate(llm, thinking_budget_override=0)
        self.assertTrue(all(c["budget"] == 0 for c in llm.calls))
        self.assertEqual(res.metrics["behavior_coding"]["calls"], 1)
        self.assertEqual(res.metrics["behavior_coding"]["input_tokens"], 100)
        self.assertIn("thinking=0", res.model_version)

    async def test_agents_subset(self):
        llm = full_llm()
        await evaluate(llm, agents={"behavior_coding"})
        self.assertEqual(llm.roles(), ["behavior_coding"])
        with self.assertRaises(ValueError):
            await evaluate(llm, agents={"feedback"})

    async def test_unknown_duration_skips_duration_rules(self):
        inp = fixture_input(FIXTURE)
        inp.duration_seconds = None
        res = await run_evaluation(inp, llm=full_llm(), settings=settings())
        self.assertEqual(res.limitation_notes, [])

    async def test_no_counselor_turns_fails(self):
        inp = EvaluationInput(turns=[{"turn_no": 1, "speaker": "client", "content": "halo"}], change_target="x")
        with self.assertRaises(EvaluationError):
            await run_evaluation(inp, llm=FakeLLM({}), settings=settings())


class TestDurationRules(unittest.IsolatedAsyncioTestCase):
    async def test_five_minutes_or_less_only_behavior_coding(self):  # Rubrik 2.1
        llm = full_llm()
        res = await evaluate(llm, duration=300)
        self.assertEqual(llm.roles(), ["behavior_coding"])
        self.assertIsNone(res.globals)
        self.assertIsNone(res.processes)
        self.assertIsNone(res.feedback)
        self.assertIn("≤ 5 menit", res.limitation_notes[0])
        self.assertEqual(res.agents_run, ["behavior_coding"])

    async def test_under_ten_minutes_scored_with_limitation(self):  # Rubrik 2.1, MITI FAQ 1
        llm = full_llm()
        res = await evaluate(llm, duration=301)
        self.assertIn("global_scoring", llm.roles())
        self.assertIsNotNone(res.globals)
        self.assertIn("< 10 menit", res.limitation_notes[0])

    async def test_ten_minutes_no_limitation(self):
        res = await evaluate(full_llm(), duration=600)
        self.assertEqual(res.limitation_notes, [])


class TestAgentOutputValidation(unittest.IsolatedAsyncioTestCase):
    async def test_feedback_retried_once_then_valid(self):
        bad = {"items": [feedback_item(3, "kutipan karangan")]}
        good = {"items": [feedback_item(3, K3[:25])]}
        llm = full_llm(feedback=[bad, good])
        res = await evaluate(llm)
        self.assertEqual(llm.roles().count("feedback"), 2)
        retry = [c for c in llm.calls if c["role"] == "feedback"][1]
        self.assertIn("tidak ditemukan di T3", retry["user"])
        self.assertEqual(len(res.feedback), 1)

    async def test_invalid_items_dropped_after_retry(self):
        mixed = {"items": [feedback_item(3, K3[:25]), feedback_item(4, "x", "alternative_response", "Coba ini.")]}
        res = await evaluate(full_llm(feedback=[mixed, mixed]))
        self.assertEqual([f["kind"] for f in res.feedback], ["strength"])
        self.assertIn("giliran klien", res.debug["feedback"]["dropped"][0])

    async def test_all_feedback_invalid_fails(self):
        bad = {"items": [feedback_item(3, "tidak ada di transkrip")]}
        with self.assertRaises(EvaluationError):
            await evaluate(full_llm(feedback=bad))

    async def test_alternative_response_content_is_concrete_sentence(self):
        res = await evaluate(full_llm())
        alt = next(f for f in res.feedback if f["kind"] == "alternative_response")
        self.assertEqual(alt["content"], "Coba katakan ini.")
        self.assertEqual(alt["explanation"], "penjelasan")  # penjelasan tidak dibuang

    async def test_alternative_response_explanation_saved_to_db(self):
        res = await evaluate(full_llm())
        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=False)))
        turn_ids = {t["turn_no"]: 100 + t["turn_no"] for t in FIXTURE["turns"]}
        await save_evaluation_results(conn, 7, res, turn_ids, 700)
        rows = next(c.args[1] for c in conn.executemany.call_args_list if "INSERT INTO feedback_items" in c.args[0])
        by_kind = {r[1]: r for r in rows}
        self.assertEqual(by_kind["alternative_response"][7], "penjelasan")
        self.assertIsNone(by_kind["strength"][7])  # penjelasan jenis lain sudah ada di content

    async def test_global_score_out_of_range_fails(self):
        llm = full_llm()
        llm.answers[GlobalScoringOutput] = [globals_output(score=6)]
        with self.assertRaises(EvaluationError):
            await evaluate(llm)

    async def test_missing_processes_recorded_as_insufficient_evidence(self):
        res = await evaluate(full_llm())
        by_proc = {p["process"]: p for p in res.processes}
        self.assertEqual(set(by_proc), {"engaging", "focusing", "evoking", "planning"})
        self.assertFalse(by_proc["focusing"]["evidence_found"])
        self.assertIsNone(by_proc["planning"]["start_turn_no"])

    def test_excerpt_matching_normalized(self):
        content = "Bapak ingin tetap sehat, walau TOKO sering ramai di malam hari."
        self.assertTrue(excerpt_matches("bapak ingin tetap sehat walau toko sering ramai", content))
        self.assertTrue(excerpt_matches("Bapak ingin … di malam hari", content))
        self.assertFalse(excerpt_matches("di malam hari … bapak ingin", content))
        self.assertFalse(excerpt_matches("", content))


if __name__ == "__main__":
    unittest.main()
