"""Status percobaan di katalog: query asli dijalankan di SQLite, hanya sesi milik pemanggil yang dihitung."""
from __future__ import annotations

import sqlite3

from repositories.scenarios import get_catalog_scenarios
from schemas.scenario import CatalogScenarioItem
from tests.base import BaseTestCase

STUDENT = 10


class SqliteConn:
    def __init__(self) -> None:
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            """
            CREATE TABLE scenarios (id INTEGER, title TEXT, change_target TEXT, visibility TEXT, deleted_at TEXT);
            CREATE TABLE scenario_personas (scenario_id INTEGER, name TEXT, age INTEGER, gender TEXT,
                avatar_file TEXT, occupation TEXT, education TEXT);
            CREATE TABLE scenario_cases (scenario_id INTEGER, initial_summary TEXT);
            CREATE TABLE sessions (id INTEGER, scenario_id INTEGER, student_id INTEGER, class_id INTEGER,
                status TEXT, deleted_at TEXT);
            INSERT INTO scenarios VALUES (1, 'Judul', 'Target', 'catalog', NULL);
            INSERT INTO scenario_personas VALUES (1, 'Klien', 20, 'Perempuan', NULL, 'Mahasiswa', NULL);
            INSERT INTO scenario_cases VALUES (1, 'Ringkasan');
            """
        )

    async def fetch(self, query: str, *args):
        cursor = self.db.execute(query, {str(i): value for i, value in enumerate(args, 1)})
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


class TestCatalogAttempts(BaseTestCase):
    def setUp(self):
        self.conn = SqliteConn()
        self.addCleanup(self.conn.db.close)

    def _session(self, session_id, status="completed", student=STUDENT, class_id=None, deleted=None):
        self.conn.db.execute("INSERT INTO sessions VALUES (?, 1, ?, ?, ?, ?)", (session_id, student, class_id, status, deleted))

    def _item(self) -> CatalogScenarioItem:
        result = self.run_async(get_catalog_scenarios(self.conn, STUDENT))
        return CatalogScenarioItem(**result["items"][0])

    def test_never_attempted(self):
        item = self._item()
        self.assertEqual((item.attempt_status, item.completed_attempts, item.active_session_id), ("unattempted", 0, None))

    def test_counts_completed_and_reports_running_session(self):
        self._session(1)
        self._session(2)
        self._session(3, status="in_progress")
        item = self._item()
        self.assertEqual((item.completed_attempts, item.total_attempts, item.active_session_id), (2, 3, 3))

    def test_only_running_session_has_no_completed(self):
        self._session(1, status="in_progress")
        item = self._item()
        self.assertEqual((item.attempt_status, item.completed_attempts, item.active_session_id), ("attempted", 0, 1))

    def test_other_students_deleted_and_class_sessions_ignored(self):
        self._session(1, student=99)
        self._session(2, student=99, status="in_progress")
        self._session(3, deleted="2026-11-01")
        self._session(4, class_id=7)
        item = self._item()
        self.assertEqual((item.attempt_status, item.completed_attempts, item.active_session_id), ("unattempted", 0, None))
