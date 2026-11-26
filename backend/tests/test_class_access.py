"""validate_class_access: query aslinya dijalankan pada SQLite di memori, jadi yang diuji perilaku SQL-nya."""
from __future__ import annotations

import sqlite3

from repositories.evaluations import lecturer_manages_session
from repositories.scenarios import validate_class_access
from repositories.sessions import get_session_by_id
from tests.base import BaseTestCase


class SqliteConn:
    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE classes (id INTEGER, deleted_at TEXT);
            CREATE TABLE class_members (class_id INTEGER, user_id INTEGER, deleted_at TEXT);
            CREATE TABLE class_scenarios (class_id INTEGER, scenario_id INTEGER);
            CREATE TABLE scenarios (id INTEGER, deleted_at TEXT);
            INSERT INTO classes VALUES (1, NULL);
            INSERT INTO scenarios VALUES (5, NULL);
            INSERT INTO class_scenarios VALUES (1, 5);
            """
        )

    async def fetchrow(self, query: str, *args):
        return self.db.execute(query, {str(i): value for i, value in enumerate(args, 1)}).fetchone()


class TestClassAccess(BaseTestCase):
    def setUp(self):
        self.conn = SqliteConn()
        self.addCleanup(self.conn.db.close)

    def _member(self, deleted_at: str | None = None, user_id: int = 10) -> None:
        self.conn.db.execute("INSERT INTO class_members VALUES (1, ?, ?)", (user_id, deleted_at))

    def _allowed(self) -> bool:
        return self.run_async(validate_class_access(self.conn, 5, 1, 10))

    def test_active_member_allowed(self):
        self._member()
        self.assertTrue(self._allowed())

    def test_soft_deleted_member_rejected(self):
        self._member(deleted_at="2026-11-01")
        self._member(user_id=11)  # anggota aktif lain tidak boleh meloloskan
        self.assertFalse(self._allowed())

    def test_rejoined_member_allowed(self):
        self._member(deleted_at="2026-11-01")
        self._member()
        self.assertTrue(self._allowed())

    def test_deleted_class_rejected(self):
        self._member()
        self.conn.db.execute("UPDATE classes SET deleted_at = '2026-11-01'")
        self.assertFalse(self._allowed())


class TestDeletedRowsHidden(BaseTestCase):
    def setUp(self):
        self.conn = SqliteConn()
        self.addCleanup(self.conn.db.close)

    async def _fetchval(self, query: str, *args):
        return (await self.conn.fetchrow(query, *args))[0]

    def test_lecturer_cannot_view_session_of_deleted_class(self):
        self.conn.db.executescript(
            """
            CREATE TABLE v_sessions_for_lecturer (id INTEGER, class_id INTEGER, lecturer_id INTEGER);
            INSERT INTO v_sessions_for_lecturer VALUES (100, 1, 7);
            """
        )
        self.conn.fetchval = self._fetchval
        self.assertTrue(self.run_async(lecturer_manages_session(self.conn, 100, 7)))
        self.conn.db.execute("UPDATE classes SET deleted_at = '2026-11-01'")
        self.assertFalse(self.run_async(lecturer_manages_session(self.conn, 100, 7)))

    def test_soft_deleted_session_not_returned(self):
        self.conn.db.executescript(
            """
            CREATE TABLE sessions (
                id INTEGER, student_id INTEGER, scenario_id INTEGER, class_id INTEGER, parent_session_id INTEGER,
                scenario_snapshot TEXT, status TEXT, started_at TEXT, ended_at TEXT, duration_seconds INTEGER,
                deleted_at TEXT
            );
            INSERT INTO sessions VALUES (100, 10, 5, NULL, NULL, '{}', 'completed', 'x', NULL, NULL, NULL);
            """
        )

        async def fetch_dict(query: str, *args):
            cursor = self.conn.db.execute(query, {str(i): v for i, v in enumerate(args, 1)})
            row = cursor.fetchone()
            return dict(zip([c[0] for c in cursor.description], row)) if row else None

        self.conn.fetchrow = fetch_dict
        self.assertEqual(self.run_async(get_session_by_id(self.conn, 100))["id"], 100)
        self.conn.db.execute("UPDATE sessions SET deleted_at = '2026-11-01'")
        self.assertIsNone(self.run_async(get_session_by_id(self.conn, 100)))

