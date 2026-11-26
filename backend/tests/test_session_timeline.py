"""Garis waktu sesi: lanjut setelah muat ulang, durasi aktif, giliran ketikan, dan validasi server."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api.sessions import end_active_session, send_counselor_turn
from repositories.sessions import _LATEST_EVALUATION, active_duration_seconds, end_session, list_student_sessions
from repositories.turns import get_session_turns, get_spoken_counselor_turns, save_turn
from schemas.session import CreateTurnRequest, EndSessionRequest, TurnResponse
from services.evaluation.miti_evaluator import agents_to_run
from services.simulation.orchestrator import process_turn
from tests.base import BaseTestCase

DAY_MS = 24 * 3600 * 1000


def spoken(start, end, **kw) -> CreateTurnRequest:
    return CreateTurnRequest(content="Halo", start_ms=start, end_ms=end, words=[], **kw)


class SqliteConn:
    """Menjalankan SQL repository di SQLite; `$1` dipetakan ke parameter bernama '1'."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def _run(self, sql, args):
        sql = sql.replace("::jsonb", "").replace("::speaker", "")
        cursor = self.db.execute(sql, {str(i): v for i, v in enumerate(args, 1)})
        names = [c[0] for c in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    async def fetch(self, sql, *args):
        return self._run(sql, args)

    async def fetchval(self, sql, *args):
        return next(iter(self._run(sql, args)[0].values()))


class TestTurnTimingSchema(BaseTestCase):
    def test_typed_turn_has_no_speech_duration(self):
        req = CreateTurnRequest(content="Diketik", start_ms=5000, end_ms=6000)  # +1 detik karangan dibuang
        self.assertEqual((req.start_ms, req.end_ms, req.sent_ms, req.words), (5000, 5000, 5000, None))

    def test_spoken_turn_keeps_duration_even_without_word_timings(self):
        req = spoken(5000, 8000, sent_ms=15000)
        self.assertEqual((req.start_ms, req.end_ms, req.sent_ms, req.words), (5000, 8000, 15000, []))

    def test_sent_ms_never_before_end(self):
        self.assertEqual(spoken(5000, 8000, sent_ms=100).sent_ms, 8000)

    def test_spoken_end_before_start_rejected(self):
        with self.assertRaises(ValueError):
            spoken(8000, 5000)

    def test_values_outside_integer_column_rejected(self):
        with self.assertRaises(ValueError):
            CreateTurnRequest(content="x", start_ms=2**31)


class TestServerValidatesTimeline(BaseTestCase):
    """Setelah muat ulang: giliran baru tidak boleh mundur dari giliran tersimpan."""

    def send(self, payload, end_ms=240_000, wall_ms=DAY_MS):
        session = self.get_sample_session(session_id=300, student_id=10)
        with patch("api.sessions.get_session_by_id", AsyncMock(return_value=session)), \
             patch("api.sessions.get_timeline", AsyncMock(return_value={"end_ms": end_ms, "wall_ms": wall_ms})), \
             patch("api.sessions.process_turn", new_callable=AsyncMock) as process, \
             patch("api.sessions.acquire_turn_lock", new_callable=AsyncMock) as lock:
            try:
                self.run_async(send_counselor_turn(
                    300, payload, self.get_sample_user(user_id=10, role="student"), self.create_mock_connection()
                ))
                return process, None
            except HTTPException as exc:
                process.assert_not_awaited()
                lock.return_value.release.assert_awaited_once()  # lock tidak tertinggal
                return process, exc.status_code

    def test_clock_restarted_from_zero_is_rejected(self):
        self.assertEqual(self.send(spoken(2_000, 4_000))[1], 409)

    def test_overlap_by_one_ms_is_rejected(self):
        self.assertEqual(self.send(CreateTurnRequest(content="x", start_ms=239_999))[1], 409)

    def test_resume_from_stored_end_is_accepted(self):
        process, code = self.send(spoken(240_000, 243_000, sent_ms=250_000))
        self.assertIsNone(code)
        self.assertEqual(process.await_args.kwargs["start_ms"], 240_000)
        self.assertEqual(process.await_args.kwargs["sent_ms"], 250_000)
        self.assertEqual(process.await_args.kwargs["word_timestamps"], [])

    def test_timeline_longer_than_real_time_is_rejected(self):
        self.assertEqual(self.send(CreateTurnRequest(content="x", start_ms=700_000), wall_ms=300_000)[1], 422)


class TestClientTurnOnTimeline(BaseTestCase):
    @patch("services.simulation.orchestrator.save_client_state", new_callable=AsyncMock, return_value=9)
    @patch("services.simulation.orchestrator.save_turn", new_callable=AsyncMock, side_effect=[1, 2])
    @patch("services.simulation.orchestrator.get_next_turn_no", new_callable=AsyncMock, return_value=1)
    @patch("services.simulation.orchestrator.get_session_turns", new_callable=AsyncMock, return_value=[])
    @patch("services.simulation.orchestrator.get_latest_topic_notes", new_callable=AsyncMock, return_value=[])
    @patch("services.simulation.orchestrator.get_latest_client_state", new_callable=AsyncMock)
    @patch("services.simulation.orchestrator.get_settings")
    def test_reply_is_placed_after_send_plus_processing(self, settings, state, _notes, _turns, _next, save, _save_state):
        settings.return_value.GREETING_SHORTCUT_ENABLED = True
        settings.return_value.DEBUG_INCLUDE_INTERNAL = False
        session = self.get_sample_session()
        state.return_value = session["scenario_snapshot"]["initial_state"]
        response = self.run_async(process_turn(
            self.create_mock_connection(), session, "Halo, selamat pagi", start_ms=10_000, end_ms=12_000,
            sent_ms=20_000, lock_wait_ms=500,
        ))
        self.assertIsInstance(response, TurnResponse)
        counselor, client = (c.kwargs for c in save.await_args_list)
        self.assertEqual((counselor["start_ms"], counselor["end_ms"]), (10_000, 12_000))
        self.assertEqual(client["start_ms"], client["end_ms"])
        self.assertGreaterEqual(client["start_ms"], 20_500)
        self.assertLess(client["start_ms"], 30_000)


class TestTypedTurnsInStorage(BaseTestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute(
            "CREATE TABLE turns (id INTEGER PRIMARY KEY, session_id INTEGER, turn_no INTEGER, speaker TEXT, "
            "content TEXT, start_ms INTEGER, end_ms INTEGER, word_timestamps TEXT, created_at TEXT)"
        )
        self.conn = SqliteConn(db)
        words = [{"word": "Halo", "start_ms": 0, "end_ms": 300}]
        for turn_no, speaker, start, end, stamps in [
            (1, "counselor", 0, 900, words),
            (2, "client", 2000, 2000, None),
            (3, "counselor", 5000, 5000, None),  # diketik
            (4, "client", 7000, 7000, None),
            (5, "counselor", 9000, 9800, []),  # diucapkan, STT tanpa waktu per kata
        ]:
            self.run_async(save_turn(self.conn, 1, turn_no, speaker, "isi", start, end, stamps))

    def test_typed_turns_excluded_from_vocal_data(self):
        rows = self.run_async(get_spoken_counselor_turns(self.conn, 1))
        self.assertEqual([r["turn_no"] for r in rows], [1, 5])
        self.assertEqual(json.loads(rows[1]["word_timestamps"]), [])

    def test_input_mode_marks_typed_and_spoken(self):
        rows = self.run_async(get_session_turns(self.conn, 1))
        self.assertEqual([r["input_mode"] for r in rows], ["voice", None, "text", None, "voice"])
        self.assertNotIn("word_timestamps", rows[0])


class TestActiveDuration(BaseTestCase):
    """Durasi = titik akhir garis waktu aktif, bukan ended_at - started_at."""

    def end(self, end_ms, wall_ms, ended_ms=0) -> int:
        conn = self.create_mock_connection()
        conn.fetchrow.side_effect = [{"end_ms": end_ms, "wall_ms": wall_ms}, {"scenario_snapshot": {}}]
        self.run_async(end_session(conn, 7, ended_ms))
        update_sql, session_id, duration = conn.fetchrow.await_args.args
        self.assertIn("duration_seconds = $2", update_sql)
        self.assertEqual(session_id, 7)
        return duration

    def test_abandoned_and_ended_next_day_counts_only_active_timeline(self):
        self.assertEqual(self.end(240_000, 20 * 3600 * 1000), 240)

    def test_resumed_next_day_adds_only_time_on_the_page(self):
        self.assertEqual(self.end(240_000, DAY_MS, ended_ms=270_000), 270)

    def test_stale_or_missing_end_position_never_shortens(self):
        self.assertEqual(active_duration_seconds(240_000, 3_000, DAY_MS), 240)
        self.assertEqual(active_duration_seconds(0, 0, DAY_MS), 0)

    def test_end_position_capped_by_real_time(self):
        self.assertEqual(active_duration_seconds(1_000, 10**9, 90_000), 90)

    def test_evaluation_limits_follow_the_new_duration(self):
        day = DAY_MS
        self.assertEqual(agents_to_run(self.end(300_999, day))[0], ["behavior_coding"])  # <= 5 menit
        agents, notes = agents_to_run(self.end(599_000, day))
        self.assertIn("global_scoring", agents)
        self.assertTrue(any("< 10 menit" in n for n in notes))
        self.assertEqual(agents_to_run(self.end(600_000, day))[1], [])

    def test_endpoint_passes_end_position(self):
        session = self.get_sample_session(session_id=301, student_id=10)
        done = {"id": 301, "status": "completed", "duration_seconds": 270, "ended_at": "2026-11-26T00:00:00Z"}
        user = self.get_sample_user(user_id=10, role="student")
        for payload, expected in [(EndSessionRequest(ended_ms=270_000), 270_000), (None, 0)]:
            with patch("api.sessions.get_session_by_id", AsyncMock(return_value=session)), \
                 patch("api.sessions.acquire_turn_lock", new_callable=AsyncMock), \
                 patch("api.sessions.end_session", AsyncMock(return_value=done)) as repo:
                self.run_async(end_active_session(301, payload, user, self.create_mock_connection()))
            self.assertEqual(repo.await_args.args[2], expected)

    def test_total_duration_sums_active_durations(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript(
            "CREATE TABLE sessions (id INTEGER, student_id INTEGER, status TEXT, duration_seconds INTEGER, deleted_at TEXT);"
            "CREATE TABLE evaluations (session_id INTEGER, status TEXT);"
        )
        for session_id, end_ms in [(1, 240_000), (2, 660_000)]:
            db.execute(
                "INSERT INTO sessions VALUES (?, 10, 'completed', ?, NULL)",
                (session_id, self.end(end_ms, DAY_MS)),
            )
        conn = self.create_mock_connection()
        conn.fetch.return_value = []
        conn.fetchrow.return_value = {}
        self.run_async(list_student_sessions(conn, 10))
        sql = conn.fetchrow.await_args.args[0].replace(_LATEST_EVALUATION, "LEFT JOIN evaluations ev ON ev.session_id = s.id")
        cursor = db.execute(sql, {"1": 10})
        row = dict(zip([c[0] for c in cursor.description], cursor.fetchone()))
        self.assertEqual(row["total_duration_seconds"], 900)
