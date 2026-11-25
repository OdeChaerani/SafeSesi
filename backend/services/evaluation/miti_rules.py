"""Aturan penghitungan kode perilaku MITI 4.2.1 (langkah 2, deterministik, tanpa LLM).

Masukan: hasil Behavior Coding Agent (unit ujaran + kandidat kode). Keluaran: kode akhir per
volley, frekuensi, dan jejak debug (setiap unit: kode LLM, hasil resolusi, aturan yang berlaku).

Rujukan bagian manual ditulis di setiap aturan. Aturan bertanda "PENGISIAN CELAH" adalah
keputusan peneliti untuk kasus yang tidak diatur tegas oleh manual (lihat
docs/perbedaan_miti_rubrik.md); di luar itu manual diikuti apa adanya.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from schemas.evaluation import MITI_CODES, BehaviorCodingOutput, CodedUnit

MIA = ("AF", "SEEK", "EA")
# E.4.f.1 Figure 1: piramida MIA dari bawah ke atas.
MIA_RANK = {"AF": 0, "SEEK": 1, "EA": 2}
REFLECTIONS = ("SR", "CR")
PERSUASION = ("P", "PWP")
# E.1.a: paling banyak 8 kode per volley (GI, P/PWP, Q, SR/CR, AF, Seek, EA, Confront).
MAX_CODES_PER_VOLLEY = 8
# E.4.f.2.a (adaptasi Rubrik SafeSesi): afirmasi yang SAMA dikode paling banyak 3 kali.
THREE_STRIKES_LIMIT = 3


class CodingValidationError(ValueError):
    """Keluaran Behavior Coding Agent tidak sesuai transkrip."""


@dataclass
class FinalCode:
    turn_no: int  # giliran pertama volley (tempat kode disimpan)
    unit_no: int  # nomor unit berurutan di dalam volley
    code: str
    excerpt: str
    reason: str
    uncertainty_note: str | None
    source_turn_no: int  # giliran asal unit (beda dari turn_no jika volley digabung)


@dataclass
class RulesResult:
    codes: list[FinalCode]
    frequencies: dict[str, int]
    volleys: list[list[int]]
    debug: dict[str, Any] = field(default_factory=dict)


def _pair(a: str, b: str, x: str | tuple[str, ...], y: str | tuple[str, ...]) -> bool:
    xs = (x,) if isinstance(x, str) else x
    ys = (y,) if isinstance(y, str) else y
    return (a in xs and b in ys) or (a in ys and b in xs)


def resolve_unit(unit: CodedUnit) -> tuple[str | None, str]:
    """Kode akhir satu unit ujaran (satu unit = satu kode, E.1.a) dan aturan yang berlaku."""
    a, b, certain = unit.code, unit.alternative_code, unit.certain
    if a is None:
        return None, "tidak dikode menurut agen (F)"
    if b is None or b == a:
        if not certain and a == "AF":
            # E.4.f.2: jika ragu apakah cukup spesifik/kuat untuk Affirm, AF tidak diberikan.
            return None, "E.4.f.2: AF ragu -> tidak dikode"
        return a, "kode tunggal"

    if certain:
        # Kedua kode jelas terpenuhi pada unit yang sama -> aturan prioritas (trumping).
        if _pair(a, b, "P", "PWP"):
            return "PWP", "E.4.c.1: P dan PWP pada unit sama -> PWP"
        if _pair(a, b, "CONFRONT", ("P", "Q") + REFLECTIONS):
            return "CONFRONT", "E.4.g.2/E.4.g.3: Confront mengalahkan P, Q, dan refleksi"
        if _pair(a, b, "AF", REFLECTIONS):
            return "AF", "E.4.f.2: Affirm mengalahkan refleksi"
        if a in MIA and b in MIA:
            top = max(a, b, key=MIA_RANK.__getitem__)
            return top, "E.4.f.1: keduanya jelas -> kode MIA yang lebih tinggi"
        if a in MIA or b in MIA:
            return (a if a in MIA else b), "E.4.f.1: kode MIA jelas terpenuhi -> MIA"
        if _pair(a, b, "SR", "CR"):
            return "CR", "E.4.e.2: refleksi jelas kompleks -> CR"
        if _pair(a, b, "GI", PERSUASION):
            return (a if a in PERSUASION else b), "E.4.b: persuasi jelas -> P/PWP"
        return a, "pasangan tanpa aturan prioritas -> kode utama"

    # Ragu di antara dua kode -> aturan default saat ragu.
    if _pair(a, b, "SR", "CR"):
        return "SR", "E.4.e.2: ragu SR vs CR -> SR"
    if _pair(a, b, "GI", PERSUASION):
        return "GI", "E.4.b/E.4.c: ragu persuasi vs GI -> GI"
    if _pair(a, b, "CONFRONT", "P"):
        # PENGISIAN CELAH: manual E.4.g.3 tidak memberi default saat ragu Confront vs Persuade.
        return "P", "PENGISIAN CELAH (E.4.g.3): ragu Confront vs P -> P"
    if _pair(a, b, "CONFRONT", REFLECTIONS):
        return None, "E.4.g.2: ragu Confront vs refleksi -> tidak dikode"
    if _pair(a, b, "CONFRONT", "Q"):
        return "Q", "E.4.g.2: Confront hanya bila jelas; ragu -> Q"
    if a in MIA and b in MIA:
        low = min(a, b, key=MIA_RANK.__getitem__)
        return low, "E.4.f.1: ragu antarkode MIA -> kode yang lebih rendah"
    if a in MIA or b in MIA:
        return (b if a in MIA else a), "E.4.f.1.a: ragu MIA vs kode lain -> kode lain"
    return a, "ragu tanpa aturan default di manual -> kode utama"


def validate_coding(output: BehaviorCodingOutput, counselor_turns: list[int]) -> None:
    got = [t.turn_no for t in output.turns]
    missing = sorted(set(counselor_turns) - set(got))
    extra = sorted(set(got) - set(counselor_turns))
    dupes = sorted(n for n, c in Counter(got).items() if c > 1)
    problems = []
    if missing:
        problems.append(f"giliran konselor tidak dikodekan: {missing}")
    if extra:
        problems.append(f"nomor giliran bukan giliran konselor: {extra}")
    if dupes:
        problems.append(f"giliran dikodekan lebih dari sekali: {dupes}")
    if problems:
        raise CodingValidationError("Keluaran Behavior Coding Agent tidak valid: " + "; ".join(problems))


def group_volleys(output: BehaviorCodingOutput, counselor_turns: list[int]) -> list[list[int]]:
    """E.3: ujaran klien fasilitatif tidak memutus volley; giliran digabung ke volley sebelumnya."""
    flags = {t.turn_no: t.continues_previous_volley for t in output.turns}
    volleys: list[list[int]] = []
    for turn_no in sorted(counselor_turns):
        if volleys and flags.get(turn_no):
            volleys[-1].append(turn_no)
        else:
            volleys.append([turn_no])
    return volleys


def apply_rules(output: BehaviorCodingOutput, counselor_turns: list[int]) -> RulesResult:
    validate_coding(output, counselor_turns)
    by_turn = {t.turn_no: t for t in output.turns}
    volleys = group_volleys(output, counselor_turns)
    unit_log: list[dict[str, Any]] = []
    codes: list[FinalCode] = []

    for volley in volleys:
        head = volley[0]
        candidates: list[tuple[str, CodedUnit, int, dict[str, Any]]] = []
        for turn_no in volley:
            for unit in sorted(by_turn[turn_no].units, key=lambda u: u.unit_no):
                resolved, rule = resolve_unit(unit)
                entry = {
                    "turn_no": turn_no,
                    "volley_head": head,
                    "unit_no": unit.unit_no,
                    "excerpt": unit.excerpt,
                    "llm_code": unit.code,
                    "alternative_code": unit.alternative_code,
                    "certain": unit.certain,
                    "same_affirmation_as_turn": unit.same_affirmation_as_turn,
                    "resolved_code": resolved,
                    "resolve_rule": rule,
                    "kept": False,
                    "drop_rule": None if resolved else rule,
                }
                unit_log.append(entry)
                if resolved:
                    candidates.append((resolved, unit, turn_no, entry))

        kept: dict[str, tuple[CodedUnit, int, dict[str, Any]]] = {}
        # E.1.a, E.4.e.3: satu kode refleksi per volley; CR jika ada refleksi kompleks.
        reflection = "CR" if any(c == "CR" for c, *_ in candidates) else "SR"
        # E.1.a, E.4.c.1: satu slot persuasi per volley. PENGISIAN CELAH (perluasan E.4.c.1):
        # P dan PWP di unit berbeda dalam satu volley -> PWP.
        persuasion = "PWP" if any(c == "PWP" for c, *_ in candidates) else "P"
        for code, unit, turn_no, entry in candidates:
            slot = reflection if code in REFLECTIONS else persuasion if code in PERSUASION else code
            if code != slot:
                entry["drop_rule"] = (
                    "E.1.a/E.4.e.3: satu refleksi per volley, CR diutamakan"
                    if code in REFLECTIONS
                    else "PENGISIAN CELAH (perluasan E.4.c.1): P dan PWP dalam satu volley -> PWP"
                )
                continue
            if slot in kept:
                # E.1.a (dan E.4.d untuk Q): setiap kode paling banyak sekali per volley.
                entry["drop_rule"] = f"E.1.a: {slot} sudah dikode di volley ini"
                continue
            kept[slot] = (unit, turn_no, entry)
            entry["kept"] = True
        assert len(kept) <= MAX_CODES_PER_VOLLEY, f"volley {head}: {len(kept)} kode > {MAX_CODES_PER_VOLLEY}"

        for unit_no, (code, (unit, turn_no, entry)) in enumerate(
            sorted(kept.items(), key=lambda kv: (kv[1][1], kv[1][0].unit_no)), start=1
        ):
            entry["final_unit_no"] = unit_no
            codes.append(FinalCode(head, unit_no, code, unit.excerpt, unit.reason, unit.uncertainty_note, turn_no))

    _apply_three_strikes(codes, volleys, unit_log)
    frequencies = {c: 0 for c in MITI_CODES}
    for fc in codes:
        frequencies[fc.code] += 1
    return RulesResult(
        codes=codes,
        frequencies=frequencies,
        volleys=volleys,
        debug={"volleys": volleys, "units": unit_log},
    )


def _apply_three_strikes(codes: list[FinalCode], volleys: list[list[int]], unit_log: list[dict[str, Any]]) -> None:
    """E.4.f.2.a, adaptasi Rubrik SafeSesi: afirmasi yang sama (diulang) dikode paling banyak 3 kali.

    Pengulangan ditandai agen lewat same_affirmation_as_turn; Python hanya menghitung rantainya.
    """
    head_of = {t: v[0] for v in volleys for t in v}
    entry_of = {(e["volley_head"], e.get("final_unit_no")): e for e in unit_log if e["kept"]}
    group: dict[int, int] = {}  # kepala volley AF -> id kelompok afirmasi sama
    counts: Counter[int] = Counter()
    for fc in sorted((c for c in codes if c.code == "AF"), key=lambda c: c.turn_no):
        entry = entry_of[(fc.turn_no, fc.unit_no)]
        ref = entry["same_affirmation_as_turn"]
        gid = group.get(head_of.get(ref, -1), fc.turn_no) if ref is not None else fc.turn_no
        group[fc.turn_no] = gid
        counts[gid] += 1
        if counts[gid] > THREE_STRIKES_LIMIT:
            codes.remove(fc)
            entry["kept"] = False
            entry["drop_rule"] = "E.4.f.2.a (adaptasi: ambang 3, afirmasi sama): afirmasi ke-4 dst. tidak dikode"
