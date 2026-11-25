"""validate_class_access: query aslinya dijalankan pada SQLite di memori, jadi yang diuji perilaku SQL-nya."""
from __future__ import annotations

import sqlite3

from repositories.scenarios import validate_class_access
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
