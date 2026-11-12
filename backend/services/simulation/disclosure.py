"""Aturan keterbukaan (Disclosure) klien virtual — fungsi murni tanpa I/O.

Acuan: BRD SafeSesi Lampiran 1–2 dan Ilustrasi Sesi final:
- Fakta tersembunyi hanya boleh diungkap bila tingkat Disclosure saat ini
  sama dengan atau lebih tinggi dari tingkat minimal fakta tersebut.
- Disclosure tidak menurun selama sesi.
- Ketika Discord tampak, klien tidak mengungkapkan informasi tersembunyi baru.
"""

from __future__ import annotations

from typing import Any, Iterable

# DEFAULT_MIN_DISCLOSURE_LEVEL juga dipakai untuk snapshot lama yang dibuat
# sebelum kolom min_disclosure_level ada.
from schemas.scenario import DEFAULT_MIN_DISCLOSURE_LEVEL

DISCLOSURE_ORDER: dict[str, int] = {"guarded": 0, "medium": 1, "high": 2}


def disclosure_rank(level: Any) -> int | None:
    """Urutan tingkat keterbukaan; None jika nilainya tidak dikenal."""
    if not isinstance(level, str):
        return None
    return DISCLOSURE_ORDER.get(level.strip().lower())


def revealed_fact_codes(topic_notes: Iterable[dict[str, Any]]) -> set[str]:
    """Kode fakta yang sudah terungkap: topik hidden fact dengan catatan terbaru tidak kosong."""
    codes: set[str] = set()
    for note in topic_notes:
        code = note.get("hidden_fact_code")
        description = note.get("description") or ""
        if code and description.strip():
            codes.add(code)
    return codes


def filter_hidden_facts(
    hidden_facts: Iterable[dict[str, Any]],
    disclosure_level: Any,
    discord_present: bool,
    topic_notes: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Menyaring fakta tersembunyi yang boleh masuk prompt Peran B.

    - Fakta lolos hanya jika urutan(disclosure_level) >= urutan(fakta.min_disclosure_level).
    - Jika discord_present, hanya fakta yang sudah terungkap yang lolos.
    Nilai tingkat yang tidak dikenal diperlakukan secara tertutup (fakta tidak lolos).
    """
    current_rank = disclosure_rank(disclosure_level)
    if current_rank is None:
        return []

    revealed = revealed_fact_codes(topic_notes) if discord_present else set()

    allowed: list[dict[str, Any]] = []
    for fact in hidden_facts:
        min_rank = disclosure_rank(
            fact.get("min_disclosure_level") or DEFAULT_MIN_DISCLOSURE_LEVEL
        )
        if min_rank is None or current_rank < min_rank:
            continue
        if discord_present and fact.get("code") not in revealed:
            continue
        allowed.append(fact)
    return allowed


def enforce_disclosure_floor(previous_level: Any, proposed_level: Any) -> str:
    """Disclosure tidak pernah turun: mengembalikan max(previous, proposed).

    Jika proposed tidak dikenal, previous dipertahankan; jika previous tidak
    dikenal, proposed dipakai apa adanya.
    """
    prev_rank = disclosure_rank(previous_level)
    new_rank = disclosure_rank(proposed_level)
    if prev_rank is None:
        return proposed_level
    if new_rank is None or new_rank < prev_rank:
        return previous_level
    return proposed_level


def resolve_disclosure(previous_level: Any, proposed_level: Any, discord_present: bool) -> str:
    """Tingkat Disclosure final untuk state baru.

    - Discord tampak: tingkat sebelumnya dipertahankan (tidak naik, tidak turun).
    - Selain itu: tidak pernah turun (enforce_disclosure_floor).
    """
    if discord_present and disclosure_rank(previous_level) is not None:
        return previous_level
    return enforce_disclosure_floor(previous_level, proposed_level)
