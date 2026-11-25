"""Pembatasan percobaan (rate limiting) untuk endpoint auth: sliding window log di memori proses.

Satu instance server (target ~40 pengguna). Penyimpanan dibungkus RateLimitStore sehingga bisa diganti
(mis. tabel database) lewat set_store() tanpa mengubah endpoint. Kalau nanti berjalan di lebih dari
satu proses, store di memori ini TIDAK cukup karena hitungannya tidak dibagi antar proses.
"""
from __future__ import annotations

import ipaddress
import math
import time
from collections import OrderedDict, deque
from typing import Callable, Protocol

from fastapi import HTTPException, Request, status

from core.config import Settings

# Satu pesan untuk semua kasus agar tidak membocorkan apakah email terdaftar.
RATE_LIMITED_MESSAGE = "Terlalu banyak percobaan. Silakan coba lagi beberapa saat lagi."
_SWEEP_INTERVAL_S = 60.0
MAX_KEYS = 10000  # yang paling lama tidak disentuh dibuang lebih dulu

# (jumlah percobaan, jendela detik). Longgarkan di sini bila pengguna sah sering terkena batas.
RULES: dict[str, tuple[int, int]] = {
    "login_pair": (5, 900),  # percobaan GAGAL per IP + email
    "login_ip": (200, 900),  # semua percobaan login per IP; longgar karena satu IP kampus dipakai bersama 30-40 pengguna
    "activate": (100, 900),  # per IP; alasan sama dengan login_ip
    "change_password": (5, 900),  # percobaan GAGAL per pengguna + IP
    "refresh": (120, 60),  # per IP; dipanggil otomatis frontend (single-flight)
}


class RateLimitStore(Protocol):
    def acquire(self, key: str, limit: int, window_s: float) -> float | None:
        """Catat satu percobaan. None bila masih di bawah batas; bila sudah penuh, percobaan TIDAK
        dicatat dan hasilnya detik sampai slot berikutnya kosong."""

    def clear(self, key: str) -> None: ...


class _Entry:
    __slots__ = ("hits", "expires")

    def __init__(self) -> None:
        self.hits: deque[float] = deque()
        self.expires = 0.0


class InMemoryRateLimitStore:
    def __init__(self, max_keys: int = 10000, clock: Callable[[], float] = time.monotonic) -> None:
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._max_keys = max_keys
        self._clock = clock
        self._last_sweep = clock()

    def acquire(self, key: str, limit: int, window_s: float) -> float | None:
        now = self._clock()
        self._sweep(now)
        entry = self._entries.get(key)
        if entry is None:
            entry = self._entries[key] = _Entry()
        hits = entry.hits
        while hits and hits[0] <= now - window_s:
            hits.popleft()
        if len(hits) >= limit:
            return hits[0] + window_s - now
        hits.append(now)
        entry.expires = max(entry.expires, now + window_s)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_keys:
            self._entries.popitem(last=False)
        return None

    def clear(self, key: str) -> None:
        self._entries.pop(key, None)

    def _sweep(self, now: float) -> None:
        """Buang kunci yang semua percobaannya sudah di luar jendela, agar memori tidak membengkak."""
        if now - self._last_sweep < _SWEEP_INTERVAL_S:
            return
        self._last_sweep = now
        for key in [k for k, e in self._entries.items() if e.expires <= now]:
            del self._entries[key]


_store: RateLimitStore | None = None


def get_store(settings: Settings) -> RateLimitStore:
    global _store
    if _store is None:
        _store = InMemoryRateLimitStore(max_keys=MAX_KEYS)
    return _store


def set_store(store: RateLimitStore | None) -> None:
    """Mengganti penyimpanan (mis. ke database) atau mengosongkan (None) untuk tes."""
    global _store
    _store = store


def enforce(store: RateLimitStore, key: str, rule: str) -> None:
    """Catat percobaan menurut RULES[rule]; 429 + Retry-After bila batas terlewati."""
    retry_after = store.acquire(key, *RULES[rule])
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMITED_MESSAGE,
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


def client_ip(request: Request, settings: Settings) -> str:
    """IP klien. X-Forwarded-For hanya dipakai bila TRUST_PROXY_HEADERS; yang dibaca entri TERAKHIR
    (ditambahkan proxy tepercaya kita), bukan yang pertama (bisa dipalsukan klien)."""
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass  # header kosong/rusak: pakai alamat koneksi
    return request.client.host if request.client else "unknown"
