"""Logika pembanding di evals/scripts/compare_miti_fixtures.py (tanpa Gemini)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from compare_miti_fixtures import aggregate, compare_codes, compare_globals
from services.evaluation.miti_rules import FinalCode

FX = {
    "fixture_id": "x",
    "expected_globals": {"cultivating_change_talk": 3, "softening_sustain_talk": 3, "partnership": 5, "empathy": 5},
    "turns": [
        {"turn_no": 1, "speaker": "counselor", "content": "a", "expected_codes": ["SR", "Q"], "acceptable_alternatives": []},
        {"turn_no": 2, "speaker": "client", "content": "b"},
        {"turn_no": 3, "speaker": "counselor", "content": "c", "expected_codes": ["Q"], "acceptable_alternatives": ["SEEK"]},
        {"turn_no": 4, "speaker": "client", "content": "uh huh"},
        {"turn_no": 5, "speaker": "counselor", "content": "d", "expected_codes": [], "acceptable_alternatives": [],
         "same_as_previous_volley": True},
    ],
}


def code(turn_no: int, c: str) -> FinalCode:
    return FinalCode(turn_no, 1, c, "e", "r", None, turn_no)


class TestCompare(unittest.TestCase):
    def test_alternative_and_merged_volley_count_as_match(self):
        result = SimpleNamespace(codes=[code(1, "SR"), code(1, "Q"), code(5, "SEEK")])
        cmp = compare_codes(FX, result)
        self.assertEqual([v["match"] for v in cmp["volleys"]], [True, True])
        self.assertEqual(cmp["volleys"][1]["turns"], [3, 5])
        self.assertEqual(cmp["tp"], {"SR": 1, "Q": 2})

    def test_missing_and_extra_codes(self):
        result = SimpleNamespace(codes=[code(1, "CR"), code(3, "Q")])
        cmp = compare_codes(FX, result)
        self.assertEqual(cmp["fn"], {"SR": 1, "Q": 1})
        self.assertEqual(cmp["fp"], {"CR": 1})
        summary = aggregate([{"codes": cmp, "frequencies": {"system": {"CR": 1, "Q": 1}, "expert": {"SR": 1, "Q": 2}}}])
        self.assertEqual(summary["volley_exact_match"]["matched"], 1)
        self.assertEqual(summary["per_code"]["Q"]["recall"], 0.5)
        self.assertEqual(summary["per_code"]["CR"]["precision"], 0.0)
        self.assertEqual(summary["per_code"]["GI"]["precision"], "tidak dapat dihitung")

    def test_globals_exact_and_within_one(self):
        g = {d: {"score": s} for d, s in zip(FX["expected_globals"], (3, 4, 3, 5))}
        out = compare_globals(FX, SimpleNamespace(globals=g))
        self.assertEqual((out["exact"], out["within_1"], out["total"]), (2, 3, 4))


if __name__ == "__main__":
    unittest.main()
