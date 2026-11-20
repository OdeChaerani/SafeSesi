"""Simulasi sungguhan beberapa giliran per mode Peran A untuk mengukur durasi per tahap.

MEMANGGIL GEMINI DAN MENULIS KE DATABASE (DATABASE_URL di backend/.env): tiap mode membuat satu
sesi baru (skenario Nadia, user dev), mengirim beberapa giliran, lalu mengakhiri sesi. Aplikasi
dijalankan in-process (httpx ASGITransport + lifespan), jadi lock giliran, Peran C, dan State
Detail Agent di background berjalan seperti di server. Log safesesi.timing ditangkap lalu
dirangkum. session_id yang dibuat dicetak; skrip tidak menghapus apa pun.

Pemakaian (dari root repo):
  backend/venv/Scripts/python backend/evals/scripts/sim_timing.py --modes combined split --turns 6 --pause-s 30
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

# Ucapan konselor generik buatan baru (bukan dari dokumen Ilustrasi).
UTTERANCES = [
    "Terima kasih sudah datang. Apa yang ingin kamu bicarakan hari ini?",
    "Kedengarannya beberapa minggu ini cukup melelahkan buatmu.",
    "Bagian mana yang paling terasa berat?",
    "Jadi di satu sisi kamu ingin tetap terlibat, di sisi lain kamu merasa kewalahan.",
    "Apa yang membuatmu ragu untuk mengurangi sebagian tanggung jawab itu?",
    "Kalau keadaannya berubah, apa yang paling kamu harapkan?",
]

STAGES = ["lock_wait", "load", "role_a", "state_decision", "role_b", "save", "role_c", "state_detail"]


class TimingCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        timing = getattr(record, "timing", None)
        if timing is not None:
            self.records.append(timing)


async def run_mode(mode: str, args: argparse.Namespace) -> int:
    import httpx

    import main
    from core.config import get_settings

    settings = get_settings()
    settings.STATE_UPDATE_MODE = mode
    settings.GREETING_SHORTCUT_ENABLED = False  # semua giliran melewati pipeline LLM

    async with main.app.router.lifespan_context(main.app):
        transport = httpx.ASGITransport(app=main.app)
        headers = {"X-Dev-User-Id": str(args.user_id)}
        async with httpx.AsyncClient(transport=transport, base_url="http://sim", headers=headers, timeout=120) as client:
            catalog = (await client.get("/scenarios/catalog")).raise_for_status().json()
            matches = [s for s in catalog["items"] if args.scenario.lower() in (s["client_name"] + " " + s["title"]).lower()]
            if not matches:
                raise SystemExit(f"Skenario '{args.scenario}' tidak ditemukan di katalog user {args.user_id}.")
            scenario = matches[0]
            if scenario.get("active_session_id"):
                raise SystemExit(
                    f"User {args.user_id} masih punya sesi aktif #{scenario['active_session_id']} untuk skenario ini; "
                    "skrip tidak mengakhirinya sendiri."
                )
            created = (await client.post("/sessions", json={"scenario_id": scenario["id"], "mode": "new"})).raise_for_status().json()
            session_id = created["id"]
            print(f"[{mode}] sesi #{session_id} dibuat (skenario #{scenario['id']} {scenario['title']})", flush=True)
            for i, text in enumerate(UTTERANCES[: args.turns], start=1):
                if i > 1:
                    await asyncio.sleep(args.pause_s)  # kuota RPM Gemini
                r = await client.post(f"/sessions/{session_id}/turns", json={"content": text})
                r.raise_for_status()
                print(f"[{mode}] giliran {i}: {r.json()['content'][:80]}", flush=True)
            await asyncio.sleep(args.pause_s)
            (await client.post(f"/sessions/{session_id}/end")).raise_for_status()
            print(f"[{mode}] sesi #{session_id} diakhiri", flush=True)
    return session_id


def summarize(mode: str, records: list[dict[str, Any]]) -> None:
    turns = [r for r in records if r.get("path") == "substantive"]
    print(f"\n=== {mode}: {len(turns)} giliran ===")
    print("turn | " + " | ".join(f"{s}_ms" for s in STAGES) + " | response_ms | total_ms | status | tokens")
    for r in turns:
        cells = [str(r.get(f"{s}_ms", "-")) for s in STAGES]
        status = ",".join(f"{k}={r[k]}" for k in ("notes_status", "detail_status") if k in r)
        print(f"{r['turn_no']} | " + " | ".join(cells) + f" | {r['response_ms']} | {r['total_ms']} | {status} | {json.dumps(r.get('tokens'))}")
    if turns:
        means = {s: statistics.mean(r[f"{s}_ms"]) for s in STAGES if all(f"{s}_ms" in r for r in turns)}
        print("rata-rata: " + ", ".join(f"{s}={v:.0f}" for s, v in means.items())
              + f", response={statistics.mean(r['response_ms'] for r in turns):.0f}, total={statistics.mean(r['total_ms'] for r in turns):.0f}")


async def main_async(args: argparse.Namespace) -> None:
    capture = TimingCapture()
    logging.getLogger("safesesi.timing").addHandler(capture)
    session_ids: dict[str, int] = {}
    per_mode: dict[str, list[dict[str, Any]]] = {}
    for mode in args.modes:
        start = len(capture.records)
        session_ids[mode] = await run_mode(mode, args)
        per_mode[mode] = [r for r in capture.records[start:] if r.get("session_id") == session_ids[mode]]
    for mode, records in per_mode.items():
        summarize(mode, records)
    print(f"\nsession_id yang dibuat: {session_ids}")
    if args.output:
        Path(args.output).write_text(json.dumps({"session_ids": session_ids, "records": per_mode}, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modes", nargs="+", choices=["combined", "split"], default=["combined", "split"])
    parser.add_argument("--turns", type=int, default=6)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--scenario", default="Nadia", help="potongan nama klien/judul skenario")
    parser.add_argument("--pause-s", type=float, default=30.0, help="jeda antargiliran (kuota RPM Gemini)")
    parser.add_argument("--output", help="simpan record timing ke file JSON")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
