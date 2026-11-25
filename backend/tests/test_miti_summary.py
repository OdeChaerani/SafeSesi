"""Ukuran ringkasan MITI 4.2.1 bagian H dan penyebut nol (Rubrik 2.4)."""
from __future__ import annotations

import unittest

from services.evaluation.summary import NOT_ASSESSED, NOT_COMPUTABLE, REFERENCE_THRESHOLDS, reference_band, summary_measures

GLOBALS = {"cultivating_change_talk": 4, "softening_sustain_talk": 3, "partnership": 4, "empathy": 5}


class TestSummaryMeasures(unittest.TestCase):
    def test_formulas(self):
        freq = {"SR": 1, "CR": 2, "Q": 3, "AF": 1, "SEEK": 1, "EA": 1, "P": 2, "CONFRONT": 1, "PWP": 4}
        m = summary_measures(freq, GLOBALS)
        self.assertEqual(m["technical_global"]["value"], 3.5)
        self.assertEqual(m["relational_global"]["value"], 4.5)
        self.assertEqual(m["pct_complex_reflection"]["value"], 66.67)
        self.assertEqual(m["reflection_question_ratio"]["value"], 1.0)
        self.assertEqual(m["total_mia"]["value"], 3)
        self.assertEqual(m["total_mina"]["value"], 3)  # PWP tidak masuk MIA/MINA

    def test_no_reflections_pct_cr_not_computable(self):
        m = summary_measures({"Q": 2}, GLOBALS)
        self.assertIsNone(m["pct_complex_reflection"]["value"])
        self.assertEqual(m["pct_complex_reflection"]["label"], NOT_COMPUTABLE)
        self.assertEqual(m["pct_complex_reflection"]["counts"], {"SR": 0, "CR": 0})

    def test_no_questions_rq_not_computable_with_raw_counts(self):
        m = summary_measures({"SR": 2, "CR": 1}, GLOBALS)
        self.assertIsNone(m["reflection_question_ratio"]["value"])
        self.assertEqual(m["reflection_question_ratio"]["label"], NOT_COMPUTABLE)
        self.assertEqual(m["reflection_question_ratio"]["counts"], {"SR": 2, "CR": 1, "Q": 0})

    def test_missing_globals_not_assessed(self):  # sesi <= 5 menit
        m = summary_measures({"SR": 1, "Q": 1}, None)
        self.assertEqual(m["technical_global"]["label"], NOT_ASSESSED)
        self.assertIsNone(m["relational_global"]["value"])
        self.assertEqual(m["reflection_question_ratio"]["value"], 1.0)

    def test_zero_counts_are_frequencies_not_errors(self):
        m = summary_measures({}, GLOBALS)
        self.assertEqual((m["total_mia"]["value"], m["total_mina"]["value"]), (0, 0))

    def test_reference_band_boundaries(self):  # ambang inklusif: tepat di ambang masuk band itu
        t = REFERENCE_THRESHOLDS["relational_global"]
        self.assertEqual(reference_band(4, t), "baik")
        self.assertEqual(reference_band(3.5, t), "cukup")
        self.assertEqual(reference_band(3.49, t), "di_bawah_acuan")
        self.assertIsNone(reference_band(None, t))

    def test_reference_fields_on_thresholded_measures_only(self):
        m = summary_measures({"SR": 2, "CR": 1}, None)  # Q = 0, global tidak dinilai
        self.assertIsNone(m["reflection_question_ratio"]["reference_band"])
        self.assertEqual(m["reflection_question_ratio"]["reference_thresholds"], {"cukup": 1, "baik": 2})
        self.assertIsNone(m["technical_global"]["reference_band"])
        self.assertEqual(m["pct_complex_reflection"]["reference_band"], "di_bawah_acuan")  # 33,33%
        self.assertNotIn("reference_band", m["total_mia"])


if __name__ == "__main__":
    unittest.main()
