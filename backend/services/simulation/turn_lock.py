"""Lock giliran per sesi yang aman lintas worker, plus registri tugas background Peran C.

Mekanisme: advisory lock PostgreSQL tingkat transaksi (pg_advisory_xact_lock) pada
koneksi khusus yang transaksinya dibiarkan terbuka sejak awal giliran hingga Peran C
selesai. Karena lock berada di database, semua worker/proses uvicorn melihat lock yang
sama. Lock tingkat transaksi dipilih (bukan pg_advisory_lock tingkat sesi) agar tetap
benar di belakang pooler mode transaksi (Supavisor/PgBouncer port 6543): koneksi
backend terikat ke klien selama transaksi berjalan. Jika proses mati, koneksi putus dan
PostgreSQL melepas lock secara otomatis.

Urutan yang dijamin:
- Giliran N+1 baru memuat catatan topik setelah Peran C giliran N selesai (commit/rollback).
- End session menunggu Peran C terakhir selesai.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine
import asyncpg

logger = logging.getLogger("safesesi.simulation.turn_lock")

# Kunci 64-bit diturunkan dari nama agar tidak bertabrakan dengan pengguna advisory lock lain.
_LOCK_SQL = (
    "SELECT pg_advisory_xact_lock("
    "hashtextextended('safesesi:session-turn:' || ($1::bigint)::text, 0))"
)


class TurnLockTimeout(Exception):
    """Lock giliran tidak diperoleh dalam batas waktu (giliran/Peran C sebelumnya belum selesai)."""


class NullTurnLock:
    """Lock no-op saat pool database tidak dikonfigurasi (unit test / tanpa DB)."""

    conn: asyncpg.Connection | None = None

    async def release(self, *, commit: bool = True) -> None:
        return None


class DbTurnLock:
    """Advisory lock per sesi yang dipegang selama transaksi pada koneksi khusus."""

    def __init__(self, pool: asyncpg.Pool, session_id: int) -> None:
        self._pool = pool
        self._session_id = session_id
        self.conn: asyncpg.Connection | None = None
        self._tx: Any = None
        self._released = False

    async def acquire(self, timeout_s: float) -> "DbTurnLock":
        self.conn = await self._pool.acquire()
        try:
            self._tx = self.conn.transaction()
            await self._tx.start()
            # lock_timeout berlaku untuk advisory lock; nilai int dari config, bukan input pengguna
            await self.conn.execute(f"SET LOCAL lock_timeout = '{int(timeout_s * 1000)}ms'")
            await self.conn.execute(_LOCK_SQL, self._session_id)
        except asyncpg.exceptions.LockNotAvailableError as exc:
            await self.release(commit=False)
            raise TurnLockTimeout(str(exc)) from exc
        except BaseException:
            await self.release(commit=False)
            raise
        return self

    async def release(self, *, commit: bool = True) -> None:
        """Commit (atau rollback) transaksi lock lalu kembalikan koneksi ke pool. Idempoten."""
        if self._released or self.conn is None:
            return
        self._released = True
        try:
            if self._tx is not None:
                if commit:
                    await self._tx.commit()
                else:
                    await self._tx.rollback()
        finally:
            await self._pool.release(self.conn)


_pool: asyncpg.Pool | None = None
_lock_timeout_s: float = 30.0


def configure_turn_lock(pool: asyncpg.Pool | None, timeout_s: float = 30.0) -> None:
    """Dipanggil di lifespan aplikasi setelah pool dibuat."""
    global _pool, _lock_timeout_s
    _pool = pool
    _lock_timeout_s = timeout_s


async def acquire_turn_lock(session_id: int) -> DbTurnLock | NullTurnLock:
    """Menunggu hingga giliran/Peran C sebelumnya pada sesi ini selesai, lalu memegang lock."""
    if _pool is None:
        return NullTurnLock()
    return await DbTurnLock(_pool, session_id).acquire(_lock_timeout_s)


# ---------------------------------------------------------------------------
# Registri tugas background (agar tidak hilang oleh GC dan bisa ditunggu saat shutdown)
# ---------------------------------------------------------------------------

_background_tasks: set[asyncio.Task[Any]] = set()


def spawn_background(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
    task = asyncio.get_running_loop().create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def drain_background_tasks(timeout_s: float = 30.0) -> None:
    """Menunggu tugas background yang tersisa (dipanggil saat shutdown, sebelum pool ditutup)."""
    pending = list(_background_tasks)
    if not pending:
        return
    logger.info("Menunggu %d tugas Peran C background selesai...", len(pending))
    _, still_running = await asyncio.wait(pending, timeout=timeout_s)
    for task in still_running:
        task.cancel()
