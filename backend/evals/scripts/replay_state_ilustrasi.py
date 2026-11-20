"""Replay Peran A (State Updater) terhadap sesi pada dokumen Ilustrasi SafeSesi final.

Peran A diuji secara terisolasi: tiap giliran memakai ucapan konselor, ucapan klien,
dan catatan pembahasan PERSIS dari dokumen (bukan buatan LLM), sedangkan Client State
yang diteruskan ke giliran berikutnya adalah hasil model sendiri. Fungsi yang dipanggil
adalah update_client_state_llm dari aplikasi (termasuk aturan Disclosure di kode);
keluaran mentah LLM juga dicatat untuk melihat seberapa sering kode mengoreksinya.

Pemakaian (dari root repo; skrip ini memanggil Gemini sungguhan kecuali build-fixture):
  # 1) Bangun fixture dari docx (docs/ tidak di-commit; fixture di-commit)
  backend/venv/Scripts/python backend/evals/scripts/replay_state_ilustrasi.py build-fixture
  # 2) Replay. Model ditulis "nama" atau "nama:budget" (budget: angka atau none)
  backend/venv/Scripts/python backend/evals/scripts/replay_state_ilustrasi.py run --models gemini-3.8-flash:0 gemini-3.5-flash-lite:none
  backend/venv/Scripts/python backend/evals/scripts/replay_state_ilustrasi.py run --runs 3 --sessions SS-NAD-01-S01 --show-side-by-side
  # 3) Mode split: State Decision Agent saja (dengan/tanpa alasan, panjang riwayat)
  backend/venv/Scripts/python backend/evals/scripts/replay_state_ilustrasi.py run --mode split --decision-variant no_reason --history-turns 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_DOCX = REPO_DIR / "docs" / "Ilustrasi_Sesi_dan_Evaluasi_SafeSesi_final.docx"
DEFAULT_FIXTURE = BACKEND_DIR / "evals" / "fixtures" / "ilustrasi" / "ilustrasi_state_sessions.json"
SESSION_ORDER = ["SS-NAD-01-S01", "SS-SAR-01-S01", "SS-SAR-01-S02", "SS-HEN-01-S01", "SS-RIN-01-S01"]

# Kecenderungan ambivalensi kondisi awal (dokumen menulisnya sebagai teks bebas).
INITIAL_AMBIVALENCE_LEAN = {
    "SS-NAD-01-S01": "both",  # "Kecenderungan awal: kedua sisi sama kuat."
    "SS-SAR-01-S01": "both",  # "Kecenderungan awal: dua sisi, ragu."
    "SS-SAR-01-S02": "both",  # akhir S1: "Dua sisi, condong mencari tahu biaya ...; belum ada komitmen"
    "SS-HEN-01-S01": "toward_status_quo",  # "mempertahankan keadaan saat ini (sustain talk dominan)"
    "SS-RIN-01-S01": "both",  # "Kecenderungan awal: dua sisi berimbang."
}

LEVELS = ["guarded", "medium", "high"]

# ---------------------------------------------------------------------------
# 1. Parsing docx -> fixture
# ---------------------------------------------------------------------------

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _para_text(p: ET.Element) -> str:
    parts: list[str] = []
    for node in p.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
        elif node.tag == W + "tab":
            parts.append(" ")
    return "".join(parts).strip()


def read_blocks(docx: Path) -> list[tuple[str, Any]]:
    """Urutan blok dokumen: ("p", teks) atau ("tbl", [[sel, ...], ...])."""
    body = ET.fromstring(zipfile.ZipFile(docx).read("word/document.xml")).find(W + "body")
    blocks: list[tuple[str, Any]] = []
    for el in body:
        if el.tag == W + "p":
            text = _para_text(el)
            if text:
                blocks.append(("p", text))
        elif el.tag == W + "tbl":
            rows = []
            for tr in el.iter(W + "tr"):
                cells = []
                for tc in tr.findall(W + "tc"):
                    cells.append("\n".join(t for t in (_para_text(p) for p in tc.iter(W + "p")) if t))
                rows.append(cells)
            blocks.append(("tbl", rows))
    return blocks


def parse_level(text: str) -> str:
    """Tingkat Disclosure dari teks dokumen: label pertama yang muncul."""
    hits = []
    for level, label in (("guarded", "Terbatas (Guarded"), ("medium", "Sedang (Medium"), ("high", "Tinggi (High")):
        i = text.find(label)
        if i >= 0:
            hits.append((i, level))
    if not hits:
        raise ValueError(f"Tingkat Disclosure tidak dikenali: {text!r}")
    return min(hits)[1]


def parse_discord(text: str) -> bool:
    t = text.strip().lower()
    if t.startswith("tidak tampak"):
        return False
    if t.startswith("tampak") or t.startswith("mulai tampak"):
        return True
    raise ValueError(f"Status Discord tidak dikenali: {text!r}")


STATE_RE = re.compile(
    r"Emotion:\s*(?P<emotion>.*?)\s*Disclosure:\s*(?P<disclosure>.*?)\s*Ambivalence:\s*(?P<ambivalence>.*?)\s*Discord:\s*(?P<discord>.*)",
    re.S,
)


def parse_state_cell(cell: str) -> dict[str, Any]:
    m = STATE_RE.search(cell.replace("\n", " "))
    if not m:
        raise ValueError(f"Sel Client State tidak dikenali: {cell[:120]!r}")
    g = {k: v.strip() for k, v in m.groupdict().items()}
    return {
        "emotion": g["emotion"],
        "disclosure_level": parse_level(g["disclosure"]),
        "disclosure_text": g["disclosure"],
        "ambivalence": g["ambivalence"],
        "discord_present": parse_discord(g["discord"]),
        "discord_text": g["discord"],
    }


def split_notes(cell: str, topic_names: list[str]) -> dict[str, str]:
    """'Catatan pembahasan setelah C04<Topik A>: ...<Topik B>: ...' -> {topik: deskripsi}."""
    text = re.sub(r"^Catatan pembahasan setelah C\d+", "", cell.replace("\n", " ").strip())
    marks = sorted((text.find(f"{name}:"), name) for name in topic_names if f"{name}:" in text)
    notes = {}
    for idx, (pos, name) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(text)
        notes[name] = text[pos + len(name) + 1 : end].strip()
    return notes


def parse_reasons(ambivalence: str) -> tuple[str | None, str | None]:
    change = re.search(r"Alasan berubah:\s*(.*?)(?:Alasan bertahan:|$)", ambivalence)
    maintain = re.search(r"Alasan bertahan:\s*(.*?)(?:Kecenderungan awal:|$)", ambivalence)
    return (change.group(1).strip(" .") if change else None, maintain.group(1).strip(" .") if maintain else None)


def _age(text: str) -> int:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else 0


def build_fixture(docx: Path) -> dict[str, Any]:
    blocks = read_blocks(docx)
    scenarios: dict[str, dict[str, Any]] = {}
    sessions: dict[str, dict[str, Any]] = {}
    scen = None
    sess = None

    for kind, value in blocks:
        if kind == "p":
            m = re.match(r"^1\.2\.\d+\s+(SS-[A-Z]+-\d+)", value)
            if m:
                scen = scenarios.setdefault(m.group(1), {"code": m.group(1)})
                sess = None
            continue

        rows: list[list[str]] = value
        header = [c.strip() for c in rows[0]] if rows else []
        first = header[0] if header else ""

        if len(rows) > 1 and rows[1] and rows[1][0].strip() == "Kode skenario dan sesi":
            code = rows[1][1].split(";")[-1].strip()
            sess = sessions.setdefault(code, {"session_code": code, "scenario_code": code.rsplit("-", 1)[0]})
            sess["notes"] = {r[0].strip(): r[1].strip() for r in rows[1:] if len(r) > 1}
            continue

        if sess is None and scen is not None:
            if first == "No." and header[1] == "Isian Persona":
                p = {r[0].strip(): r[2].strip() for r in rows[1:]}
                scen["persona"] = {
                    "name": p["1"].split(";")[0].strip(),
                    "age": _age(p["2"]),
                    "gender": p["3"].rstrip("."),
                    "education": p["4"],
                    "occupation": p["5"],
                    "marital_status": p["6"],
                    "family_background": p["7"],
                    "personality": p["8"],
                    "communication_style": p["9"],
                    "additional_background": p["10"],
                }
            elif first == "No." and header[1] == "Isian Kasus":
                c = {r[0].strip(): r[2].strip() for r in rows[1:]}
                scen["case"] = {
                    "main_problem": c["1"],
                    "history_impact": c["2"],
                    "expectation_change_context": c["3"],
                    "health_condition": c["5"],
                    "initial_summary": c["6"].strip("“”\""),
                }
            elif first == "Kode" and header[1] == "Judul singkat":
                scen["hidden_facts"] = [
                    {"code": r[0].strip(), "short_title": r[1].strip(), "fact": r[2].strip(), "min_disclosure_level": parse_level(r[3])}
                    for r in rows[1:]
                ]
            elif first == "Komponen" and header[1] == "Kondisi awal":
                d = {r[0].strip(): r[1].strip() for r in rows[1:]}
                change, maintain = parse_reasons(d["Ambivalence"])
                scen["initial_state_doc"] = d
                scen["initial_state"] = {
                    "emotion_type": d["Emotion"],
                    "emotion_cause": None,
                    "disclosure_level": parse_level(d["Disclosure"]),
                    "disclosure_trigger": "Kondisi awal skenario",
                    "reasons_to_change": change,
                    "reasons_to_maintain": maintain,
                    "ambivalence_lean": None,  # diisi per sesi dari INITIAL_AMBIVALENCE_LEAN
                    "discord_present": parse_discord(d["Discord"]),
                    "discord_context": None,
                    "discord_response": None,
                }
            elif first == "No." and header[1].startswith("Topik yang Ditetapkan"):
                scen["topics"] = [r[1].strip() for r in rows[1:]]
            continue

        if sess is None:
            continue

        if first == "Topik" and len(header) > 1 and header[1].startswith("Catatan awal sesi"):
            sess["initial_notes"] = {r[0].strip(): r[1].strip() for r in rows[1:]}
        elif first.startswith("K / waktu"):
            topic_names = scenarios[sess["scenario_code"]]["topics"]
            turns = []
            for r in rows[1:]:
                if r[0].startswith("Client State setelah"):
                    turns[-1]["state_after"] = parse_state_cell(r[0])
                    turns[-1]["notes_after"] = split_notes(r[1], topic_names) if len(r) > 1 else {}
                elif re.match(r"^K\d\d", r[0]):
                    turns.append({"turn": int(r[0][1:3]), "counselor": r[1].strip(), "client": r[3].strip()})
            sess["turns"] = turns
        elif first == "Komponen" and len(header) > 1 and header[1] == "Catatan akhir":
            d = {r[0].strip(): r[1].strip() for r in rows[1:]}
            sess["final_state_doc"] = {
                "emotion": d["Emotion"],
                "disclosure_level": parse_level(d["Disclosure"]),
                "ambivalence": d["Ambivalence"],
                "discord_present": parse_discord(d["Discord"]),
            }

    out_sessions = []
    for code in SESSION_ORDER:
        s = sessions[code]
        sc = scenarios[s["scenario_code"]]
        if code.endswith("-S01"):
            initial = dict(sc["initial_state"])
            parent = None
            initial_notes = {name: "" for name in sc["topics"]}
        else:
            # Sesi lanjutan: state awal = Client State akhir sesi induk menurut dokumen
            parent = code[:-3] + "S01"
            final = sessions[parent]["final_state_doc"]
            initial = {
                "emotion_type": final["emotion"],
                "emotion_cause": None,
                "disclosure_level": final["disclosure_level"],
                "disclosure_trigger": "Tingkat akhir sesi sebelumnya",
                "reasons_to_change": None,
                "reasons_to_maintain": None,
                "ambivalence_lean": None,
                "discord_present": final["discord_present"],
                "discord_context": None,
                "discord_response": None,
            }
            initial_notes = {name: s.get("initial_notes", {}).get(name, "") for name in sc["topics"]}
        initial["ambivalence_lean"] = INITIAL_AMBIVALENCE_LEAN[code]
        if len(s["turns"]) != 10 or any("state_after" not in t for t in s["turns"]):
            raise ValueError(f"{code}: transkrip tidak lengkap ({len(s['turns'])} giliran)")
        out_sessions.append(
            {
                "session_code": code,
                "scenario_code": s["scenario_code"],
                "parent_session_code": parent,
                "initial_state": initial,
                "initial_notes": initial_notes,
                "turns": s["turns"],
                "final_state_doc": s.get("final_state_doc"),
            }
        )

    return {
        "source": docx.name,
        "note": (
            "Dibangun otomatis oleh evals/scripts/replay_state_ilustrasi.py build-fixture. "
            "ambivalence_lean kondisi awal dipetakan manual dari teks dokumen (INITIAL_AMBIVALENCE_LEAN). "
            "Sesi lanjutan memakai Client State akhir sesi induk dari dokumen; dokumen tidak memisahkan "
            "alasan berubah/bertahan pada state akhir, sehingga reasons_* bernilai null."
        ),
        "scenarios": {code: {k: v for k, v in sc.items() if k != "initial_state"} for code, sc in scenarios.items()},
        "sessions": out_sessions,
    }


# ---------------------------------------------------------------------------
# 2. Replay Peran A
# ---------------------------------------------------------------------------


def parse_model_arg(text: str) -> tuple[str, int | None]:
    if ":" not in text:
        return text, 0
    name, budget = text.split(":", 1)
    return name, None if budget.strip().lower() in ("none", "") else int(budget)


class RateLimiter:
    """Menjaga jarak antarpanggilan Gemini (kuota RPM). Jeda terjadi sebelum pengukuran waktu."""

    def __init__(self, rpm: float) -> None:
        self.interval = 60.0 / rpm if rpm else 0.0
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = max(now, self._next) + self.interval


class RecordingLLM:
    """Membungkus client Gemini: mencatat keluaran mentah Peran A sebelum aturan di kode."""

    TRANSIENT = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.last_raw: Any = None
        self.last_ms: float = 0.0

    async def generate_json(self, **kwargs: Any) -> Any:
        """Retry gangguan sementara Gemini (kuota/permintaan ramai) dengan jeda; last_ms hanya
        durasi panggilan yang berhasil, jadi jeda retry tidak masuk ke angka durasi."""
        for attempt in range(6):
            t0 = time.perf_counter()
            try:
                result = await self.inner.generate_json(**kwargs)
            except Exception as exc:
                if attempt == 5 or not any(code in str(exc) for code in self.TRANSIENT):
                    raise
                print(f"    gangguan sementara Gemini, coba lagi dalam 30 dtk: {str(exc)[:80]}", flush=True)
                await asyncio.sleep(30)
                continue
            self.last_ms = (time.perf_counter() - t0) * 1000
            self.last_raw = result
            return result


async def replay_session(
    session: dict[str, Any], scenario: dict[str, Any], parent_turns: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    """cfg: mode (combined|split), decision_variant (reason|no_reason), history_turns.

    Mode split hanya menjalankan State Decision Agent; field deskriptif state diteruskan dari
    kondisi awal (State Detail Agent tidak ikut di-replay).
    """
    from services.llm.gemini_client import get_gemini_client, track_usage
    from services.simulation import state_updater

    recorder = RecordingLLM(get_gemini_client())
    state = dict(session["initial_state"])
    history = [h for t in parent_turns for h in ({"speaker": "counselor", "content": t["counselor"]}, {"speaker": "client", "content": t["client"]})]
    notes = dict(session["initial_notes"])
    results = []
    for turn in session["turns"]:
        topic_notes = [{"topic_name": name, "description": desc} for name, desc in notes.items()]
        usage: dict[str, dict[str, int]] = {}
        track_usage(usage)
        await cfg["limiter"].wait()
        # recorder dipasang per panggilan: state_updater memanggil get_gemini_client() di dalam fungsi
        state_updater.get_gemini_client = lambda: recorder
        if cfg["mode"] == "split":
            decided = await state_updater.update_client_state_decision(
                counselor_utterance=turn["counselor"],
                current_state=state,
                persona=scenario["persona"],
                case_data=scenario["case"],
                transcript_history=history,
                with_reasons=cfg["decision_variant"] == "reason",
                history_turns=cfg["history_turns"],
            )
            new_state = state_updater.ClientState(
                **{
                    **state,
                    "emotion_type": decided.emotion_short,
                    "disclosure_level": decided.disclosure_level,
                    "discord_present": decided.discord_present,
                    "ambivalence_lean": decided.ambivalence_lean,
                }
            )
        else:
            new_state = await state_updater.update_client_state_llm(
                counselor_utterance=turn["counselor"],
                current_state=state,
                persona=scenario["persona"],
                case_data=scenario["case"],
                transcript_history=history,
                topic_notes=topic_notes,
            )
        ms = recorder.last_ms
        raw = recorder.last_raw
        tok = next(iter(usage.values()), {"input": 0, "output": 0})
        results.append(
            {
                "turn": turn["turn"],
                "ms": round(ms),
                "input_tokens": tok["input"],
                "output_tokens": tok["output"],
                "disclosure_level": new_state.disclosure_level,
                "raw_disclosure_level": raw.disclosure_level if raw is not None else None,
                "discord_present": new_state.discord_present,
                "emotion_type": new_state.emotion_type,
                "ambivalence_lean": new_state.ambivalence_lean,
                "reasons_to_change": new_state.reasons_to_change,
                "reasons_to_maintain": new_state.reasons_to_maintain,
            }
        )
        state = new_state.model_dump(exclude={"id", "session_id", "turn_id", "created_at"})
        history += [{"speaker": "counselor", "content": turn["counselor"]}, {"speaker": "client", "content": turn["client"]}]
        notes.update(turn["notes_after"])
    return {"turns": results}


def transitions(levels: list[str], discords: list[bool], start_level: str, start_discord: bool) -> dict[str, list[int]]:
    rises, appear, subside = [], [], []
    prev_l, prev_d = start_level, start_discord
    for i, (lvl, d) in enumerate(zip(levels, discords), start=1):
        if LEVELS.index(lvl) > LEVELS.index(prev_l):
            rises.append(i)
        if d and not prev_d:
            appear.append(i)
        if prev_d and not d:
            subside.append(i)
        prev_l, prev_d = lvl, d
    return {"rise": rises, "discord_on": appear, "discord_off": subside}


def fmt_turns(xs: list[int]) -> str:
    return ",".join(f"K{x:02d}" for x in xs) or "-"


async def run_replay(args: argparse.Namespace) -> None:
    from core.config import get_settings

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    sessions = [s for s in fixture["sessions"] if not args.sessions or s["session_code"] in args.sessions]
    by_code = {s["session_code"]: s for s in fixture["sessions"]}
    settings = get_settings()
    sem = asyncio.Semaphore(args.concurrency)
    all_results: dict[str, Any] = {}

    cfg = {
        "mode": args.mode,
        "decision_variant": args.decision_variant,
        "history_turns": args.history_turns,
        "limiter": RateLimiter(args.rpm),
    }
    for model_arg in args.models:
        model, budget = parse_model_arg(model_arg)
        settings.GEMINI_MODEL_STATE = settings.GEMINI_MODEL_STATE_DECISION = model
        settings.GEMINI_THINKING_BUDGET_STATE = settings.GEMINI_THINKING_BUDGET_STATE_DECISION = budget
        label = f"{model} (budget={'none' if budget is None else budget})"
        if args.mode == "split":
            label += f" split/{args.decision_variant}/riwayat {args.history_turns}"
        else:
            label += " combined"
        print(f"\n=== Model {label}: {len(sessions)} sesi x {args.runs} run ===", flush=True)

        async def one(session: dict[str, Any], run: int) -> tuple[str, int, dict[str, Any]]:
            async with sem:
                scenario = fixture["scenarios"][session["scenario_code"]]
                parent = by_code[session["parent_session_code"]]["turns"] if session["parent_session_code"] else []
                res = await replay_session(session, scenario, parent, cfg)
                print(f"  selesai {session['session_code']} run {run + 1}", flush=True)
                return session["session_code"], run, res

        done = await asyncio.gather(*(one(s, r) for s in sessions for r in range(args.runs)))
        per_session: dict[str, list[dict[str, Any]]] = {}
        for code, run, res in sorted(done, key=lambda x: (x[0], x[1])):
            per_session.setdefault(code, []).append(res)
        all_results[label] = per_session

    summary_rows = []
    for label, per_session in all_results.items():
        for session in sessions:
            code = session["session_code"]
            runs = per_session[code]
            doc_levels = [t["state_after"]["disclosure_level"] for t in session["turns"]]
            doc_discord = [t["state_after"]["discord_present"] for t in session["turns"]]
            start_l, start_d = session["initial_state"]["disclosure_level"], session["initial_state"]["discord_present"]
            doc_tr = transitions(doc_levels, doc_discord, start_l, start_d)

            print(f"\n--- {code} | {label}")
            print(f"  dokumen : disclosure naik {fmt_turns(doc_tr['rise'])} | discord muncul {fmt_turns(doc_tr['discord_on'])} | mereda {fmt_turns(doc_tr['discord_off'])}")
            print(f"            disclosure {' '.join(l[0].upper() for l in doc_levels)} | discord {' '.join('D' if d else '.' for d in doc_discord)}")
            d_match, x_match, ms_all, corrections = [], [], [], 0
            tok_in = [t["input_tokens"] for r in runs for t in r["turns"]]
            tok_out = [t["output_tokens"] for r in runs for t in r["turns"]]
            doc_reaches_high = "high" in doc_levels
            false_high_runs = sum(
                1 for r in runs if not doc_reaches_high and any(t["disclosure_level"] == "high" for t in r["turns"])
            )
            for i, res in enumerate(runs, start=1):
                levels = [t["disclosure_level"] for t in res["turns"]]
                discords = [t["discord_present"] for t in res["turns"]]
                tr = transitions(levels, discords, start_l, start_d)
                dm = sum(a == b for a, b in zip(levels, doc_levels))
                xm = sum(a == b for a, b in zip(discords, doc_discord))
                corr = sum(1 for t in res["turns"] if t["raw_disclosure_level"] != t["disclosure_level"])
                d_match.append(dm)
                x_match.append(xm)
                corrections += corr
                ms_all += [t["ms"] for t in res["turns"]]
                print(
                    f"  run {i}   : disclosure naik {fmt_turns(tr['rise'])} | discord muncul {fmt_turns(tr['discord_on'])} | mereda {fmt_turns(tr['discord_off'])}"
                    f" | cocok disclosure {dm}/10, discord {xm}/10 | koreksi kode {corr}"
                )
                print(f"            disclosure {' '.join(l[0].upper() for l in levels)} | discord {' '.join('D' if d else '.' for d in discords)}")
            avg_ms = statistics.mean(ms_all)
            print(f"  rata-rata Peran A: {avg_ms:.0f} ms (median {statistics.median(ms_all):.0f} ms)")

            if args.show_side_by_side:
                first = runs[0]["turns"]
                print("  emotion & ambivalence (run 1) — dokumen | model:")
                for t, m in zip(session["turns"], first):
                    s = t["state_after"]
                    print(f"    K{t['turn']:02d} E: {s['emotion'][:70]}")
                    print(f"         | {m['emotion_type'][:70]}")
                    print(f"        A: {s['ambivalence'][:70]}")
                    print(f"         | {m['ambivalence_lean']}: +{(m['reasons_to_change'] or '-')[:30]} / -{(m['reasons_to_maintain'] or '-')[:30]}")

            summary_rows.append(
                {
                    "session": code,
                    "model": label,
                    "disclosure_match": statistics.mean(d_match),
                    "discord_match": statistics.mean(x_match),
                    "rise_doc": fmt_turns(doc_tr["rise"]),
                    "rise_model": " / ".join(
                        fmt_turns(transitions([t["disclosure_level"] for t in r["turns"]], [t["discord_present"] for t in r["turns"]], start_l, start_d)["rise"])
                        for r in runs
                    ),
                    "discord_doc": f"{fmt_turns(doc_tr['discord_on'])}->{fmt_turns(doc_tr['discord_off'])}",
                    "discord_model": " / ".join(
                        "{}->{}".format(
                            *(fmt_turns(v) for v in [
                                transitions([t["disclosure_level"] for t in r["turns"]], [t["discord_present"] for t in r["turns"]], start_l, start_d)[k]
                                for k in ("discord_on", "discord_off")
                            ])
                        )
                        for r in runs
                    ),
                    "avg_ms": round(avg_ms),
                    "corrections": corrections,
                    "false_high": f"{false_high_runs}/{len(runs)}" if not doc_reaches_high else "n/a",
                    "avg_input_tokens": round(statistics.mean(tok_in)),
                    "avg_output_tokens": round(statistics.mean(tok_out)),
                }
            )

    print("\n=== Ringkasan (cocok = rata-rata giliran sama dengan dokumen dari 10; per run dipisah '/') ===")
    print("High palsu = jumlah run yang naik ke high padahal dokumen tidak mencapai high (n/a = dokumen mencapai high)")
    header = ["Sesi", "Model", "Cocok D", "Cocok Dc", "Naik: dok", "Naik: model", "Discord dok", "Discord model", "High palsu", "A ms", "Tok in", "Tok out", "Koreksi"]
    print(" | ".join(header))
    for r in summary_rows:
        print(
            f"{r['session']} | {r['model']} | {r['disclosure_match']:.1f} | {r['discord_match']:.1f} | {r['rise_doc']} | {r['rise_model']} | "
            f"{r['discord_doc']} | {r['discord_model']} | {r['false_high']} | {r['avg_ms']} | {r['avg_input_tokens']} | {r['avg_output_tokens']} | {r['corrections']}"
        )

    if args.output:
        Path(args.output).write_text(json.dumps({"summary": summary_rows, "results": all_results}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nHasil lengkap: {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-fixture", help="Bangun fixture JSON dari docx Ilustrasi")
    b.add_argument("--docx", default=str(DEFAULT_DOCX))
    b.add_argument("--out", default=str(DEFAULT_FIXTURE))

    r = sub.add_parser("run", help="Replay Peran A terhadap fixture")
    r.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    r.add_argument("--models", nargs="+", default=["gemini-3.8-flash:0"], help="nama[:budget], budget angka atau none")
    r.add_argument("--runs", type=int, default=3, help="jumlah run per model (LLM tidak deterministik)")
    r.add_argument("--sessions", nargs="*", help="batasi ke kode sesi tertentu")
    r.add_argument("--concurrency", type=int, default=4, help="jumlah sesi yang di-replay bersamaan")
    r.add_argument("--show-side-by-side", action="store_true", help="tampilkan emotion & ambivalence dokumen vs model")
    r.add_argument("--output", help="simpan hasil lengkap ke file JSON")
    r.add_argument("--mode", choices=["combined", "split"], default="combined", help="split: State Decision Agent saja")
    r.add_argument("--decision-variant", choices=["reason", "no_reason"], default="reason", help="mode split: dengan/tanpa field alasan")
    r.add_argument("--history-turns", type=int, default=4, help="mode split: jumlah giliran riwayat di prompt")
    r.add_argument("--rpm", type=float, default=0, help="batas panggilan Gemini per menit (0 = tanpa batas)")

    args = parser.parse_args()
    if args.cmd == "build-fixture":
        fixture = build_fixture(Path(args.docx))
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
        for s in fixture["sessions"]:
            levels = " ".join(t["state_after"]["disclosure_level"][0].upper() for t in s["turns"])
            discord = " ".join("D" if t["state_after"]["discord_present"] else "." for t in s["turns"])
            print(f"{s['session_code']}: awal {s['initial_state']['disclosure_level']}, {len(s['turns'])} giliran | disclosure {levels} | discord {discord}")
        print(f"Fixture: {out}")
    else:
        asyncio.run(run_replay(args))


if __name__ == "__main__":
    main()
