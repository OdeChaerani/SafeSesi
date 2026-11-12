"""Pengukuran durasi per tahap satu giliran simulasi (log terstruktur, satu baris JSON per giliran)."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

timing_logger = logging.getLogger("safesesi.timing")


class TurnTimings:
    """Mengumpulkan durasi tahap (ms) satu giliran.

    Tahap: load, role_a, role_b, save, role_c. response_ms = waktu sampai respons
    siap dikirim ke mahasiswa; total_ms = sampai seluruh pekerjaan giliran selesai.
    """

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.stages: dict[str, float] = {}
        self.response_ms: float | None = None

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
            **extra,
        }
        timing_logger.info(json.dumps(record, ensure_ascii=False))
        return record
