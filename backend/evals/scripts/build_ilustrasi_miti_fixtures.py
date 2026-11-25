"""Bangun fixture MITI dari dokumen Ilustrasi SafeSesi (docs/, tidak di-commit).

Fixture hanya untuk pengujian dan pembanding; isinya tidak boleh dipakai sebagai contoh prompt.

    backend/venv/Scripts/python backend/evals/scripts/build_ilustrasi_miti_fixtures.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_state_ilustrasi import DEFAULT_DOCX, REPO_DIR, SESSION_ORDER, read_blocks  # noqa: E402

OUT_DIR = REPO_DIR / "backend" / "evals" / "fixtures" / "ilustrasi"

CODE_NAMES = {
    "Giving Information": "GI",
    "Persuade": "P",
    "Persuade with Permission": "PWP",
    "Question": "Q",
    "Simple Reflection": "SR",
    "Complex Reflection": "CR",
    "Affirm": "AF",
    "Seeking Collaboration": "SEEK",
    "Emphasizing Autonomy": "EA",
    "Confront": "CONFRONT",
}
SHORT_CODES = {"GI": "GI", "P": "P", "PWP": "PWP", "Q": "Q", "SR": "SR", "CR": "CR", "AF": "AF",
               "Seek": "SEEK", "Emphasize": "EA", "Confront": "CONFRONT"}
DIMENSIONS = {
    "Cultivating Change Talk": "cultivating_change_talk",
    "Softening Sustain Talk": "softening_sustain_talk",
    "Partnership": "partnership",
    "Empathy": "empathy",
}
PROCESSES = {"Engaging": "engaging", "Focusing": "focusing", "Evoking": "evoking", "Planning": "planning"}
FEEDBACK_KINDS = {"Kekuatan": "strength", "Area pengembangan": "improvement", "Alternatif respons": "alternative_response"}
CODE_ORDER = list(CODE_NAMES.values())


def parse_duration(text: str) -> int:
    m = re.search(r"(\d+)\s*menit\s*(\d+)\s*detik", text)
    if not m:
        raise ValueError(f"Durasi tidak dikenali: {text!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def k_turns(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"K(\d\d)", text)]


def build() -> list[dict[str, Any]]:
    blocks = read_blocks(DEFAULT_DOCX)
    summaries: dict[str, str] = {}
    sessions: dict[str, dict[str, Any]] = {}
    scen = sess = None
    for kind, value in blocks:
        if kind == "p":
            m = re.match(r"^1\.2\.\d+\s+(SS-[A-Z]+-\d+)", value)
            if m:
                scen, sess = m.group(1), None
            continue
        rows: list[list[str]] = value
        head = [c.strip() for c in rows[0]] if rows else []
        first = head[0] if head else ""
        if sess is None and scen and first == "No." and head[1] == "Isian Kasus":
            summaries[scen] = {r[0].strip(): r[2].strip() for r in rows[1:]}["6"].strip("“”\"")
            continue
        if len(rows) > 1 and rows[1] and rows[1][0].strip() == "Kode skenario dan sesi":
            code = rows[1][1].split(";")[-1].strip()
            info = {r[0].strip(): r[1].strip() for r in rows[1:] if len(r) > 1}
            sess = sessions.setdefault(code, {
                "session_code": code,
                "scenario_code": code.rsplit("-", 1)[0],
                "duration_seconds": parse_duration(info["Durasi ilustratif"]),
                "change_target": info["Target perubahan"],
            })
            continue
        if sess is None:
            continue
        if first.startswith("K / waktu"):
            sess["dialog"] = [(int(r[0][1:3]), r[1].strip(), r[3].strip()) for r in rows[1:] if re.match(r"^K\d\d", r[0])]
        elif first == "Kode perilaku MITI":
            sess["codes_by_turn"] = by_turn = {}
            sess["frequencies"] = {}
            for r in rows[1:]:
                code = CODE_NAMES[r[0].strip()]
                sess["frequencies"][code] = int(r[1])
                for k in k_turns(r[2]):
                    by_turn.setdefault(k, []).append(code)
        elif first == "Giliran" and head[1] == "Kode perilaku":
            sess["reasons"] = {k_turns(r[0])[0]: r[2].strip() for r in rows[1:]}
        elif first == "Penilaian global":
            sess["globals"] = {DIMENSIONS[r[0].strip()]: int(r[1]) for r in rows[1:]}
            sess["global_reasons"] = {DIMENSIONS[r[0].strip()]: r[2].strip() for r in rows[1:]}
        elif first == "Proses MI":
            sess["processes"] = [{"process": PROCESSES[r[0].strip()], "text": r[1].strip()} for r in rows[1:]]
        elif first == "Bagian umpan balik":
            sess["feedback"] = [{"kind": FEEDBACK_KINDS[r[0].strip()], "text": r[1].strip()} for r in rows[1:]]
        elif first.startswith("Giliran · waktu"):
            # Kolom "Kode" tabel vokal: pembanding silang untuk kode per giliran.
            sess["vocal_codes"] = {
                k_turns(r[0])[0]: sorted(SHORT_CODES[c.strip()] for c in r[2].split(",") if c.strip())
                for r in rows[1:]
            }

    out = []
    for code in SESSION_ORDER:
        s = sessions[code]
        by_turn = s["codes_by_turn"]
        for k, codes in s["vocal_codes"].items():
            if sorted(by_turn.get(k, [])) != codes:
                raise ValueError(f"{code} K{k:02d}: tabel frekuensi {by_turn.get(k)} != tabel vokal {codes}")
        for c, n in s["frequencies"].items():
            if n != sum(c in v for v in by_turn.values()):
                raise ValueError(f"{code}: frekuensi {c}={n} tidak cocok dengan daftar giliran")
        turns = []
        for k, counselor, client in s["dialog"]:
            turns.append({
                "turn_no": 2 * k - 1,
                "label": f"K{k:02d}",
                "speaker": "counselor",
                "content": counselor,
                "expected_codes": sorted(by_turn.get(k, []), key=CODE_ORDER.index),
                "acceptable_alternatives": [],
                "same_as_previous_volley": False,
                "not_coded": not by_turn.get(k),
                "global_evidence_notes": [],
                "expert_note": s.get("reasons", {}).get(k),
            })
            turns.append({"turn_no": 2 * k, "label": f"C{k:02d}", "speaker": "client", "content": client})
        out.append({
            "fixture_id": code,
            "title": f"Ilustrasi SafeSesi {code}",
            "source": "Ilustrasi_Sesi_dan_Evaluasi_SafeSesi_final.docx (ilustratif, bukan validasi ahli)",
            "language": "id",
            "duration_known": True,
            "duration_seconds": s["duration_seconds"],
            "change_target": s["change_target"],
            "change_target_assumed": False,
            "initial_summary": summaries[s["scenario_code"]],
            "expected_globals": s["globals"],
            "expected_global_reasons": s["global_reasons"],
            "expected_frequencies": {c: s["frequencies"].get(c, 0) for c in CODE_ORDER},
            "expected_processes": s["processes"],
            "expected_feedback": s["feedback"],
            "turns": turns,
        })
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fx in build():
        path = OUT_DIR / f"{fx['fixture_id']}.json"
        path.write_text(json.dumps(fx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        codes = {t["label"]: t["expected_codes"] for t in fx["turns"] if t["speaker"] == "counselor"}
        print(f"{fx['fixture_id']}: {fx['duration_seconds']} dtk, globals={fx['expected_globals']}")
        print("   ", " ".join(f"{k}:{'+'.join(v) or '-'}" for k, v in codes.items()))


if __name__ == "__main__":
    main()
