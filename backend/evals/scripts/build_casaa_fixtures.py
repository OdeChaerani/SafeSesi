"""Bangun fixture gold standard MITI dari transkrip latihan CASAA (PDF) di docs/.

Fixture hanya untuk pengujian dan pembanding; isinya tidak boleh dipakai sebagai contoh prompt.
Butuh `pdftotext` (xpdf/poppler) di PATH dan PDF di docs/coded-transcript-miti/. Hasilnya
(backend/evals/fixtures/casaa/) TIDAK di-commit karena hak cipta CASAA; bangun ulang di tiap mesin.

    backend/venv/Scripts/python backend/evals/scripts/build_casaa_fixtures.py                # ketiga transkrip
    backend/venv/Scripts/python backend/evals/scripts/build_casaa_fixtures.py --only smoker  # satu transkrip
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parents[3]
PDF_DIR = REPO_DIR / "docs" / "coded-transcript-miti"
OUT_DIR = REPO_DIR / "backend" / "evals" / "fixtures" / "casaa"

ASSUMED_TARGET_NOTE = (
    "Target perubahan ditetapkan peneliti karena transkrip CASAA tidak mencantumkannya "
    "(MITI 4.2.1 bagian C mewajibkan target ditetapkan sebelum pengodean)."
)

TRANSCRIPTS: dict[str, dict[str, Any]] = {
    "smoker": {
        "pdf": "have-you-ever-been-a-smoker-coded-transcript.pdf",
        "title": 'MITI 4 Training "Have you ever been a smoker?"',
        "change_target": "quit smoking",
    },
    "emmy": {
        "pdf": "emmys-first-encounter-coded-transcript.pdf",
        "title": "Emmy's First Encounter with an IPV Counselor",
        "change_target": "increase safety for herself and her baby (safety planning)",
    },
    "cheryl": {
        "pdf": "session1miti.pdf",
        "title": "CASAA MITI 4 Coding Training Series - Manuel #1 (Cheryl)",
        "change_target": "reduce drinking",
    },
}

# Penulisan kode di transkrip CASAA -> label enum miti_code. "EMP" di Emmy #53 adalah
# Emphasize (isi ujarannya menegaskan klien sebagai pengambil keputusan), bukan Empathy.
CODE_ALIASES = {
    "GI": "GI",
    "PERSUADE WITH": "PWP",
    "PERSUADE W": "PWP",
    "PWP": "PWP",
    "PERSUADE": "P",
    "Q": "Q",
    "SR": "SR",
    "CR": "CR",
    "AF": "AF",
    "AFF": "AF",
    "AFFIRM": "AF",
    "SEEK": "SEEK",
    "EMPHASIZE": "EA",
    "EMP": "EA",
    "CONFRONT": "CONFRONT",
    "NC": "NC",
    "NOT CODED": "NC",
    "SAME": "SAME",
}
_CODE_ALT = "|".join(sorted((re.escape(k) for k in CODE_ALIASES), key=len, reverse=True))
CODE_RE = re.compile(rf"(?i)(?<![A-Za-z])({_CODE_ALT})(?![A-Za-z])")
# Baris sel kode: satu/lebih kode (dipisah , ;) lalu sisa teks opsional (catatan ahli).
CODE_LINE_RE = re.compile(rf"(?i)^\s*((?:{_CODE_ALT})(?:\s*[,;]\s*(?:{_CODE_ALT}))*)\s*[,;]?\s*(.*)$")
EVIDENCE_RE = re.compile(r"\(?\s*\+\s*([A-Za-z]+)\s*\)?")
INLINE_UNIT_RE = re.compile(r"\s*\((GI|Emphasize|Seek|SR|CR|Q|AF|Confront|Persuade)\)([.,;!?]?)")
ROW_RE = re.compile(r"^(\s*)(\d+)\s+([PC])(\s+|$)")
GLOBAL_START_RE = re.compile(r"^\s*(Global|CULTIVATING|CCT)\b", re.I)
GLOBAL_RES = {
    "cultivating_change_talk": re.compile(r"\b(?:CCT|CULTIVATING)\W*([1-5])\b", re.I),
    "softening_sustain_talk": re.compile(r"\b(?:SST|SOFTENING)\W*([1-5])\b", re.I),
    "partnership": re.compile(r"\b(?:PAR|PARTNERSHIP)\W*([1-5])\b", re.I),
    "empathy": re.compile(r"\b(?:EMP|EMPATHY)\W*([1-5])\b", re.I),
}
EVIDENCE_DIMENSIONS = {
    "CULTIVATE": "cultivating_change_talk",
    "SOFTEN": "softening_sustain_talk",
    "SIDESTEP": "softening_sustain_talk",
    "PARTNER": "partnership",
    "PAR": "partnership",
    "EMP": "empathy",
    "EMPATHY": "empathy",
}

# Sel yang tidak dapat diurai aman secara otomatis; ditetapkan manual dari PDF.
# Kunci: (transkrip, nomor ujaran berurutan).
OVERRIDES: dict[tuple[str, int], dict[str, Any]] = {
    # Sel berisi "GI / Support, NC / AF": NC hanya untuk unit pernyataan dukungan, bukan
    # seluruh volley. Baris NC/AF muncul setelah teks catatan sehingga tidak terbaca otomatis.
    ("emmy", 37): {"expected_codes": ["GI", "AF"], "expert_note": "Support, NC (unit pernyataan dukungan tidak dikode)"},
}


def pdf_to_pages(pdf: Path) -> list[list[str]]:
    if not shutil.which("pdftotext"):
        sys.exit("pdftotext tidak ditemukan di PATH (dibutuhkan untuk membaca PDF CASAA).")
    out = subprocess.run(
        ["pdftotext", "-table", "-enc", "UTF-8", str(pdf), "-"],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return [page.splitlines() for page in out.split("\f")]


def segments(line: str) -> list[tuple[int, int, str]]:
    """Potongan teks dipisah >=2 spasi: (awal, celah sebelum, teks)."""
    result, prev_end = [], 0
    for m in re.finditer(r"\S+(?: \S+)*", line):
        result.append((m.start(), m.start() - prev_end, m.group()))
        prev_end = m.end()
    return result


def detect_columns(lines: list[str], has_explanation: bool) -> tuple[int, int | None, int]:
    """Kolom isi, kolom kode, kolom penjelasan per halaman (posisi berbeda antarhalaman)."""
    content_cols = [m.end() for line in lines if (m := ROW_RE.match(line)) and m.group(4)]
    content_col = min(content_cols) if content_cols else 8
    right = []
    for line in lines:
        segs = segments(line)
        for i, (start, gap, _text) in enumerate(segs):
            if start >= content_col + 25 and (i > 0 and gap >= 3 or i == 0):
                right.append(start)
    code_col = min(right) if right else 10_000
    expl_col = None
    if has_explanation:
        later = [s for s in right if s > code_col + 6]
        expl_col = min(later) if later else None
    return content_col, expl_col, code_col


def read_rows(pdf: Path) -> tuple[list[dict[str, Any]], list[str]]:
    pages = pdf_to_pages(pdf)
    has_explanation = any("Explanation" in line for line in pages[0])
    rows: list[dict[str, Any]] = []
    tail: list[str] = []
    in_globals = False
    started = False
    for lines in pages:
        if not any(line.strip() for line in lines):
            continue
        content_col, expl_col, code_col = detect_columns(lines, has_explanation)
        title_skipped = False
        for line in lines:
            if not line.strip():
                continue
            if not title_skipped:
                title_skipped = True  # baris judul tiap halaman
                continue
            if in_globals or GLOBAL_START_RE.match(line):
                in_globals = True
                tail.append(line.strip())
                continue
            m = ROW_RE.match(line)
            if m:
                started = True
                rows.append({"source_utt_no": int(m.group(2)), "speaker": m.group(3),
                             "content": [], "code": [], "expl": []})
            elif not started:
                continue  # header tabel di halaman pertama
            row = rows[-1]
            body = line[m.end():] if m else line
            offset = m.end() if m else 0
            for start, _gap, text in segments(body):
                col = start + offset
                if expl_col is not None and col >= expl_col - 1:
                    row["expl"].append(text)
                elif col >= code_col - 1:
                    row["code"].append(text)
                else:
                    row["content"].append(text)
    return rows, tail


def parse_code_cell(code_lines: list[str]) -> dict[str, Any]:
    """Urai sel kode: kode, alternatif yang diterima, penanda bukti global, catatan ahli.

    Kode dibaca dari baris awal sel; begitu muncul teks catatan, sisanya dianggap catatan.
    Baris berisi kode saja yang diikuti baris berhuruf kecil adalah awal catatan
    (mis. "Emphasize / considered but ruled out ...").
    """
    text = "\n".join(code_lines)
    evidence = [m.group(1) for m in EVIDENCE_RE.finditer(text)]
    text = EVIDENCE_RE.sub(" ", text)
    text = re.sub(r"(?i)persuade\s*\n\s*with\b", "Persuade with", text)
    text = re.sub(r"(?i)\bNOT\s*\n\s*CODED\b", "NOT CODED", text)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    codes: list[str] = []
    notes: list[str] = []
    for i, line in enumerate(lines):
        m = CODE_LINE_RE.match(line) if not notes else None
        next_lower = i + 1 < len(lines) and re.match(r"[a-z]{2,}\b", lines[i + 1]) is not None
        if m and not (not m.group(2) and next_lower):
            codes += [CODE_ALIASES[c.upper()] for c in CODE_RE.findall(m.group(1))]
            if m.group(2):
                notes.append(m.group(2))
        else:
            notes.append(line)
    note = " ".join(notes).strip() or None
    alternatives = []
    if note:
        for m in re.finditer(r"(?i)would not be\s+wrong to consider an?\s+([A-Za-z]+)", note):
            alternatives.append(CODE_ALIASES[m.group(1).upper()])
    return {"codes": codes, "notes": note, "evidence": evidence, "alternatives": alternatives}


def parse_globals(tail: list[str]) -> dict[str, int]:
    text = " ".join(tail)
    scores = {}
    for dim, rx in GLOBAL_RES.items():
        m = rx.search(text)
        if not m:
            raise ValueError(f"Skor global {dim} tidak ditemukan di: {text!r}")
        scores[dim] = int(m.group(1))
    return scores


def build_transcript(key: str) -> dict[str, Any]:
    meta = TRANSCRIPTS[key]
    rows, tail = read_rows(PDF_DIR / meta["pdf"])
    turns, warnings = [], []
    for turn_no, row in enumerate(rows, start=1):
        content = " ".join(row["content"]).strip()
        if row["source_utt_no"] != turn_no:
            warnings.append(f"ujaran #{turn_no}: nomor tercetak di PDF {row['source_utt_no']}")
        expected_turn_speaker = "P" if turn_no % 2 else "C"
        if row["speaker"] != expected_turn_speaker:
            warnings.append(f"ujaran #{turn_no}: pembicara {row['speaker']} tidak berselang-seling")
        turn: dict[str, Any] = {
            "turn_no": turn_no,
            "source_utt_no": row["source_utt_no"],
            "speaker": "counselor" if row["speaker"] == "P" else "client",
        }
        if row["speaker"] == "C":
            if row["code"] or row["expl"]:
                warnings.append(f"ujaran #{turn_no} (klien) punya teks di kolom kode: {row['code'] + row['expl']}")
            turn["content"] = content
            turns.append(turn)
            continue

        # Anotasi kode inline di isi ujaran (mis. smoker #49 "(GI)") dibuang dari teks yang
        # dikirim ke evaluator, disimpan sebagai pembagian unit menurut ahli.
        units, last = [], 0
        for m in INLINE_UNIT_RE.finditer(content):
            units.append({"excerpt": (content[last:m.start()] + m.group(2)).strip(),
                          "code": CODE_ALIASES[m.group(1).upper()]})
            last = m.end()
        if units:
            content = INLINE_UNIT_RE.sub(lambda m: m.group(2), content)
        cell = parse_code_cell(row["code"])
        codes = cell["codes"]
        if units and not codes:
            codes = [u["code"] for u in units]
        expert_notes = [n for n in (cell["notes"], " ".join(row["expl"]) or None) if n]
        same = "SAME" in codes
        real = [c for c in dict.fromkeys(codes) if c not in ("SAME", "NC")]
        turn.update(
            content=content,
            expected_codes=real,
            acceptable_alternatives=cell["alternatives"],
            same_as_previous_volley=same,
            not_coded=not real and not same,
            global_evidence_notes=[
                {"marker": f"+{e}", "dimension": EVIDENCE_DIMENSIONS.get(e.upper())} for e in cell["evidence"]
            ],
            expert_note=" | ".join(expert_notes) or None,
        )
        if units:
            turn["expert_units"] = units
        if not codes:
            turn["expert_note"] = turn["expert_note"] or "Kolom kode kosong di PDF (tidak dikode)."
        override = OVERRIDES.get((key, turn_no))
        if override:
            turn.update(override)
            turn["override_applied"] = True
        turns.append(turn)

    return {
        "fixture_id": f"casaa_{key}",
        "title": meta["title"],
        "source": "CASAA, MITI 4 Coding Training",
        "source_file": meta["pdf"],
        "language": "en",
        "duration_known": False,
        "duration_seconds": None,
        "change_target": meta["change_target"],
        "change_target_assumed": True,
        "change_target_note": ASSUMED_TARGET_NOTE,
        "expected_globals": parse_globals(tail),
        "parse_warnings": warnings,
        "turns": turns,
    }


def print_summary(fx: dict[str, Any], limit: int) -> None:
    print(f"{fx['fixture_id']}: {len(fx['turns'])} ujaran, target={fx['change_target']!r} (asumsi)")
    print("skor global ahli:", fx["expected_globals"])
    for w in fx["parse_warnings"]:
        print("  PERINGATAN:", w)
    for t in fx["turns"][:limit]:
        who = "P" if t["speaker"] == "counselor" else "C"
        print(f"\n#{t['turn_no']:>3} {who}: {t['content'][:110]}")
        if who == "P":
            flags = [k for k in ("same_as_previous_volley", "not_coded") if t[k]]
            print(f"      kode={t['expected_codes']} alt={t['acceptable_alternatives']} {flags or ''}"
                  f" bukti_global={[g['marker'] for g in t['global_evidence_notes']]}")
            if t["expert_note"]:
                print(f"      catatan ahli: {t['expert_note']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", choices=sorted(TRANSCRIPTS), action="append")
    parser.add_argument("--show", type=int, default=10, help="jumlah ujaran yang dicetak")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key in args.only or sorted(TRANSCRIPTS):
        fx = build_transcript(key)
        out = OUT_DIR / f"{fx['fixture_id']}.json"
        out.write_text(json.dumps(fx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print_summary(fx, args.show)
        print(f"-> {out.relative_to(REPO_DIR)}\n")


if __name__ == "__main__":
    main()
