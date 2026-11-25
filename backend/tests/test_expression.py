"""Ekspresi avatar dari emosi Client State: pemetaan kata kunci dan ikut di respons giliran."""
from __future__ import annotations

from services.simulation.expression import expression_for_emotion
from tests.base import BaseTestCase


class TestExpressionForEmotion(BaseTestCase):
    def test_basic_emotions(self):
        cases = {
            "Sedih dan kecewa pada diri sendiri": "sad",
            "cemas, takut mengecewakan teman": "anxious",
            "Kesal karena merasa dihakimi": "tense",
            "Lega dan sedikit berharap": "happy",
            "": "neutral",
            None: "neutral",
        }
        for emotion, expected in cases.items():
            self.assertEqual(expression_for_emotion(emotion), expected, emotion)

    def test_negation_not_happy(self):
        self.assertEqual(expression_for_emotion("tidak nyaman ditanya soal ayah"), "tense")
        self.assertEqual(expression_for_emotion("tidak tenang"), "anxious")
        self.assertEqual(expression_for_emotion("kurang yakin bisa berubah"), "anxious")

    def test_discord_overrides_emotion(self):
        # Contoh nyata client_state_log: konselor meremehkan usaha klien.
        self.assertEqual(expression_for_emotion("Kecewa dan sakit hati", discord_present=True), "tense")
        self.assertEqual(expression_for_emotion("Kecewa dan sakit hati"), "sad")
        self.assertEqual(expression_for_emotion("merasa tidak dihargai"), "tense")

    def test_mixed_uses_priority(self):
        self.assertEqual(expression_for_emotion("cemas dan kesal"), "tense")
        self.assertEqual(expression_for_emotion("lelah tapi lega"), "sad")
