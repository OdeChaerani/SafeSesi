"""Ekspresi wajah avatar dari Client State: discord_present dan emotion_type (teks bebas dari Peran A).

Hanya label kasar ini yang dikirim ke frontend; teks emosi dan field Client State lain tidak.
Pemetaan deterministik berbasis kata kunci; urutan menentukan prioritas untuk emosi campuran
(mis. "cemas dan kesal" -> tense).
"""
from __future__ import annotations

from schemas.session import Expression

# shortcut: daftar kata kunci, bukan klasifikasi semantik; tambah kata bila log menunjukkan emosi yang jatuh ke neutral.
_KEYWORDS: tuple[tuple[Expression, tuple[str, ...]], ...] = (
    ("tense", ("marah", "kesal", "jengkel", "frustrasi", "frustasi", "defensif", "tersinggung", "terganggu",
               "tidak nyaman", "kurang nyaman", "tidak senang", "tidak dihargai", "diremehkan", "dipojokkan", "dihakimi", "diserang", "angry", "annoyed", "defensive", "irritat")),
    ("sad", ("sedih", "kecewa", "sakit hati", "terluka", "putus asa", "bersalah", "malu", "hampa", "lelah", "capek", "tertekan",
             "terpuruk", "kesepian", "sad", "guilt", "ashamed", "hopeless", "exhausted")),
    ("anxious", ("cemas", "khawatir", "takut", "gelisah", "tegang", "panik", "bingung", "ragu", "waswas",
                 "was-was", "tidak tenang", "tidak yakin", "kurang yakin", "kewalahan", "ambivalen", "anxious", "worried", "afraid", "nervous", "overwhelm")),
    ("happy", ("lega", "senang", "bahagia", "bersyukur", "berharap", "harapan", "optimis", "semangat",
               "termotivasi", "yakin", "tenang", "nyaman", "relieved", "happy", "hopeful", "motivated", "calm")),
)


def expression_for_emotion(emotion: str | None, discord_present: bool = False) -> Expression:
    # Ketegangan hubungan lebih menentukan raut wajah daripada kata emosinya
    # (mis. "kecewa dan sakit hati" saat konselor menghakimi -> tegang, bukan sekadar sedih).
    if discord_present:
        return "tense"
    text = (emotion or "").lower()
    # Negasi ("tidak nyaman", "tidak tenang") ada di kategori yang dicek sebelum happy.
    for expression, words in _KEYWORDS:
        if any(w in text for w in words):
            return expression
    return "neutral"
