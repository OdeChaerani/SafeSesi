"""Aturan penghitungan MITI 4.2.1 (langkah 2) — tanpa LLM."""
from __future__ import annotations

import unittest
from typing import Any

from schemas.evaluation import BehaviorCodingOutput, CodedUnit
from services.evaluation.miti_rules import CodingValidationError, apply_rules, resolve_unit


def unit(code: str | None, alt: str | None = None, certain: bool = True, n: int = 1, same_af: int | None = None) -> dict[str, Any]:
    return {"unit_no": n, "excerpt": f"unit {n}", "reason": "r", "code": code, "alternative_code": alt,
            "certain": certain, "same_affirmation_as_turn": same_af, "uncertainty_note": None}


def turn(turn_no: int, *units: dict[str, Any], cont: bool = False) -> dict[str, Any]:
    numbered = [{**u, "unit_no": i} for i, u in enumerate(units, start=1)]
    return {"turn_no": turn_no, "volley_reason": "r", "continues_previous_volley": cont, "units": numbered}


def coding(*turns: dict[str, Any]) -> BehaviorCodingOutput:
    return BehaviorCodingOutput.model_validate({"turns": list(turns)})


def resolved(code, alt=None, certain=True):
    return resolve_unit(CodedUnit.model_validate(unit(code, alt, certain)))[0]


def volley_codes(*units: dict[str, Any]) -> list[str]:
    res = apply_rules(coding(turn(1, *units)), [1])
    return sorted(c.code for c in res.codes)


class TestResolveUnit(unittest.TestCase):
    """Satu unit = satu kode (E.1.a); aturan prioritas antarkode yang tumpang tindih."""

    def test_null_code_is_not_coded(self):  # F
        self.assertIsNone(resolved(None))

    def test_uncertain_affirm_without_alternative_not_coded(self):  # E.4.f.2
        self.assertIsNone(resolved("AF", certain=False))
        self.assertEqual(resolved("AF", certain=True), "AF")

    def test_p_and_pwp_same_unit_gives_pwp(self):  # E.4.c.1
        self.assertEqual(resolved("P", "PWP"), "PWP")

    def test_confront_trumps_persuade_question_reflection(self):  # E.4.g.3, E.4.g.2
        for other in ("P", "Q", "SR", "CR"):
            self.assertEqual(resolved(other, "CONFRONT"), "CONFRONT", other)

    def test_affirm_trumps_reflection(self):  # E.4.f.2
        self.assertEqual(resolved("CR", "AF"), "AF")

    def test_mia_pyramid_certain_takes_higher(self):  # E.4.f.1
        self.assertEqual(resolved("SEEK", "EA"), "EA")
        self.assertEqual(resolved("AF", "SEEK"), "SEEK")

    def test_mia_pyramid_uncertain_takes_lower(self):  # E.4.f.1
        self.assertEqual(resolved("EA", "SEEK", certain=False), "SEEK")
        self.assertEqual(resolved("SEEK", "AF", certain=False), "AF")

    def test_uncertain_mia_vs_other_takes_other(self):  # E.4.f.1.a, FAQ 9
        self.assertEqual(resolved("SEEK", "Q", certain=False), "Q")
        self.assertEqual(resolved("AF", "CR", certain=False), "CR")

    def test_uncertain_sr_cr_gives_sr(self):  # E.4.e.2
        self.assertEqual(resolved("CR", "SR", certain=False), "SR")

    def test_uncertain_persuasion_vs_gi_gives_gi(self):  # E.4.b, E.4.c
        self.assertEqual(resolved("P", "GI", certain=False), "GI")
        self.assertEqual(resolved("PWP", "GI", certain=False), "GI")

    def test_uncertain_confront_vs_persuade_gives_p(self):  # pengisian celah E.4.g.3
        self.assertEqual(resolved("CONFRONT", "P", certain=False), "P")

    def test_uncertain_confront_vs_reflection_not_coded(self):  # E.4.g.2
        self.assertIsNone(resolved("CONFRONT", "SR", certain=False))
        self.assertIsNone(resolved("CR", "CONFRONT", certain=False))

    def test_uncertain_confront_vs_question_gives_q(self):  # E.4.g.2
        self.assertEqual(resolved("CONFRONT", "Q", certain=False), "Q")


class TestVolleyRules(unittest.TestCase):
    def test_one_question_per_volley(self):  # E.4.d
        self.assertEqual(volley_codes(unit("Q"), unit("Q"), unit("Q")), ["Q"])

    def test_one_reflection_cr_wins(self):  # E.1.a, E.4.e.3
        self.assertEqual(volley_codes(unit("SR"), unit("EA"), unit("CR")), ["CR", "EA"])
        self.assertEqual(volley_codes(unit("SR"), unit("SR")), ["SR"])

    def test_reflection_and_question_both_coded(self):  # E.4.e.4
        self.assertEqual(volley_codes(unit("CR"), unit("Q")), ["CR", "Q"])

    def test_p_and_pwp_in_different_units_gives_pwp(self):  # pengisian celah, perluasan E.4.c.1
        self.assertEqual(volley_codes(unit("P"), unit("PWP")), ["PWP"])
        self.assertEqual(volley_codes(unit("PWP"), unit("P")), ["PWP"])

    def test_pwp_with_explicit_autonomy_codes_both(self):  # E.4.c
        self.assertEqual(volley_codes(unit("EA"), unit("PWP")), ["EA", "PWP"])

    def test_each_code_once_per_volley(self):  # E.1.a
        self.assertEqual(volley_codes(unit("GI"), unit("GI"), unit("AF"), unit("AF")), ["AF", "GI"])

    def test_maximum_eight_codes(self):  # E.1.a
        all_codes = ["GI", "P", "PWP", "Q", "SR", "CR", "AF", "SEEK", "EA", "CONFRONT"]
        self.assertEqual(len(volley_codes(*(unit(c) for c in all_codes))), 8)

    def test_final_units_numbered_uniquely(self):
        res = apply_rules(coding(turn(1, unit(None), unit("SR"), unit("Q"))), [1])
        self.assertEqual([(c.unit_no, c.code) for c in res.codes], [(1, "SR"), (2, "Q")])


class TestFacilitativeVolleys(unittest.TestCase):
    """E.3: ujaran klien fasilitatif tidak memutus volley."""

    def test_continuation_merges_into_previous_volley(self):
        res = apply_rules(coding(turn(1, unit("CR")), turn(3, unit("CR"), unit("Q"), cont=True), turn(5, unit("SR"))), [1, 3, 5])
        self.assertEqual(res.volleys, [[1, 3], [5]])
        self.assertEqual(sorted((c.turn_no, c.code) for c in res.codes), [(1, "CR"), (1, "Q"), (5, "SR")])
        self.assertEqual(res.frequencies["CR"], 1)
        q = next(c for c in res.codes if c.code == "Q")
        self.assertEqual((q.unit_no, q.source_turn_no), (2, 3))

    def test_first_turn_cannot_continue(self):
        res = apply_rules(coding(turn(1, unit("Q"), cont=True)), [1])
        self.assertEqual(res.volleys, [[1]])


class TestThreeStrikes(unittest.TestCase):
    """E.4.f.2.a, adaptasi: afirmasi yang sama dikode paling banyak 3 kali."""

    def test_fourth_repeat_of_same_affirmation_dropped(self):
        turns = [turn(1, unit("AF"))] + [turn(n, unit("AF", same_af=n - 2)) for n in (3, 5, 7, 9)]
        res = apply_rules(coding(*turns), [1, 3, 5, 7, 9])
        self.assertEqual([c.turn_no for c in res.codes], [1, 3, 5])
        dropped = [u for u in res.debug["units"] if not u["kept"]]
        self.assertTrue(all("E.4.f.2.a" in u["drop_rule"] for u in dropped))

    def test_different_affirmations_not_limited(self):
        res = apply_rules(coding(*(turn(n, unit("AF")) for n in (1, 3, 5, 7, 9))), [1, 3, 5, 7, 9])
        self.assertEqual(res.frequencies["AF"], 5)


class TestValidation(unittest.TestCase):
    def test_missing_counselor_turn_rejected(self):
        with self.assertRaises(CodingValidationError):
            apply_rules(coding(turn(1, unit("Q"))), [1, 3])

    def test_client_turn_rejected(self):
        with self.assertRaises(CodingValidationError):
            apply_rules(coding(turn(1, unit("Q")), turn(2, unit("SR"))), [1])

    def test_debug_keeps_before_and_after(self):
        res = apply_rules(coding(turn(1, unit("SR"), unit("CR"))), [1])
        units = res.debug["units"]
        self.assertEqual([u["llm_code"] for u in units], ["SR", "CR"])
        self.assertEqual([u["kept"] for u in units], [False, True])
        self.assertEqual(set(res.frequencies), {"GI", "P", "PWP", "Q", "SR", "CR", "AF", "SEEK", "EA", "CONFRONT"})


if __name__ == "__main__":
    unittest.main()
