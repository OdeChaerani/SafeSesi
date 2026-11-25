from __future__ import annotations

import asyncio
import itertools
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from api.sessions import end_active_session, send_counselor_turn
from core.errors import LLMServiceError
from fastapi import HTTPException
from schemas.client_state import ClientState
from schemas.session import CreateTurnRequest
from services.simulation.notes_updater import TopicNoteUpdate
from tests.base import BaseTestCase, MockTx

_session_ids = itertools.count(9000)


class FakeDbLocks:
    """Meniru advisory lock per sesi di database: satu lock bersama untuk semua worker.

    Berbeda dengan asyncio.Lock per proses di api/sessions.py, lock ini tetap dipegang
    oleh tugas Peran C setelah request selesai, sama seperti DbTurnLock.
    """

    def __init__(self, events: list[str]) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self.events = events
        self.releases: list[bool] = []

    async def acquire(self, session_id: int) -> "FakeTurnLock":
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        await lock.acquire()
        self.events.append("lock_acquired")
        return FakeTurnLock(self, lock)


class FakeTurnLock:
    def __init__(self, owner: FakeDbLocks, lock: asyncio.Lock) -> None:
        self.conn = AsyncMock()
        self.conn.transaction = MagicMock(return_value=MockTx())
        self._owner = owner
        self._lock = lock
        self._released = False

    async def release(self, *, commit: bool = True) -> None:
        if self._released:
            return
        self._released = True
        self._owner.releases.append(commit)
        self._owner.events.append("lock_released")
        self._lock.release()


async def settle(rounds: int = 20) -> None:
    """Memberi kesempatan semua tugas yang siap untuk berjalan."""
    for _ in range(rounds):
        await asyncio.sleep(0)


class TestBackgroundNotesOrdering(unittest.IsolatedAsyncioTestCase):
    """Peran C di background: urutan giliran, kegagalan, dan end session."""

    def setUp(self) -> None:
        self.session_id = next(_session_ids)
        base = BaseTestCase()
        self.user = base.get_sample_user(user_id=10)
        self.session = base.get_sample_session(session_id=self.session_id, student_id=10)
        self.conn = base.create_mock_connection()

        self.events: list[str] = []
        self.locks = FakeDbLocks(self.events)
        self.c_gate = asyncio.Event()
        self.c_should_fail = False
        turn_numbers = itertools.count(1, 2)

        settings = MagicMock()
        settings.NOTES_UPDATE_MODE = "background"
        settings.GREETING_SHORTCUT_ENABLED = False
        settings.DEBUG_INCLUDE_INTERNAL = False
        settings.NOTES_TIMEOUT_S = 5.0

        async def fake_notes_llm(**kwargs: Any) -> list[TopicNoteUpdate]:
            self.events.append("c_started")
            await self.c_gate.wait()
            if self.c_should_fail:
                self.events.append("c_failed")
                raise LLMServiceError("Gemini tidak tersedia")
            self.events.append("c_done")
            return [TopicNoteUpdate(topic_name="Permasalahan utama", description="Catatan baru")]

        async def fake_load_notes(conn: Any, session_id: int) -> list[dict[str, Any]]:
            self.events.append("load_notes")
            return [{"session_topic_id": 1, "topic_name": "Permasalahan utama", "description": ""}]

        async def fake_role_b(**kwargs: Any) -> str:
            return "Iya, begitu Kak."

        async def fake_end_session(conn: Any, session_id: int) -> dict[str, Any]:
            self.events.append("end_session")
            return {"id": session_id, "status": "completed", "duration_seconds": 60, "ended_at": "2026-11-12T10:00:00Z"}

        patches = [
            patch("api.sessions.acquire_turn_lock", side_effect=self.locks.acquire),
            patch("api.sessions.get_session_by_id", AsyncMock(return_value=self.session)),
            patch("api.sessions.end_session", side_effect=fake_end_session),
            patch("services.simulation.orchestrator.get_settings", return_value=settings),
            patch("services.simulation.orchestrator.get_latest_client_state", AsyncMock(return_value=None)),
            patch("services.simulation.orchestrator.get_latest_topic_notes", side_effect=fake_load_notes),
            patch("services.simulation.orchestrator.get_session_turns", AsyncMock(return_value=[])),
            patch("services.simulation.orchestrator.get_next_turn_no", side_effect=lambda *a, **k: next(turn_numbers)),
            patch("services.simulation.orchestrator.save_turn", AsyncMock(return_value=1)),
            patch("services.simulation.orchestrator.save_client_state", AsyncMock()),
            patch("services.simulation.orchestrator.save_topic_note", AsyncMock(side_effect=lambda *a, **k: self.events.append("note_saved"))),
            patch(
                "services.simulation.orchestrator.update_client_state_llm",
                AsyncMock(return_value=ClientState(emotion_type="Cemas", disclosure_level="medium", ambivalence_lean="both")),
            ),
            patch("services.simulation.orchestrator.generate_client_response_llm", side_effect=fake_role_b),
            patch("services.simulation.orchestrator.update_topic_notes_llm", side_effect=fake_notes_llm),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def turn(self, text: str = "Boleh ceritakan lebih lanjut?"):
        return send_counselor_turn(
            session_id=self.session_id,
            payload=CreateTurnRequest(content=text),
            user=self.user,
            conn=self.conn,
        )

    async def test_response_returned_before_role_c_finishes(self):
        res = await asyncio.wait_for(self.turn(), timeout=2)
        await settle()

        self.assertEqual(res.content, "Iya, begitu Kak.")
        self.assertIn("c_started", self.events)
        self.assertNotIn("c_done", self.events)
        self.assertNotIn("lock_released", self.events)  # lock dipegang Peran C

        self.c_gate.set()
        await settle()
        self.assertEqual(self.events[-3:], ["c_done", "note_saved", "lock_released"])
        self.assertEqual(self.locks.releases, [True])

    async def test_next_turn_waits_for_previous_role_c_before_loading_notes(self):
        await self.turn("Giliran pertama")
        second = asyncio.create_task(self.turn("Giliran kedua"))
        await settle()

        self.assertEqual(self.events.count("load_notes"), 1)  # giliran kedua masih menunggu lock
        self.assertFalse(second.done())

        self.c_gate.set()
        res = await asyncio.wait_for(second, timeout=2)
        await settle()

        self.assertEqual(res.turn_no, 4)
        first_c_done = self.events.index("c_done")
        second_load = [i for i, e in enumerate(self.events) if e == "load_notes"][1]
        self.assertLess(first_c_done, second_load)
        self.assertLess(self.events.index("note_saved"), second_load)
        self.assertLess(self.events.index("lock_released"), second_load)

    async def test_role_c_failure_does_not_fail_response_and_next_turn_runs(self):
        self.c_should_fail = True
        self.c_gate.set()

        with self.assertLogs("safesesi.simulation.orchestrator", level="ERROR") as logs:
            res = await asyncio.wait_for(self.turn(), timeout=2)
            await settle()

        self.assertEqual(res.content, "Iya, begitu Kak.")
        self.assertIn("c_failed", self.events)
        self.assertNotIn("note_saved", self.events)
        self.assertEqual(self.locks.releases, [False])  # rollback, tetapi lock tetap dilepas
        self.assertTrue(any("Peran C background gagal" in line for line in logs.output))

        self.c_should_fail = False
        res2 = await asyncio.wait_for(self.turn("Giliran berikutnya"), timeout=2)
        await settle()
        self.assertEqual(res2.turn_no, 4)
        self.assertEqual(self.events.count("load_notes"), 2)

    async def test_end_session_waits_for_last_role_c(self):
        await self.turn()
        end_task = asyncio.create_task(
            end_active_session(session_id=self.session_id, user=self.user, conn=self.conn)
        )
        await settle()

        self.assertNotIn("end_session", self.events)
        self.assertFalse(end_task.done())

        self.c_gate.set()
        res = await asyncio.wait_for(end_task, timeout=2)

        self.assertEqual(res["status"], "completed")
        self.assertLess(self.events.index("note_saved"), self.events.index("end_session"))
        self.assertEqual(self.events.count("lock_acquired"), self.events.count("lock_released"))

    async def test_lock_released_when_role_a_fails(self):
        with patch(
            "services.simulation.orchestrator.update_client_state_llm",
            AsyncMock(side_effect=LLMServiceError("Gemini tidak tersedia")),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await asyncio.wait_for(self.turn(), timeout=2)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(self.locks.releases, [False])
        self.assertNotIn("c_started", self.events)

        self.c_gate.set()
        res = await asyncio.wait_for(self.turn("Coba lagi"), timeout=2)
        self.assertEqual(res.content, "Iya, begitu Kak.")

    async def test_inline_mode_without_lock_connection(self):
        """Tanpa koneksi lock (NullTurnLock), Peran C dijalankan inline sebelum respons."""
        from services.simulation.turn_lock import NullTurnLock

        self.c_gate.set()
        with patch("api.sessions.acquire_turn_lock", AsyncMock(return_value=NullTurnLock())):
            res = await asyncio.wait_for(self.turn(), timeout=2)
        self.assertEqual(res.content, "Iya, begitu Kak.")
        self.assertEqual(self.events[-2:], ["c_done", "note_saved"])  # selesai sebelum respons

    async def test_turn_rejected_after_end_releases_lock(self):
        completed = {**self.session, "status": "completed"}
        with patch("api.sessions.get_session_by_id", AsyncMock(side_effect=[self.session, completed])):
            with self.assertRaises(HTTPException) as ctx:
                await self.turn()
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.locks.releases, [False])
