from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

import asyncpg

from services.simulation.turn_lock import DbTurnLock, TurnLockTimeout


def make_pool():
    tx = MagicMock()
    tx.start = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    conn = MagicMock()
    conn.transaction = MagicMock(return_value=tx)
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = AsyncMock(return_value=conn)
    pool.release = AsyncMock()
    return pool, conn, tx


class TestDbTurnLock(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_takes_xact_advisory_lock_inside_transaction(self):
        pool, conn, tx = make_pool()
        lock = await DbTurnLock(pool, 42).acquire(timeout_s=2.5)

        tx.start.assert_awaited_once()
        sqls = [c.args[0] for c in conn.execute.await_args_list]
        self.assertEqual(sqls[0], "SET LOCAL lock_timeout = '2500ms'")
        self.assertIn("pg_advisory_xact_lock", sqls[1])
        self.assertEqual(conn.execute.await_args_list[1].args[1], 42)
        self.assertIs(lock.conn, conn)

    async def test_release_commits_once_and_returns_connection(self):
        pool, conn, tx = make_pool()
        lock = await DbTurnLock(pool, 1).acquire(timeout_s=1)
        await lock.release(commit=True)
        await lock.release(commit=True)  # idempoten

        tx.commit.assert_awaited_once()
        tx.rollback.assert_not_awaited()
        pool.release.assert_awaited_once_with(conn)

    async def test_release_rollback(self):
        pool, conn, tx = make_pool()
        lock = await DbTurnLock(pool, 1).acquire(timeout_s=1)
        await lock.release(commit=False)
        tx.rollback.assert_awaited_once()
        pool.release.assert_awaited_once_with(conn)

    async def test_lock_timeout_raises_and_releases_connection(self):
        pool, conn, tx = make_pool()
        conn.execute.side_effect = [None, asyncpg.exceptions.LockNotAvailableError("lock timeout")]

        with self.assertRaises(TurnLockTimeout):
            await DbTurnLock(pool, 1).acquire(timeout_s=1)
        tx.rollback.assert_awaited_once()
        pool.release.assert_awaited_once_with(conn)
