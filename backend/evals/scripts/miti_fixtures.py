"""Pemuat fixture MITI (Ilustrasi dan CASAA) untuk tes dan skrip pembanding.

Fixture hanya untuk pengujian; isinya tidak boleh dipakai sebagai contoh prompt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from schemas.evaluation import MITI_CODES
from services.evaluation.miti_evaluator import EvaluationInput

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"
SETS = ("ilustrasi", "casaa")
DEFAULT_SESSION = {"ilustrasi": "SS-NAD-01-S01", "casaa": "casaa_smoker"}
# ilustrasi/ juga berisi ilustrasi_state_sessions.json (fixture replay Peran A), jadi pola nama dibatasi.
FIXTURE_GLOB = {"ilustrasi": "SS-*.json", "casaa": "casaa_*.json"}
BUILD_HINT = {
    "ilustrasi": "backend/venv/Scripts/python backend/evals/scripts/build_ilustrasi_miti_fixtures.py",
    "casaa": "backend/venv/Scripts/python backend/evals/scripts/build_casaa_fixtures.py "
             "(butuh PDF di docs/coded-transcript-miti/ dan pdftotext di PATH)",
}


class FixturesMissing(FileNotFoundError):
    pass


def load_set(set_name: str) -> list[dict[str, Any]]:
    paths = sorted((FIXTURE_DIR / set_name).glob(FIXTURE_GLOB[set_name]))
    if not paths:
        raise FixturesMissing(
            f"Fixture {set_name} belum dibangun di {FIXTURE_DIR / set_name}. Bangun dengan:\n  {BUILD_HINT[set_name]}"
        )
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def fixture_input(fx: dict[str, Any], change_target: str | None = None) -> EvaluationInput:
    return EvaluationInput(
        turns=[{"turn_no": t["turn_no"], "speaker": t["speaker"], "content": t["content"]} for t in fx["turns"]],
        change_target=change_target or fx["change_target"],
        initial_summary=fx.get("initial_summary"),
        # duration_known false (CASAA): aturan durasi Rubrik dilewati.
        duration_seconds=fx["duration_seconds"] if fx.get("duration_known") else None,
        label=fx["fixture_id"],
    )


def expert_volleys(fx: dict[str, Any]) -> list[dict[str, Any]]:
    """Volley menurut ahli: baris SAME (lanjutan volley, E.3) digabung ke volley sebelumnya."""
    volleys: list[dict[str, Any]] = []
    for t in fx["turns"]:
        if t["speaker"] != "counselor":
            continue
        if t.get("same_as_previous_volley") and volleys:
            volleys[-1]["turns"].append(t["turn_no"])
            continue
        volleys.append({
            "head": t["turn_no"],
            "turns": [t["turn_no"]],
            "codes": list(t["expected_codes"]),
            "alternatives": list(t.get("acceptable_alternatives") or []),
        })
    return volleys


def expert_frequencies(fx: dict[str, Any]) -> dict[str, int]:
    freq = {c: 0 for c in MITI_CODES}
    for v in expert_volleys(fx):
        for c in v["codes"]:
            freq[c] += 1
    return freq
