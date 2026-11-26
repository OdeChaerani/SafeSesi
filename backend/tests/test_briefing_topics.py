from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from api.sessions import get_briefing_topics, get_session_detail, student_visible_topics
from tests.base import BaseTestCase

PARENT_ID = 101
CHILD_ID = 102

# Catatan topik terbaru sesi induk: H2 belum terungkap (deskripsi kosong / spasi).
PARENT_NOTES = [
    {
        "session_topic_id": 1,
        "sort_order": 1,
        "topic_name": "Permasalahan utama",
        "source": "main_problem",
        "hidden_fact_code": None,
        "description": "Klien kewalahan membagi kuliah dan organisasi.",
        "turn_id": 20,
    },
    {
        "session_topic_id": 2,
        "sort_order": 2,
        "topic_name": "Penilaian teman",
        "source": "hidden_fact",
        "hidden_fact_code": "H1",
        "description": "Klien takut dinilai teman bila membatasi tugas.",
        "turn_id": 22,
    },
    {
        "session_topic_id": 3,
        "sort_order": 3,
        "topic_name": "JUDUL-RAHASIA-H2",
        "source": "hidden_fact",
        "hidden_fact_code": "H2",
        "description": "",
        "turn_id": None,
    },
    {
        "session_topic_id": 4,
        "sort_order": 4,
        "topic_name": "JUDUL-RAHASIA-H4",
        "source": "hidden_fact",
        "hidden_fact_code": "H4",
        "description": "   ",
        "turn_id": None,
    },
]

EXPECTED_STUDENT_TOPICS = [
    {"name": "Permasalahan utama", "description": "Klien kewalahan membagi kuliah dan organisasi."},
    {"name": "Penilaian teman", "description": "Klien takut dinilai teman bila membatasi tugas."},
]


class TestBriefingTopics(BaseTestCase):
    """BRD 6.1.2: catatan topik sesi induk pada briefing/sesi lanjutan."""

    def setUp(self):
        super().setUp()
        self.student = self.get_sample_user(user_id=10, role="student")
        self.lecturer = self.get_sample_user(user_id=1, role="lecturer")
        self.conn = self.create_mock_connection()
        self.parent = self.get_sample_session(session_id=PARENT_ID, student_id=10, status="completed")
        self.child = {**self.get_sample_session(session_id=CHILD_ID, student_id=10), "parent_session_id": PARENT_ID}

    def _assert_no_hidden_titles(self, payload) -> None:
        dumped = json.dumps(payload, default=str)
        self.assertNotIn("JUDUL-RAHASIA", dumped)
        self.assertNotIn("hidden_fact_code", dumped)

    def test_student_visible_topics_drops_empty(self):
        self.assertEqual(student_visible_topics(PARENT_NOTES), EXPECTED_STUDENT_TOPICS)
        self.assertEqual(student_visible_topics([]), [])

    @patch("api.sessions.get_evaluation_by_session", new_callable=AsyncMock, return_value=None)
    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_briefing_topics_student_only_non_empty(self, mock_get_sess, mock_notes, _evaluation):
        mock_get_sess.return_value = self.parent
        mock_notes.return_value = PARENT_NOTES

        res = self.run_async(get_briefing_topics(session_id=PARENT_ID, user=self.student, conn=self.conn))

        self.assertEqual(res["topics"], EXPECTED_STUDENT_TOPICS)
        self._assert_no_hidden_titles(res)
        mock_notes.assert_called_once_with(self.conn, PARENT_ID)
        self.assertEqual(res["evaluation_status"], "none")  # untuk tautan hasil evaluasi di briefing lanjutan

    @patch("api.sessions.get_evaluation_by_session", new_callable=AsyncMock, return_value=None)
    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_briefing_topics_lecturer_sees_all(self, mock_get_sess, mock_notes, _evaluation):
        # Dosen hanya melihat sesi kelas yang dikelolanya; di sana ia melihat semua topik.
        mock_get_sess.return_value = {**self.parent, "class_id": 3}
        mock_notes.return_value = PARENT_NOTES

        with patch("api.deps.lecturer_manages_session", AsyncMock(return_value=True)):
            res = self.run_async(get_briefing_topics(session_id=PARENT_ID, user=self.lecturer, conn=self.conn))

        self.assertEqual(len(res["topics"]), 4)
        self.assertIn("JUDUL-RAHASIA-H2", json.dumps(res))

    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_briefing_topics_other_student_forbidden(self, mock_get_sess, mock_notes):
        mock_get_sess.return_value = self.parent
        other = self.get_sample_user(user_id=99, role="student")

        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_briefing_topics(session_id=PARENT_ID, user=other, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)
        mock_notes.assert_not_called()

    @patch("api.sessions.get_session_turns")
    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_continue_session_detail_student_previous_topics(self, mock_get_sess, mock_notes, mock_turns):
        mock_get_sess.return_value = self.child
        mock_notes.return_value = PARENT_NOTES
        mock_turns.return_value = []

        detail = self.run_async(get_session_detail(session_id=CHILD_ID, user=self.student, conn=self.conn))

        self.assertEqual(detail["previous_topics"], EXPECTED_STUDENT_TOPICS)
        self.assertNotIn("topics", detail)
        self.assertNotIn("scenario_snapshot", detail)
        self._assert_no_hidden_titles(detail)
        mock_notes.assert_called_once_with(self.conn, PARENT_ID)

    @patch("api.sessions.get_session_turns")
    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_first_session_detail_sends_no_topics(self, mock_get_sess, mock_notes, mock_turns):
        mock_get_sess.return_value = self.get_sample_session(session_id=PARENT_ID, student_id=10)
        mock_notes.return_value = PARENT_NOTES
        mock_turns.return_value = []

        detail = self.run_async(get_session_detail(session_id=PARENT_ID, user=self.student, conn=self.conn))

        self.assertEqual(detail["previous_topics"], [])
        self.assertNotIn("topics", detail)
        mock_notes.assert_not_called()

    @patch("api.sessions.get_session_turns")
    @patch("api.sessions.get_latest_topic_notes")
    @patch("api.sessions.get_session_by_id")
    def test_continue_session_detail_lecturer_sees_all(self, mock_get_sess, mock_notes, mock_turns):
        mock_get_sess.return_value = {**self.child, "class_id": 3}
        mock_notes.return_value = PARENT_NOTES
        mock_turns.return_value = []

        with patch("api.deps.lecturer_manages_session", AsyncMock(return_value=True)):
            detail = self.run_async(get_session_detail(session_id=CHILD_ID, user=self.lecturer, conn=self.conn))

        self.assertEqual(len(detail["previous_topics"]), 4)
        self.assertEqual(len(detail["topics"]), 4)
