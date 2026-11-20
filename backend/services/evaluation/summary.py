"""Ukuran ringkasan MITI 4.2.1 bagian H (dihitung saat GET, tidak disimpan).

Penyajian penyebut nol mengikuti Rubrik SafeSesi 2.4: "tidak dapat dihitung" beserta jumlah
mentahnya, bukan 0.
"""
from __future__ import annotations

from typing import Any

NOT_COMPUTABLE = "tidak dapat dihitung"
NOT_ASSESSED = "tidak dinilai"


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
    return {
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
