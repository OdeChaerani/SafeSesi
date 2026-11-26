"""Riwayat sesi mahasiswa dan transkrip: hanya data sendiri, aturan akses, dan tanpa Client State."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.deps import get_current_user, get_db
from api.sessions import get_session_transcript, list_my_sessions
from main import app
from repositories.sessions import _LATEST_EVALUATION, list_student_sessions
from schemas.student import SessionHistoryResponse, TranscriptResponse
from tests.base import BaseTestCase

STUDENT = 10
NOW = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
CLIENT_STATE_WORDS = ("emotion", "disclosure", "discord", "ambivalence", "hidden", "internal_state", "client_state")


def history_row(**kw: Any) -> dict[str, Any]:
    return {
        "id": 5, "scenario_id": 1, "class_id": None, "parent_session_id": None, "status": "completed",
        "started_at": NOW, "ended_at": NOW, "duration_seconds": 540,
        "scenario_title": "SS-NAD-01 Nadia Maharani", "client_name": "Nadia Maharani", "class_name": None,
        "evaluation_status": "none", "total_count": 1, **kw,
    }


COUNTS = {
    "total_sessions": 4, "completed_sessions": 3, "awaiting_evaluation": 2, "evaluation_failed": 1,
    "total_duration_seconds": 1500,
}


class TestHistoryQuery(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn = self.create_mock_connection()
        self.conn.fetch.return_value = [history_row()]
        self.conn.fetchrow.return_value = COUNTS

    def run_list(self, **kw: Any) -> dict[str, Any]:
        return self.run_async(list_student_sessions(self.conn, STUDENT, **kw))

    def fetch_call(self):
        return self.conn.fetch.call_args.args[0], self.conn.fetch.call_args.args[1:]

    def test_only_own_sessions(self):
        self.run_list()
        sql, args = self.fetch_call()
        self.assertIn("s.student_id = $1", sql)
        self.assertIn("s.deleted_at IS NULL", sql)
        self.assertEqual(args[0], STUDENT)
        self.assertEqual(self.conn.fetchrow.call_args.args[1], STUDENT)  # hitungan beranda juga hanya milik sendiri

    def test_filters_by_kind_and_scenario(self):
        self.run_list(kind="independent")
        self.assertIn("s.class_id IS NULL", self.fetch_call()[0])
        self.run_list(kind="class")
        self.assertIn("s.class_id IS NOT NULL", self.fetch_call()[0])
        self.run_list(kind="all", scenario_id=7, limit=20)
        sql, args = self.fetch_call()
        self.assertIn("s.scenario_id = $2", sql)
        self.assertNotIn("s.class_id IS", sql)
        self.assertEqual(args, (STUDENT, 7, 20))  # limit selalu parameter terakhir

    def test_reads_only_public_snapshot_fields(self):
        self.run_list()
        sql, _ = self.fetch_call()
        self.assertIn("#>> '{scenario,title}'", sql)
        self.assertIn("#>> '{persona,name}'", sql)
        for hidden in ("hidden_facts", "initial_state", "client_state", "personality", "'{case"):
            self.assertNotIn(hidden, sql)

    def test_result_shape_and_counts(self):
        self.conn.fetch.return_value = [
            history_row(id=6, class_id=3, class_name="Kelas Uji", evaluation_status="failed", total_count=2),
            history_row(id=5),
        ]
        res = self.run_list()
        body = SessionHistoryResponse.model_validate(res).model_dump(mode="json")
        self.assertEqual([i["kind"] for i in body["items"]], ["class", "independent"])
        self.assertEqual(body["items"][0]["class_name"], "Kelas Uji")
        self.assertEqual(body["items"][1]["evaluation_status"], "none")
        self.assertEqual((body["total"], body["awaiting_evaluation"], body["evaluation_failed"]), (2, 2, 1))

    def test_awaiting_and_failed_are_counted_separately(self):
        self.run_list()
        sql = self.conn.fetchrow.call_args.args[0]
        self.assertIn("s.status = 'completed' AND ev.status IS NULL", sql)  # belum pernah dievaluasi
        self.assertIn("s.status = 'completed' AND ev.status = 'failed'", sql)  # perlu dijalankan ulang

    def test_empty_history(self):
        self.conn.fetch.return_value = []
        self.conn.fetchrow.return_value = {k: 0 for k in COUNTS}
        res = self.run_list()
        self.assertEqual((res["items"], res["total"]), ([], 0))

    def test_endpoint_passes_only_the_logged_in_student(self):
        user = self.get_sample_user(user_id=STUDENT, role="student")
        with patch("api.sessions.list_student_sessions", AsyncMock(return_value={"items": []})) as repo:
            self.run_async(list_my_sessions(kind="class", scenario_id=2, limit=50, user=user, conn=self.conn))
        repo.assert_awaited_once_with(self.conn, STUDENT, kind="class", scenario_id=2, limit=50)


class TestTotalDuration(BaseTestCase):
    """Query hitungan asli dijalankan di SQLite; hanya join LATERAL (khusus PostgreSQL) yang diganti."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript(
            """
            CREATE TABLE sessions (id INTEGER, student_id INTEGER, status TEXT, duration_seconds INTEGER, deleted_at TEXT);
            CREATE TABLE evaluations (session_id INTEGER, status TEXT);
            """
        )

    def _total(self) -> int:
        conn = self.create_mock_connection()
        conn.fetch.return_value = []
        conn.fetchrow.return_value = COUNTS
        self.run_async(list_student_sessions(conn, STUDENT))
        sql, student = conn.fetchrow.call_args.args
        self.assertIn(_LATEST_EVALUATION, sql)
        sql = sql.replace(_LATEST_EVALUATION, "LEFT JOIN evaluations ev ON ev.session_id = s.id")
        cursor = self.db.execute(sql, {"1": student})
        row = dict(zip([c[0] for c in cursor.description], cursor.fetchone()))
        return row["total_duration_seconds"]

    def _add(self, session_id, student=STUDENT, status="completed", seconds=100, deleted=None):
        self.db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", (session_id, student, status, seconds, deleted))

    def test_zero_without_sessions(self):
        self.assertEqual(self._total(), 0)

    def test_only_completed_sessions_counted(self):
        self._add(1, seconds=600)
        self._add(2, seconds=90)
        self._add(3, status="in_progress", seconds=5000)
        self._add(4, seconds=None)  # selesai tanpa durasi tidak membuat hasilnya kosong
        self.assertEqual(self._total(), 690)

    def test_deleted_and_other_students_sessions_ignored(self):
        self._add(1, seconds=60)
        self._add(2, seconds=700, deleted="2026-11-01")
        self._add(3, student=99, seconds=800)
        self.assertEqual(self._total(), 60)

    def test_response_schema_requires_the_field(self):
        body = {"items": [], "total": 0, **COUNTS}
        self.assertEqual(SessionHistoryResponse(**body).total_duration_seconds, 1500)
        body.pop("total_duration_seconds")
        with self.assertRaises(ValueError):
            SessionHistoryResponse(**body)


class TestTranscript(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn = self.create_mock_connection()
        self.session = {**self.get_sample_session(session_id=5, student_id=STUDENT), "class_id": None, "parent_session_id": None,
                        "status": "completed", "started_at": NOW, "ended_at": NOW, "duration_seconds": 540, "scenario_id": 1}
        # baris dari DB membawa kolom tambahan; transkrip hanya boleh meneruskan 3 field
        self.turns = [
            {"id": 1, "session_id": 5, "turn_no": 1, "speaker": "counselor", "content": "Halo", "start_ms": 0, "end_ms": 900,
             "created_at": NOW, "word_timestamps": [{"word": "Halo"}], "internal_state": {"emotion_type": "cemas"}},
            {"id": 2, "session_id": 5, "turn_no": 2, "speaker": "client", "content": "Pagi, Kak.", "start_ms": 1000, "end_ms": 2000,
             "created_at": NOW},
        ]

    def call(self, user: dict[str, Any], session: dict[str, Any] | None = None, manages: bool = False) -> dict[str, Any]:
        with patch("api.sessions.get_session_by_id", AsyncMock(return_value=session if session is not None else self.session)), \
             patch("api.sessions.get_session_turns", AsyncMock(return_value=self.turns)), \
             patch("api.sessions.get_class", AsyncMock(return_value={"id": 3, "name": "Kelas Uji"})), \
             patch("api.deps.lecturer_manages_session", AsyncMock(return_value=manages)):
            return self.run_async(get_session_transcript(session_id=5, user=user, conn=self.conn))

    def status_of(self, user: dict[str, Any], **kw: Any) -> int:
        with self.assertRaises(HTTPException) as ctx:
            self.call(user, **kw)
        return ctx.exception.status_code

    def test_owner_gets_speaker_and_content_only(self):
        res = self.call(self.get_sample_user(user_id=STUDENT))
        body = TranscriptResponse.model_validate(res).model_dump(mode="json")
        self.assertEqual(body["turns"], [
            {"turn_no": 1, "speaker": "counselor", "content": "Halo"},
            {"turn_no": 2, "speaker": "client", "content": "Pagi, Kak."},
        ])
        self.assertEqual(body["session"]["scenario"]["client_name"], "Nadia Maharani")

    def test_transcript_has_no_client_state_or_hidden_data(self):
        res = self.call(self.get_sample_user(user_id=STUDENT))
        dumped = json.dumps(TranscriptResponse.model_validate(res).model_dump(mode="json")).lower()
        for word in CLIENT_STATE_WORDS:
            self.assertNotIn(word, dumped)
        self.assertNotIn("word_timestamps", dumped)

    def test_class_session_shows_class_name(self):
        res = self.call(self.get_sample_user(user_id=STUDENT), session={**self.session, "class_id": 3})
        self.assertEqual((res["session"]["kind"], res["session"]["class_name"]), ("class", "Kelas Uji"))

    def test_other_student_forbidden(self):
        self.assertEqual(self.status_of(self.get_sample_user(user_id=99)), 403)

    def test_lecturer_of_the_class_may_read_class_session(self):
        lecturer = self.get_sample_user(user_id=2, role="lecturer")
        res = self.call(lecturer, session={**self.session, "class_id": 3}, manages=True)
        self.assertEqual(len(res["turns"]), 2)

    def test_lecturer_of_another_class_forbidden(self):
        lecturer = self.get_sample_user(user_id=2, role="lecturer")
        self.assertEqual(self.status_of(lecturer, session={**self.session, "class_id": 3}, manages=False), 403)

    def test_independent_session_never_visible_to_lecturer(self):
        lecturer = self.get_sample_user(user_id=2, role="lecturer")
        self.assertEqual(self.status_of(lecturer, manages=True), 403)  # manages=True pun tidak cukup tanpa class_id

    def test_admin_forbidden(self):
        admin = self.get_sample_user(user_id=1, role="admin")
        self.assertEqual(self.status_of(admin), 403)
        self.assertEqual(self.status_of(admin, session={**self.session, "class_id": 3}, manages=True), 403)

    def test_missing_session_404(self):
        with patch("api.sessions.get_session_by_id", AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as ctx:
                self.run_async(get_session_transcript(session_id=5, user=self.get_sample_user(user_id=STUDENT), conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 404)


class TestHistoryHttp(BaseTestCase):
    """Parameter query diuji lewat HTTP (tanpa lifespan, jadi tidak ada panggilan Gemini)."""

    def setUp(self):
        super().setUp()
        self.addCleanup(app.dependency_overrides.clear)
        app.dependency_overrides[get_current_user] = lambda: {"id": STUDENT, "role": "student", "name": "Rani"}
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        self.client = TestClient(app)
        self.result = {"items": [], "total": 0, **{k: 0 for k in COUNTS}}

    def test_type_query_param_and_limit_reach_the_repository(self):
        with patch("api.sessions.list_student_sessions", AsyncMock(return_value=self.result)) as repo:
            res = self.client.get("/api/v1/sessions?type=class&scenario_id=3&limit=5")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(repo.call_args.kwargs, {"kind": "class", "scenario_id": 3, "limit": 5})
        self.assertEqual(set(res.json()), {"items", "total", "total_sessions", "completed_sessions", "awaiting_evaluation", "evaluation_failed", "total_duration_seconds"})

    def test_invalid_type_or_limit_rejected(self):
        with patch("api.sessions.list_student_sessions", AsyncMock(return_value=self.result)) as repo:
            self.assertEqual(self.client.get("/api/v1/sessions?type=dosen").status_code, 422)
            self.assertEqual(self.client.get("/api/v1/sessions?limit=101").status_code, 422)  # batas 100 baris
        repo.assert_not_called()

    def test_lecturer_cannot_use_student_history(self):
        app.dependency_overrides[get_current_user] = lambda: {"id": 2, "role": "lecturer", "name": "Dosen"}
        with patch("api.sessions.list_student_sessions", AsyncMock(return_value=self.result)) as repo:
            self.assertEqual(self.client.get("/api/v1/sessions").status_code, 403)
        repo.assert_not_called()
