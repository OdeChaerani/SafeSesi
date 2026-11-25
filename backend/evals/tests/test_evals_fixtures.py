"""Konsistensi fixture evals (Ilustrasi, CASAA) dengan aturan penghitungan dan prompt.

Tidak memanggil Gemini (LLM tiruan memakai kode dokumen/ahli apa adanya). Tes CASAA dilewati jika
fixture CASAA belum dibangun (fixture itu tidak di-commit karena hak cipta).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from miti_fixtures import FIXTURE_DIR, FixturesMissing, expert_frequencies, expert_volleys, fixture_input, load_set
from schemas.evaluation import BehaviorCodingOutput
from services.evaluation.miti_evaluator import run_evaluation

BACKEND = Path(__file__).resolve().parents[2]


def settings() -> Any:
    s = MagicMock()
    for role in ("BEHAVIOR_CODING", "GLOBAL_SCORING", "PROCESS_OBSERVATION", "FEEDBACK"):
        setattr(s, f"GEMINI_MODEL_{role}", "gemini-3.8-flash")
        setattr(s, f"GEMINI_THINKING_BUDGET_{role}", None)
    return s


class CodingOnlyLLM:
    """Behavior Coding Agent tiruan yang mengembalikan kode fixture apa adanya."""

    def __init__(self, fx: dict[str, Any]):
        self.fx = fx
        self.prompts: list[str] = []

    async def generate_json(self, model, system, user, schema, **kw):
        assert schema is BehaviorCodingOutput
        self.prompts.append(system + user)
        turns = []
        for t in self.fx["turns"]:
            if t["speaker"] != "counselor":
                continue
            units = [{"unit_no": i, "excerpt": t["content"][:30], "reason": "r", "code": c, "alternative_code": None,
                      "certain": True, "same_affirmation_as_turn": None, "uncertainty_note": None}
                     for i, c in enumerate(t["expected_codes"], start=1)]
            turns.append({"turn_no": t["turn_no"], "volley_reason": "r",
                          "continues_previous_volley": bool(t.get("same_as_previous_volley")), "units": units})
        return BehaviorCodingOutput.model_validate({"turns": turns})


async def coded(fx: dict[str, Any]):
    llm = CodingOnlyLLM(fx)
    res = await run_evaluation(fixture_input(fx), llm=llm, settings=settings(), agents={"behavior_coding"})
    return res, llm


def casaa_or_skip() -> list[dict[str, Any]]:
    try:
        return load_set("casaa")
    except FixturesMissing as exc:
        raise unittest.SkipTest(str(exc))


class TestIlustrasiFixtures(unittest.IsolatedAsyncioTestCase):
    async def test_frequencies_match_document_tables(self):
        fixtures = load_set("ilustrasi")
        self.assertEqual(len(fixtures), 5)
        for fx in fixtures:
            res, _ = await coded(fx)
            self.assertEqual(res.frequencies, fx["expected_frequencies"], fx["fixture_id"])

    def test_state_fixture_not_loaded_as_miti_fixture(self):
        self.assertTrue((FIXTURE_DIR / "ilustrasi" / "ilustrasi_state_sessions.json").exists())
        self.assertTrue(all(fx["fixture_id"].startswith("SS-") for fx in load_set("ilustrasi")))


class TestCasaaFixtures(unittest.IsolatedAsyncioTestCase):
    async def test_same_rows_merged_not_double_counted(self):  # MITI E.3
        fixtures = casaa_or_skip()
        self.assertEqual({f["fixture_id"] for f in fixtures}, {"casaa_smoker", "casaa_emmy", "casaa_cheryl"})
        for fx in fixtures:
            res, _ = await coded(fx)
            self.assertEqual(res.frequencies, expert_frequencies(fx), fx["fixture_id"])
            self.assertEqual([v[0] for v in res.debug["behavior_coding"]["volleys"]],
                             [v["head"] for v in expert_volleys(fx)])

    async def test_inline_expert_annotations_not_sent_to_evaluator(self):
        fx = next(f for f in casaa_or_skip() if f["fixture_id"] == "casaa_smoker")
        _, llm = await coded(fx)
        transcript = llm.prompts[0].split("Transcript:", 1)[1]  # referensi prompt sendiri memuat "Example (GI)"
        annotated = next(t for t in fx["turns"] if t.get("expert_units"))
        self.assertIn(annotated["content"], transcript)
        self.assertNotIn("(GI)", transcript)
        self.assertNotIn("(Emphasize)", transcript)


class TestPromptsDoNotContainFixtures(unittest.TestCase):
    """Isi fixture tidak boleh dipakai sebagai contoh di prompt (8 kata berurutan)."""

    @staticmethod
    def ngrams(text: str, n: int = 8) -> set[str]:
        words = re.findall(r"\w+", text.casefold())
        return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}

    def test_no_fixture_text_in_prompts(self):
        prompt_text = "\n".join(p.read_text(encoding="utf-8") for p in (BACKEND / "prompts" / "miti").glob("*.md"))
        prompt_text += (BACKEND / "prompts" / "prompt_evaluation.py").read_text(encoding="utf-8")
        prompt_grams = self.ngrams(prompt_text)
        sets = ["ilustrasi"] + (["casaa"] if list((FIXTURE_DIR / "casaa").glob("casaa_*.json")) else [])
        state = json.loads((FIXTURE_DIR / "ilustrasi" / "ilustrasi_state_sessions.json").read_text(encoding="utf-8"))
        texts = [" ".join(t["content"] for t in fx["turns"]) for s in sets for fx in load_set(s)]
        texts += [" ".join(t["counselor"] + " " + t["client"] for t in s["turns"]) for s in state["sessions"]]
        for text in texts:
            leaked = prompt_grams & self.ngrams(text)
            self.assertFalse(leaked, sorted(leaked)[:3])


if __name__ == "__main__":
    unittest.main()
