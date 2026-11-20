"""Pipeline evaluasi otomatis MITI 4.2.1 untuk satu sesi (tanpa akses database).

Urutan:
  behavior_coding ─┐
  global_scoring  ─┼─ paralel ─> aturan penghitungan (Python) ─> feedback
  process_obs     ─┘
Global Scoring Agent sengaja tidak menerima hasil kode perilaku (MITI B: skor global dan hitungan
perilaku dapat dinilai dalam dua putaran terpisah; D: skor global adalah penilaian gestalt).
Process Observation Agent juga independen (Rubrik 2.5: kode tidak dipetakan 1:1 ke proses).
Feedback Agent memerlukan hasil MITI dan bukti (Rubrik 3.1), jadi berjalan terakhir.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from core.config import get_settings
from core.errors import SafeSesiError
from prompts.prompt_evaluation import (
    behavior_coding_prompts,
    feedback_prompts,
    global_scoring_prompts,
    process_observation_prompts,
)
from schemas.evaluation import (
    GLOBAL_DIMENSIONS,
    MI_PROCESSES,
    BehaviorCodingOutput,
    FeedbackOutput,
    GlobalScoringOutput,
    ProcessObservationOutput,
)
from services.evaluation.miti_rules import FinalCode, apply_rules
from services.llm.gemini_client import EVALUATOR_ROLES, evaluator_llm_configs, get_gemini_client, track_usage

logger = logging.getLogger("safesesi.evaluation")

GUIDELINE_VERSION = "MITI 4.2.1 / Rubrik SafeSesi v1"
# Rubrik SafeSesi 2.1 (berdasar MITI Lampiran B FAQ 1): <=5 menit hanya kode perilaku;
# <10 menit skor global tetap dinilai dengan keterangan keterbatasan.
SHORT_SESSION_S = 300
LIMITED_SESSION_S = 600
TEMPERATURE = 0.0


class EvaluationError(SafeSesiError):
    def __init__(self, message: str):
        super().__init__(message, status_code=500)


@dataclass
class EvaluationInput:
    turns: list[dict[str, Any]]  # {turn_no, speaker: counselor|client, content}
    change_target: str
    initial_summary: str | None = None
    duration_seconds: int | None = None  # None = tidak diketahui (fixture CASAA): aturan durasi dilewati
    label: str = "sesi"


@dataclass
class EvaluationResult:
    codes: list[FinalCode] | None = None
    frequencies: dict[str, int] | None = None
    globals: dict[str, dict[str, Any]] | None = None
    processes: list[dict[str, Any]] | None = None
    feedback: list[dict[str, Any]] | None = None
    limitation_notes: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    model_version: str = ""
    agents_run: list[str] = field(default_factory=list)


def agents_to_run(duration_seconds: int | None, requested: set[str] | None = None) -> tuple[list[str], list[str]]:
    """Agen yang dijalankan dan keterangan keterbatasan menurut aturan durasi Rubrik 2.1."""
    agents = set(requested or EVALUATOR_ROLES)
    if "feedback" in agents and "behavior_coding" not in agents:
        raise ValueError("Feedback Agent membutuhkan hasil behavior_coding.")
    notes: list[str] = []
    if duration_seconds is not None and duration_seconds <= SHORT_SESSION_S:
        agents &= {"behavior_coding"}
        notes.append(
            f"Durasi sesi {duration_seconds} detik (≤ 5 menit): sesuai Rubrik SafeSesi 2.1, hanya kode perilaku "
            "dan ukuran berbasis jumlah kode (%CR, R:Q, MIA, MINA) yang ditampilkan. Skor global, Technical/"
            "Relational Global, pengamatan proses MI, dan umpan balik tidak dinilai."
        )
    elif duration_seconds is not None and duration_seconds < LIMITED_SESSION_S:
        notes.append(
            f"Durasi sesi {duration_seconds} detik (< 10 menit): skor global lebih sulit ditetapkan pada sesi "
            "pendek (MITI 4.2.1 Lampiran B FAQ 1; Rubrik SafeSesi 2.1). Tafsirkan skor global dengan hati-hati."
        )
    return [a for a in EVALUATOR_ROLES if a in agents], notes


def model_version_string(configs: dict[str, tuple[str, int | None]], agents: list[str]) -> str:
    def budget(b: int | None) -> str:
        return "default" if b is None else str(b)

    return "; ".join(f"{a}={configs[a][0]} (thinking={budget(configs[a][1])})" for a in agents)


# --- Pencocokan kutipan ----------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Normalisasi untuk mencocokkan kutipan: huruf kecil, tanpa tanda baca, spasi tunggal."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def excerpt_matches(excerpt: str, content: str) -> bool:
    """Kutipan cocok jika (setelah normalisasi) muncul di isi giliran; potongan yang dipisah elipsis
    harus muncul berurutan."""
    haystack = normalize_text(content)
    pos = 0
    pieces = [normalize_text(p) for p in re.split(r"\.\.\.|…", excerpt)]
    pieces = [p for p in pieces if p]
    if not pieces:
        return False
    for piece in pieces:
        idx = haystack.find(piece, pos)
        if idx < 0:
            return False
        pos = idx + len(piece)
    return True


# --- Pipeline ----------------------------------------------------------------------------


class _AgentRunner:
    def __init__(self, llm: Any, configs: dict[str, tuple[str, int | None]], usage: dict[str, dict[str, int]]):
        self.llm = llm
        self.configs = configs
        self.usage = usage
        self.elapsed: dict[str, float] = {}

    async def call(self, role: str, system: str, user: str, schema: type) -> Any:
        model, budget = self.configs[role]
        t0 = time.perf_counter()
        try:
            return await self.llm.generate_json(
                model, system, user, schema, temperature=TEMPERATURE, thinking_budget=budget, role=role
            )
        finally:
            self.elapsed[role] = self.elapsed.get(role, 0.0) + time.perf_counter() - t0

    def metrics(self) -> dict[str, dict[str, Any]]:
        out = {}
        for role, seconds in self.elapsed.items():
            u = self.usage.get(role, {})
            out[role] = {
                "duration_s": round(seconds, 2),
                "calls": u.get("calls", 0),
                "input_tokens": u.get("input", 0),
                "output_tokens": u.get("output", 0),
                "thoughts_tokens": u.get("thoughts", 0),
            }
        return out


async def run_evaluation(
    inp: EvaluationInput,
    llm: Any = None,
    settings: Any = None,
    agents: set[str] | None = None,
    thinking_budget_override: int | None | str = "unset",
) -> EvaluationResult:
    """Menjalankan agen evaluator dan aturan Python. Tidak menyentuh database.

    thinking_budget_override (skrip pembanding): menimpa thinking budget semua agen; "unset" = config.
    """
    settings = settings or get_settings()
    configs = evaluator_llm_configs(settings)
    if thinking_budget_override != "unset":
        configs = {role: (model, thinking_budget_override) for role, (model, _b) in configs.items()}
    run_list, notes = agents_to_run(inp.duration_seconds, agents)
    counselor_turns = [t["turn_no"] for t in inp.turns if t["speaker"] == "counselor"]
    if not counselor_turns:
        raise EvaluationError("Sesi tidak memiliki giliran konselor yang dapat dinilai.")

    usage: dict[str, dict[str, int]] = {}
    track_usage(usage)
    runner = _AgentRunner(llm or get_gemini_client(), configs, usage)
    result = EvaluationResult(limitation_notes=notes, agents_run=run_list, model_version=model_version_string(configs, run_list))
    turns_by_no = {t["turn_no"]: t for t in inp.turns}
    args = (inp.turns, inp.change_target, inp.initial_summary)

    async def maybe(role: str, coro_factory):
        return await coro_factory() if role in run_list else None

    bc_out, gs_out, po_out = await asyncio.gather(
        maybe("behavior_coding", lambda: runner.call("behavior_coding", *behavior_coding_prompts(*args), BehaviorCodingOutput)),
        maybe("global_scoring", lambda: runner.call("global_scoring", *global_scoring_prompts(*args), GlobalScoringOutput)),
        maybe("process_observation", lambda: runner.call("process_observation", *process_observation_prompts(*args), ProcessObservationOutput)),
    )

    if bc_out is not None:
        rules = apply_rules(bc_out, counselor_turns)
        result.codes, result.frequencies = rules.codes, rules.frequencies
        result.debug["behavior_coding"] = rules.debug
        mismatches = [
            {"turn_no": t.turn_no, "unit_no": u.unit_no, "excerpt": u.excerpt}
            for t in bc_out.turns
            for u in t.units
            if not excerpt_matches(u.excerpt, turns_by_no[t.turn_no]["content"])
        ]
        if mismatches:
            logger.warning("%s: %d kutipan unit tidak cocok dengan transkrip", inp.label, len(mismatches))
        result.debug["excerpt_mismatches"] = mismatches
    if gs_out is not None:
        result.globals = _validate_globals(gs_out, turns_by_no, result.debug)
    if po_out is not None:
        result.processes = _validate_processes(po_out, turns_by_no, result.debug)

    if "feedback" in run_list:
        result.feedback = await _run_feedback(runner, inp, result, turns_by_no)

    result.metrics = runner.metrics()
    result.debug["agent_metrics"] = result.metrics
    for role, m in result.metrics.items():
        logger.info(
            "Evaluasi %s | %s: %.2fs, %d panggilan, token input %d, output %d, thinking %d",
            inp.label, role, m["duration_s"], m["calls"], m["input_tokens"], m["output_tokens"], m["thoughts_tokens"],
        )
    return result


def _validate_globals(out: GlobalScoringOutput, turns_by_no: dict[int, Any], debug: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    dropped = {}
    for dim in GLOBAL_DIMENSIONS:
        rating = getattr(out, dim)
        if not 1 <= rating.score <= 5:
            raise EvaluationError(f"Global Scoring Agent memberi skor di luar 1–5 untuk {dim}: {rating.score}")
        valid = [n for n in rating.evidence_turn_nos if n in turns_by_no]
        if len(valid) != len(rating.evidence_turn_nos):
            dropped[dim] = sorted(set(rating.evidence_turn_nos) - set(valid))
        scores[dim] = {"score": rating.score, "reason": rating.reason, "evidence_turn_nos": valid}
    debug["global_scoring"] = {"unknown_evidence_turns_removed": dropped}
    return scores


def _validate_processes(out: ProcessObservationOutput, turns_by_no: dict[int, Any], debug: dict[str, Any]) -> list[dict[str, Any]]:
    rows, notes = [], []
    for item in out.observations:
        start, end = item.start_turn_no, item.end_turn_no
        if not item.evidence_found:
            start = end = None
        for n in (start, end):
            if n is not None and n not in turns_by_no:
                notes.append(f"{item.process}: giliran {n} tidak ada di transkrip, rentang dikosongkan")
                start = end = None
        if start is not None and end is not None and end < start:
            start, end = end, start
        rows.append({
            "process": item.process,
            "evidence_found": item.evidence_found and start is not None,
            "start_turn_no": start,
            "end_turn_no": end,
            "excerpt": item.excerpt if item.evidence_found else None,
            "reason": item.reason,
        })
    for proc in MI_PROCESSES:
        if not any(r["process"] == proc for r in rows):
            # Agen wajib melaporkan keempat proses; yang tidak dilaporkan dicatat sebagai belum cukup bukti.
            notes.append(f"{proc}: tidak dilaporkan agen")
            rows.append({"process": proc, "evidence_found": False, "start_turn_no": None, "end_turn_no": None,
                         "excerpt": None, "reason": "Belum cukup bukti untuk mengidentifikasi proses ini."})
    debug["process_observation"] = {"notes": notes}
    return rows


def validate_feedback(items: list[Any], turns_by_no: dict[int, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    valid, errors = [], []
    for i, item in enumerate(items, start=1):
        turn = turns_by_no.get(item.turn_no)
        problem = None
        if turn is None:
            problem = f"turn_no {item.turn_no} tidak ada di transkrip"
        elif item.kind == "alternative_response" and turn["speaker"] != "counselor":
            problem = f"alternative_response harus menunjuk giliran konselor, T{item.turn_no} adalah giliran klien"
        elif item.kind == "alternative_response" and not (item.alternative_text or "").strip():
            problem = "alternative_response tanpa alternative_text (kalimat konkret)"
        elif not excerpt_matches(item.excerpt, turn["content"]):
            problem = f"excerpt {item.excerpt!r} tidak ditemukan di T{item.turn_no}"
        if problem:
            errors.append(f"item {i} ({item.kind}): {problem}")
            continue
        valid.append({
            "kind": item.kind,
            "turn_no": item.turn_no,
            "evidence_turn_nos": [n for n in item.evidence_turn_nos if n in turns_by_no],
            "excerpt": item.excerpt,
            "explanation": item.explanation,
            # Kolom content: kalimat alternatif untuk alternative_response, penjelasan untuk lainnya.
            "content": item.alternative_text.strip() if item.kind == "alternative_response" else item.explanation,
        })
    if not items:
        errors.append("tidak ada item umpan balik")
    return valid, errors


async def _run_feedback(runner: _AgentRunner, inp: EvaluationInput, result: EvaluationResult, turns_by_no: dict[int, Any]) -> list[dict[str, Any]]:
    coded: dict[int, list[dict[str, str]]] = {}
    for fc in result.codes or []:
        coded.setdefault(fc.turn_no, []).append({"code": fc.code, "excerpt": fc.excerpt, "reason": fc.reason})
    coded_turns = [{"turn_no": n, "codes": c} for n, c in sorted(coded.items())]
    base = (inp.turns, inp.change_target, inp.initial_summary, coded_turns, result.globals, result.processes)

    first = await runner.call("feedback", *feedback_prompts(*base), FeedbackOutput)
    valid, errors = validate_feedback(first.items, turns_by_no)
    log: dict[str, Any] = {"attempt_1_errors": errors}
    if errors:
        logger.warning("%s: umpan balik tidak valid, Feedback Agent dijalankan ulang: %s", inp.label, errors)
        second = await runner.call("feedback", *feedback_prompts(*base, correction="\n".join(errors)), FeedbackOutput)
        valid, errors = validate_feedback(second.items, turns_by_no)
        log["attempt_2_errors"] = errors
        if errors:
            logger.warning("%s: item umpan balik tidak valid dibuang: %s", inp.label, errors)
            log["dropped"] = errors
    result.debug["feedback"] = log
    if not valid:
        raise EvaluationError("Semua item umpan balik tidak valid setelah Feedback Agent dijalankan ulang: " + "; ".join(errors))
    return valid


def planned_calls(inp: EvaluationInput, agents: set[str] | None = None) -> list[tuple[str, str, str]]:
    """Untuk --dry-run: prompt (agen, system, user) yang akan dikirim, tanpa memanggil Gemini.

    Prompt feedback dibangun dengan hasil kosong, jadi perkiraan tokennya sedikit lebih rendah
    daripada aslinya (hasil kode, skor, dan proses ikut dikirim pada panggilan sungguhan).
    """
    run_list, _ = agents_to_run(inp.duration_seconds, agents)
    args = (inp.turns, inp.change_target, inp.initial_summary)
    builders = {
        "behavior_coding": lambda: behavior_coding_prompts(*args),
        "global_scoring": lambda: global_scoring_prompts(*args),
        "process_observation": lambda: process_observation_prompts(*args),
        "feedback": lambda: feedback_prompts(*args, [], None, None),
    }
    return [(role, *builders[role]()) for role in run_list]
