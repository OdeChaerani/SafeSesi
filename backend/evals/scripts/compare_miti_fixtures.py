"""Bandingkan evaluator MITI sungguhan (memanggil Gemini) dengan fixture Ilustrasi dan CASAA.

BUKAN bagian test suite dan MEMAKAI KUOTA GEMINI (kecuali --dry-run). Menolak jalan saat
APP_ENV=production kecuali --allow-production. Tidak menulis ke database. Hasil lengkap ditulis ke
backend/evals/results/<tanggal>_<set>_<model>.json (atau --output).

Contoh (dari root repo, PowerShell):
  backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --dry-run --set all --sessions all
  backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py          # SS-NAD-01-S01 saja
  backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --set casaa --sessions all
  backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --set casaa --sessions casaa_emmy `
      --change-target-override 'casaa_emmy=return to work'
  backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --agents behavior_coding --thinking-budget 0
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = EVALS_DIR.parent
RESULTS_DIR = EVALS_DIR / "results"
sys.path.insert(0, str(BACKEND_DIR))

from core.config import get_settings  # noqa: E402
from miti_fixtures import (  # noqa: E402
    DEFAULT_SESSION,
    SETS,
    FixturesMissing,
    expert_frequencies,
    expert_volleys,
    fixture_input,
    load_set,
)
from schemas.evaluation import GLOBAL_DIMENSIONS, MITI_CODES  # noqa: E402
from services.evaluation.miti_evaluator import planned_calls, run_evaluation  # noqa: E402
from services.llm.gemini_client import EVALUATOR_ROLES, evaluator_llm_configs  # noqa: E402

NA = "tidak dapat dihitung"


def default_output_path(set_arg: str, budget: int | None | str) -> Path:
    """results/<tanggal-jam>_<set>_<model behavior_coding>[_tb<budget>].json"""
    model, cfg_budget = evaluator_llm_configs(get_settings())["behavior_coding"]
    b = cfg_budget if budget == "unset" else budget
    tag = re.sub(r"[^A-Za-z0-9.-]+", "-", f"{model}_tb{'default' if b is None else b}")
    return RESULTS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{set_arg}_{tag}.json"


def parse_budget(text: str) -> int | None:
    return None if text.lower() in ("none", "default") else int(text)


def parse_overrides(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not value.strip():
            sys.exit(f"--change-target-override harus berbentuk ID=target, bukan {item!r}")
        out[key.strip()] = value.strip().strip('"')
    return out


def select_fixtures(set_arg: str, sessions: list[str] | None) -> list[tuple[str, dict[str, Any]]]:
    sets = SETS if set_arg == "all" else (set_arg,)
    chosen = []
    for s in sets:
        fixtures = load_set(s)
        if sessions and "all" in sessions:
            wanted = {f["fixture_id"] for f in fixtures}
        elif sessions:
            wanted = set(sessions)
        else:
            wanted = {DEFAULT_SESSION[s]}
        chosen += [(s, f) for f in fixtures if f["fixture_id"] in wanted]
    known = {f["fixture_id"] for s in sets for f in load_set(s)}
    unknown = set(sessions or []) - known - {"all"}
    if unknown:
        sys.exit(f"Sesi tidak dikenal untuk --set {set_arg}: {sorted(unknown)}. Tersedia: {sorted(known)}")
    return chosen


# --- Perbandingan -------------------------------------------------------------------------


def compare_codes(fx: dict[str, Any], result: Any) -> dict[str, Any]:
    """Per volley ahli: kode ahli cocok bila sistem memberi kode itu atau salah satu alternatifnya."""
    system_by_head: dict[int, list[str]] = {}
    for c in result.codes:
        system_by_head.setdefault(c.turn_no, []).append(c.code)
    tp, fp, fn = Counter(), Counter(), Counter()
    rows = []
    for v in expert_volleys(fx):
        sys_codes = [c for t in v["turns"] for c in system_by_head.get(t, [])]
        remaining = list(sys_codes)
        matched_all = True
        for code in v["codes"]:
            hit = next((c for c in [code, *v["alternatives"]] if c in remaining), None)
            if hit:
                remaining.remove(hit)
                tp[code] += 1
            else:
                fn[code] += 1
                matched_all = False
        for c in remaining:
            if c in v["alternatives"]:
                continue  # alternatif yang diterima ahli tidak dihitung sebagai kode berlebih
            fp[c] += 1
            matched_all = False
        rows.append({"turn_no": v["head"], "turns": v["turns"], "expert": v["codes"],
                     "acceptable_alternatives": v["alternatives"], "system": sorted(sys_codes), "match": matched_all})
    return {"volleys": rows, "tp": dict(tp), "fp": dict(fp), "fn": dict(fn)}


def per_code_metrics(tp: Counter, fp: Counter, fn: Counter, sys_freq: Counter, exp_freq: Counter) -> dict[str, Any]:
    out = {}
    for c in MITI_CODES:
        p_den, r_den = tp[c] + fp[c], tp[c] + fn[c]
        out[c] = {
            "system": sys_freq[c], "expert": exp_freq[c], "diff": sys_freq[c] - exp_freq[c],
            "tp": tp[c], "fp": fp[c], "fn": fn[c],
            "precision": round(tp[c] / p_den, 3) if p_den else NA,
            "recall": round(tp[c] / r_den, 3) if r_den else NA,
        }
    return out


def compare_globals(fx: dict[str, Any], result: Any) -> dict[str, Any] | None:
    if not result.globals:
        return None
    dims = {}
    for d in GLOBAL_DIMENSIONS:
        s, e = result.globals[d]["score"], fx["expected_globals"][d]
        dims[d] = {"system": s, "expert": e, "diff": s - e}
    return {
        "dimensions": dims,
        "exact": sum(v["diff"] == 0 for v in dims.values()),
        "within_1": sum(abs(v["diff"]) <= 1 for v in dims.values()),
        "total": len(dims),
    }


def aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
    tp, fp, fn, sf, ef = Counter(), Counter(), Counter(), Counter(), Counter()
    volleys = matches = g_exact = g_within = g_total = 0
    for e in entries:
        cmp = e.get("codes")
        if cmp:
            tp.update(cmp["tp"]); fp.update(cmp["fp"]); fn.update(cmp["fn"])  # noqa: E702
            sf.update(e["frequencies"]["system"]); ef.update(e["frequencies"]["expert"])  # noqa: E702
            volleys += len(cmp["volleys"])
            matches += sum(v["match"] for v in cmp["volleys"])
        if e.get("globals"):
            g_exact += e["globals"]["exact"]; g_within += e["globals"]["within_1"]; g_total += e["globals"]["total"]  # noqa: E702
    return {
        "sessions": len(entries),
        "volley_exact_match": {"matched": matches, "total": volleys,
                               "rate": round(matches / volleys, 3) if volleys else NA},
        "per_code": per_code_metrics(tp, fp, fn, sf, ef),
        "globals": {"exact": g_exact, "within_1": g_within, "total": g_total},
    }


# --- Cetak --------------------------------------------------------------------------------


def print_session(entry: dict[str, Any]) -> None:
    print(f"\n=== {entry['fixture_id']} ({entry['set']}) target={entry['change_target']!r}"
          f"{' [asumsi]' if entry['change_target_assumed'] else ''}")
    for note in entry["limitation_notes"]:
        print("  keterbatasan:", note)
    cmp = entry.get("codes")
    if cmp:
        print("  Volley  Ahli/dokumen                 Sistem                       Cocok")
        for v in cmp["volleys"]:
            exp = "+".join(v["expert"]) or "-"
            if v["acceptable_alternatives"]:
                exp += f" (alt {'/'.join(v['acceptable_alternatives'])})"
            print(f"  T{v['turn_no']:<5} {exp:28} {'+'.join(v['system']) or '-':28} {'✓' if v['match'] else '✗'}")
        print("  Frekuensi (sistem vs ahli):",
              ", ".join(f"{c} {entry['frequencies']['system'][c]}/{entry['frequencies']['expert'][c]}" for c in MITI_CODES))
    if entry.get("globals"):
        print("  Skor global (sistem vs ahli):",
              ", ".join(f"{d} {v['system']}/{v['expert']} ({v['diff']:+d})" for d, v in entry["globals"]["dimensions"].items()))
    for role, m in entry["metrics"].items():
        print(f"  {role:20} {m['duration_s']:>7.2f}s  panggilan {m['calls']}  token in {m['input_tokens']}"
              f" out {m['output_tokens']} thinking {m['thoughts_tokens']}")


def print_summary(name: str, summary: dict[str, Any]) -> None:
    v = summary["volley_exact_match"]
    print(f"\n### Ringkasan {name}: {summary['sessions']} sesi; volley cocok persis {v['matched']}/{v['total']} ({v['rate']})")
    print("  Kode      sistem  ahli  selisih  precision  recall")
    for c, m in summary["per_code"].items():
        print(f"  {c:9} {m['system']:>6} {m['expert']:>5} {m['diff']:>+8}  {str(m['precision']):>9}  {str(m['recall']):>6}")
    g = summary["globals"]
    if g["total"]:
        print(f"  Skor global: sama persis {g['exact']}/{g['total']}, selisih ≤1 {g['within_1']}/{g['total']}")


# --- Main ---------------------------------------------------------------------------------


def dry_run(chosen, agents, overrides) -> None:
    total_calls = total_tokens = 0
    for set_name, fx in chosen:
        inp = fixture_input(fx, overrides.get(fx["fixture_id"]))
        calls = planned_calls(inp, agents)
        print(f"\n{fx['fixture_id']} ({set_name}): {len(calls)} panggilan direncanakan")
        for role, system, user in calls:
            est = (len(system) + len(user)) // 4  # perkiraan kasar: ~4 karakter per token
            total_calls += 1
            total_tokens += est
            print(f"  {role:20} ~{est:>6} token input")
        if any(r == "feedback" for r, *_ in calls):
            print("  (feedback bisa +1 panggilan jika itemnya tidak valid)")
    print(f"\nTotal: {total_calls} panggilan, ~{total_tokens} token input (perkiraan, Gemini tidak dipanggil).")


async def run(args: argparse.Namespace, chosen, agents, overrides) -> None:
    budget = parse_budget(args.thinking_budget) if args.thinking_budget is not None else "unset"
    entries: list[dict[str, Any]] = []
    for set_name, fx in chosen:
        target = overrides.get(fx["fixture_id"])
        t0 = time.perf_counter()
        result = await run_evaluation(fixture_input(fx, target), agents=agents, thinking_budget_override=budget)
        entry: dict[str, Any] = {
            "set": set_name,
            "fixture_id": fx["fixture_id"],
            "change_target": target or fx["change_target"],
            "change_target_assumed": bool(fx.get("change_target_assumed")) and not target,
            "change_target_overridden": bool(target),
            "model_version": result.model_version,
            "limitation_notes": result.limitation_notes,
            "wall_time_s": round(time.perf_counter() - t0, 2),
            "metrics": result.metrics,
        }
        if result.codes is not None:
            entry["codes"] = compare_codes(fx, result)
            entry["frequencies"] = {"system": result.frequencies, "expert": expert_frequencies(fx)}
        entry["globals"] = compare_globals(fx, result)
        entry["system_output"] = {
            "codes": [c.__dict__ for c in result.codes or []],
            "globals": result.globals,
            "processes": result.processes,
            "feedback": result.feedback,
            "debug": result.debug,
        }
        entries.append(entry)
        print_session(entry)

    summaries = {s: aggregate([e for e in entries if e["set"] == s]) for s in SETS if any(e["set"] == s for e in entries)}
    if len(summaries) > 1:
        summaries["gabungan"] = aggregate(entries)
    for name, summary in summaries.items():
        print_summary(name, summary)
    output = Path(args.output) if args.output else default_output_path(args.set, budget)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps({"args": vars(args), "sessions": entries, "summaries": summaries}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nHasil lengkap disimpan ke {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", choices=["ilustrasi", "casaa", "all"], default="ilustrasi")
    parser.add_argument("--sessions", nargs="+", help="ID fixture, atau 'all'. Default: satu sesi per set "
                        f"({', '.join(DEFAULT_SESSION.values())})")
    parser.add_argument("--thinking-budget", help="menimpa thinking budget semua agen evaluator (angka atau none)")
    parser.add_argument("--agents", nargs="+", choices=EVALUATOR_ROLES, help="jalankan sebagian agen saja")
    parser.add_argument("--change-target-override", nargs="+", default=[], metavar="ID=TARGET",
                        help='mis. casaa_emmy="return to work" (uji sensitivitas target perubahan)')
    parser.add_argument("--dry-run", action="store_true", help="perkirakan panggilan dan token tanpa memanggil Gemini")
    parser.add_argument("--output", help="lokasi file JSON hasil (default: backend/evals/results/<tanggal>_<set>_<model>.json)")
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()

    if get_settings().APP_ENV.lower() == "production" and not args.allow_production:
        sys.exit("APP_ENV=production: skrip ini menolak jalan. Tambahkan --allow-production jika memang disengaja.")
    if args.thinking_budget is not None:
        parse_budget(args.thinking_budget)  # validasi lebih awal
    try:
        chosen = select_fixtures(args.set, args.sessions)
    except FixturesMissing as exc:
        sys.exit(str(exc))
    agents = set(args.agents) if args.agents else None
    overrides = parse_overrides(args.change_target_override)
    unknown = set(overrides) - {fx["fixture_id"] for _s, fx in chosen}
    if unknown:
        sys.exit(f"--change-target-override untuk sesi yang tidak dipilih: {sorted(unknown)}")
    if args.dry_run:
        dry_run(chosen, agents, overrides)
        return
    asyncio.run(run(args, chosen, agents, overrides))


if __name__ == "__main__":
    main()
