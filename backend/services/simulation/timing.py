"""Pengukuran durasi per tahap satu giliran simulasi (satu baris log per giliran; data lengkap di atribut record `timing`)."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

timing_logger = logging.getLogger("safesesi.timing")


class TurnTimings:
    """Mengumpulkan durasi tahap (ms) satu giliran.

    Tahap: load, role_a (combined) atau state_decision + state_detail (split), role_b, save,
    role_c. response_ms = waktu sampai respons siap dikirim ke mahasiswa; total_ms = sampai
    seluruh pekerjaan giliran selesai. tokens = token input/output Gemini per peran.
    """

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.stages: dict[str, float] = {}
        self.response_ms: float | None = None
        self.tokens: dict[str, dict[str, int]] = {}

    @staticmethod
    def _ms(seconds: float) -> float:
        return round(seconds * 1000, 1)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = self._ms(time.perf_counter() - t0)

    def mark_response_ready(self) -> None:
        self.response_ms = self._ms(time.perf_counter() - self._start)

    def emit(self, session_id: int, turn_no: int | None, **extra: Any) -> dict[str, Any]:
        total_ms = self._ms(time.perf_counter() - self._start)
        record: dict[str, Any] = {
            "event": "turn_timing",
            "session_id": session_id,
            "turn_no": turn_no,
            **{f"{name}_ms": ms for name, ms in self.stages.items()},
            "response_ms": self.response_ms if self.response_ms is not None else total_ms,
            "total_ms": total_ms,
            "tokens": self.tokens,
            **extra,
        }
        # Pesan untuk dibaca manusia; data lengkap tetap tersedia di atribut record `timing`.
        timing_logger.info(format_timing(record), extra={"timing": record})
        return record


_STAGE_LABELS = [
    ("role_a", "A"),
    ("state_decision", "A-decision"),
    ("role_b", "B"),
    ("state_detail", "A-detail"),
    ("role_c", "C"),
    ("load", "load"),
    ("save", "save"),
    ("lock_wait", "lock"),
]


def format_timing(record: dict[str, Any]) -> str:
    """Contoh: giliran #2 sesi 24 [combined] respons 9.0s, total 10.0s | A 6.6s, B 1.5s, C 0.7s, ...
    | token in/out A 1560/197, B 2357/6 | notes ok"""
    sec = lambda ms: f"{ms / 1000:.1f}s"  # noqa: E731
    stages = ", ".join(f"{label} {sec(record[f'{key}_ms'])}" for key, label in _STAGE_LABELS if f"{key}_ms" in record)
    tokens = ", ".join(f"{role} {t['input']}/{t['output']}" for role, t in (record.get("tokens") or {}).items())
    statuses = ", ".join(
        f"{label} {record[key]}" for key, label in (("notes_status", "notes"), ("detail_status", "detail")) if key in record
    )
    parts = [
        f"giliran #{record.get('turn_no')} sesi {record.get('session_id')} [{record.get('state_update_mode', record.get('path'))}]"
        f" respons {sec(record['response_ms'])}, total {sec(record['total_ms'])}",
        stages,
    ]
    if tokens:
        parts.append(f"token in/out {tokens}")
    if statuses:
        parts.append(statuses)
    return " | ".join(parts)
