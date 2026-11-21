"""Penjamin panjang ucapan klien (Peran B): maksimal 3 kalimat dan 40 kata, dipotong di akhir kalimat."""
from __future__ import annotations

from services.simulation.responder import limit_reply
from tests.base import BaseTestCase


class TestLimitReply(BaseTestCase):
    def test_short_reply_unchanged(self):
        text = "Pagi, Kak. Kabar saya... ya lumayan, meski agak capek."
        self.assertEqual(limit_reply(text), text)  # "saya... ya" bukan batas kalimat

    def test_max_three_sentences(self):
        self.assertEqual(limit_reply("Iya. Benar. Saya setuju. Tapi susah."), "Iya. Benar. Saya setuju.")

    def test_word_limit_cuts_at_sentence(self):
        first = " ".join(["kata"] * 30) + "."
        second = "Ini " + " ".join(["lagi"] * 15) + "."
        self.assertEqual(limit_reply(f"{first} {second}"), first)

    def test_single_long_sentence_cut_by_words(self):
        reply = limit_reply(" ".join(["panjang"] * 50) + ".")
        self.assertEqual(len(reply.split()), 40)
        self.assertTrue(reply.endswith("…"))
