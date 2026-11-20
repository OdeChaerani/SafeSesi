"""Ukuran ringkasan MITI 4.2.1 bagian H (dihitung saat GET, tidak disimpan).

Penyajian penyebut nol mengikuti Rubrik SafeSesi 2.4: "tidak dapat dihitung" beserta jumlah
mentahnya, bukan 0.
"""
from __future__ import annotations

from typing import Any

NOT_COMPUTABLE = "tidak dapat dihitung"
NOT_ASSESSED = "tidak dinilai"

# Ambang fair/good MITI 4.2.1 bagian H. Rubrik 2.4: hanya acuan belajar, bukan penentu kelulusan.
REFERENCE_THRESHOLDS: dict[str, dict[str, float]] = {
    "technical_global": {"cukup": 3, "baik": 4},
    "relational_global": {"cukup": 3.5, "baik": 4},
    "pct_complex_reflection": {"cukup": 40, "baik": 50},
    "reflection_question_ratio": {"cukup": 1, "baik": 2},
}
REFERENCE_NOTE = "Acuan dari MITI. Dipakai sebagai bahan belajar, bukan penentu lulus."


def reference_band(value: float | None, thresholds: dict[str, float]) -> str | None:
    if value is None:
        return None
    if value >= thresholds["baik"]:
        return "baik"
    return "cukup" if value >= thresholds["cukup"] else "di_bawah_acuan"


def _with_reference(key: str, measure: dict[str, Any]) -> dict[str, Any]:
    t = REFERENCE_THRESHOLDS[key]
    return {**measure, "reference_band": reference_band(measure["value"], t), "reference_thresholds": t, "reference_note": REFERENCE_NOTE}


def _ratio(numerator: int, denominator: int, scale: float, formula: str, counts: dict[str, int]) -> dict[str, Any]:
    if denominator == 0:
        return {"value": None, "label": NOT_COMPUTABLE, "formula": formula, "counts": counts}
    return {"value": round(scale * numerator / denominator, 2), "label": None, "formula": formula, "counts": counts}


def _global_mean(globals_: dict[str, int | None] | None, a: str, b: str, formula: str) -> dict[str, Any]:
    scores = {k: (globals_ or {}).get(k) for k in (a, b)}
    if any(v is None for v in scores.values()):
        return {"value": None, "label": NOT_ASSESSED, "formula": formula, "scores": scores}
    return {"value": round((scores[a] + scores[b]) / 2, 2), "label": None, "formula": formula, "scores": scores}


def summary_measures(freq: dict[str, int], globals_: dict[str, int | None] | None) -> dict[str, Any]:
    f = {k: freq.get(k, 0) for k in ("SR", "CR", "Q", "AF", "SEEK", "EA", "P", "CONFRONT")}
    measures = {
        "technical_global": _global_mean(
            globals_, "cultivating_change_talk", "softening_sustain_talk",
            "(Cultivating Change Talk + Softening Sustain Talk) / 2",
        ),
        "relational_global": _global_mean(globals_, "partnership", "empathy", "(Partnership + Empathy) / 2"),
        "pct_complex_reflection": _ratio(
            f["CR"], f["SR"] + f["CR"], 100, "CR / (SR + CR) × 100%", {"SR": f["SR"], "CR": f["CR"]}
        ),
        "reflection_question_ratio": _ratio(
            f["SR"] + f["CR"], f["Q"], 1, "(SR + CR) / Q", {"SR": f["SR"], "CR": f["CR"], "Q": f["Q"]}
        ),
    }
    return {
        **{k: _with_reference(k, m) for k, m in measures.items()},
        "total_mia": {
            "value": f["AF"] + f["SEEK"] + f["EA"],
            "formula": "AF + Seek + Emphasize",
            "counts": {"AF": f["AF"], "SEEK": f["SEEK"], "EA": f["EA"]},
        },
        # PWP tidak masuk MIA maupun MINA (MITI bagian H).
        "total_mina": {
            "value": f["P"] + f["CONFRONT"],
            "formula": "P + Confront",
            "counts": {"P": f["P"], "CONFRONT": f["CONFRONT"]},
        },
    }
