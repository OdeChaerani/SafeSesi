"""Kelas mahasiswa, ringkasan publik skenario, dan pemisahan katalog umum dari skenario kelas."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.classes import list_class_scenarios, list_my_classes
from api.deps import get_current_user, get_db
from main import app
from repositories.classes import list_user_classes
from repositories.scenarios import fetch_public_scenarios, get_catalog_scenarios
from schemas.student import ClassScenariosResponse
from tests.base import BaseTestCase

STUDENT = 10
# Kolom/tabel yang berisi persona lengkap, isi kasus, fakta tersembunyi, dan kondisi klien.
HIDDEN_SQL_MARKERS = (
    "scenario_hidden_facts", "scenario_initial_states", "main_problem", "history_impact",
    "expectation_change_context", "health_condition", "personality", "communication_style",
    "family_background", "additional_background", "marital_status",
)
HIDDEN_KEYS = ("hidden_facts", "persona", "case", "initial_state", "main_problem", "history_impact",
               "personality", "scenario_snapshot", "emotion_type", "disclosure_level")


def public_row(**kw: Any) -> dict[str, Any]:
    return {
        "id": 1, "title": "SS-NAD-01 Nadia Maharani", "change_target": "Membatasi tugas tambahan",
        "client_name": "Nadia Maharani", "client_age": 19, "client_gender": "Perempuan",
        "client_avatar_file": "girl1.glb", "client_role": "Mahasiswi", "initial_summary": "Nadia ingin berubah.",
        "attempt_status": "unattempted", "total_attempts": 0, "last_completed_session_id": None,
        "active_session_id": None, **kw,
    }


class TestStudentClasses(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.get_sample_user(user_id=STUDENT, role="student")
        self.conn = self.create_mock_connection()

    def test_class_list_query_is_scoped_to_active_membership(self):
        self.conn.fetch.return_value = []
        self.run_async(list_user_classes(self.conn, STUDENT))
        sql, arg = self.conn.fetch.call_args.args[0], self.conn.fetch.call_args.args[1]
        self.assertEqual(arg, STUDENT)
        for fragment in ("cm.user_id = $1", "cm.deleted_at IS NULL", "cl.deleted_at IS NULL", "u.role = 'lecturer'"):
            self.assertIn(fragment, sql)

    def test_list_my_classes_returns_class_with_lecturers(self):
        rows = [{"id": 3, "name": "Kelas Uji", "academic_year": "2026/2027", "lecturers": ["Dr. A"], "scenario_count": 2}]
        with patch("api.classes.list_user_classes", AsyncMock(return_value=rows)) as repo:
            res = self.run_async(list_my_classes(user=self.user, conn=self.conn))
        repo.assert_awaited_once_with(self.conn, STUDENT)
        self.assertEqual(res[0]["lecturers"], ["Dr. A"])

    def call_scenarios(self, *, class_info: Any, member: bool):
        with patch("api.classes.get_class", AsyncMock(return_value=class_info)), \
             patch("api.classes.is_class_member", AsyncMock(return_value=member)), \
             patch("api.classes.fetch_public_scenarios", AsyncMock(return_value=[public_row()])) as fetch:
            result = self.run_async(list_class_scenarios(class_id=3, user=self.user, conn=self.conn))
            return result, fetch

    def test_non_member_cannot_see_class_scenarios(self):
        info = {"id": 3, "name": "Kelas Lain", "academic_year": "2026/2027", "lecturers": []}
        with patch("api.classes.get_class", AsyncMock(return_value=info)), \
             patch("api.classes.is_class_member", AsyncMock(return_value=False)), \
             patch("api.classes.fetch_public_scenarios", AsyncMock()) as fetch:
            with self.assertRaises(HTTPException) as ctx:
                self.run_async(list_class_scenarios(class_id=3, user=self.user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)
        fetch.assert_not_called()  # data skenario tidak pernah dibaca untuk non-anggota

    def test_unknown_class_404(self):
        with patch("api.classes.get_class", AsyncMock(return_value=None)):
            with self.assertRaises(HTTPException) as ctx:
                self.run_async(list_class_scenarios(class_id=99, user=self.user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_member_sees_public_scenarios_of_class_only(self):
        info = {"id": 3, "name": "Kelas Uji", "academic_year": "2026/2027", "lecturers": ["Dr. A"]}
        res, fetch = self.call_scenarios(class_info=info, member=True)
        fetch.assert_awaited_once_with(self.conn, STUDENT, class_id=3)
        body = ClassScenariosResponse.model_validate(res).model_dump(mode="json")
        self.assertEqual(body["class_info"]["scenario_count"], 1)
        self.assertEqual(body["items"][0]["client_name"], "Nadia Maharani")
        dumped = json.dumps(body)
        for key in HIDDEN_KEYS:
            self.assertNotIn(f'"{key}"', dumped)


class TestPublicScenarioQueries(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn = self.create_mock_connection()
        self.conn.fetch.return_value = []

    def sql_and_args(self):
        call = self.conn.fetch.call_args
        return call.args[0], call.args[1:]

    def test_catalog_only_shows_catalog_scenarios_and_independent_attempts(self):
        self.run_async(get_catalog_scenarios(self.conn, STUDENT))
        sql, args = self.sql_and_args()
        self.assertIn("sc.visibility = 'catalog'", sql)  # skenario khusus kelas tidak ikut
        self.assertIn("se.class_id IS NULL", sql)  # percobaan kelas tidak dihitung di katalog
        self.assertNotIn("class_scenarios", sql)
        self.assertEqual(args, (STUDENT,))

    def test_class_query_requires_assignment_and_counts_only_that_class(self):
        self.run_async(fetch_public_scenarios(self.conn, STUDENT, class_id=3))
        sql, args = self.sql_and_args()
        self.assertIn("JOIN class_scenarios cs ON cs.scenario_id = sc.id AND cs.class_id = $2", sql)
        self.assertIn("se.class_id = $2", sql)
        self.assertNotIn("visibility", sql)
        self.assertEqual(args, (STUDENT, 3))

    def test_queries_never_select_hidden_case_data(self):
        for kwargs in ({"catalog_only": True}, {"class_id": 3}, {"scenario_id": 1, "catalog_only": True}):
            self.run_async(fetch_public_scenarios(self.conn, STUDENT, **kwargs))
            sql, _ = self.sql_and_args()
            for marker in HIDDEN_SQL_MARKERS:
                self.assertNotIn(marker, sql, f"{marker} terpilih pada {kwargs}")

    def test_catalog_search_by_title_or_change_target(self):
        self.conn.fetch.return_value = [
            public_row(id=1, title="Kelelahan Akademik", change_target="Membatasi tugas"),
            public_row(id=2, title="Aktif Bergerak", change_target="Berjalan kaki bertahap"),
        ]
        by_title = self.run_async(get_catalog_scenarios(self.conn, STUDENT, search="kelelahan"))
        by_target = self.run_async(get_catalog_scenarios(self.conn, STUDENT, search="berjalan kaki"))
        self.assertEqual([i["id"] for i in by_title["items"]], [1])
        self.assertEqual([i["id"] for i in by_target["items"]], [2])


class TestScenarioBriefingEndpoint(BaseTestCase):
    """GET /scenarios/{id} diuji lewat HTTP (tanpa lifespan, jadi tidak ada panggilan Gemini)
    agar response_model benar-benar ikut menyaring respons."""

    def setUp(self):
        super().setUp()
        self.addCleanup(app.dependency_overrides.clear)
        app.dependency_overrides[get_current_user] = lambda: {"id": STUDENT, "role": "student", "name": "Rani"}
        app.dependency_overrides[get_db] = lambda: MagicMock()
        self.client = TestClient(app)

    def get(self, path: str, rows: list[dict[str, Any]], class_access: bool = True):
        with patch("api.scenarios.fetch_public_scenarios", AsyncMock(return_value=rows)) as fetch, \
             patch("api.scenarios.validate_class_access", AsyncMock(return_value=class_access)):
            return self.client.get(path), fetch

    def test_response_only_contains_public_summary(self):
        polluted = public_row(
            hidden_facts=[{"code": "H1"}], persona={"personality": "rahasia"}, case={"main_problem": "rahasia"},
            initial_state={"emotion_type": "cemas"}, personality="rahasia", main_problem="rahasia",
        )
        res, _ = self.get("/api/v1/scenarios/1", [polluted])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            set(res.json()),
            {"id", "title", "change_target", "client_name", "client_age", "client_gender", "client_avatar_file",
             "client_role", "initial_summary", "attempt_status", "total_attempts", "last_completed_session_id",
             "active_session_id"},
        )
        for key in HIDDEN_KEYS:
            self.assertNotIn(key, res.json())

    def test_catalog_scenario_without_class(self):
        res, fetch = self.get("/api/v1/scenarios/1", [public_row()])
        self.assertEqual(res.status_code, 200)
        fetch.assert_awaited_once()
        self.assertEqual(fetch.call_args.kwargs, {"class_id": None, "scenario_id": 1, "catalog_only": True})

    def test_class_only_scenario_is_not_found_without_class(self):
        res, _ = self.get("/api/v1/scenarios/7", [])  # bukan skenario katalog: query kosong
        self.assertEqual(res.status_code, 404)

    def test_class_scenario_forbidden_for_non_member(self):
        res, fetch = self.get("/api/v1/scenarios/1?class_id=3", [public_row()], class_access=False)
        self.assertEqual(res.status_code, 403)
        fetch.assert_not_called()

    def test_class_scenario_for_member(self):
        res, fetch = self.get("/api/v1/scenarios/1?class_id=3", [public_row()])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(fetch.call_args.kwargs, {"class_id": 3, "scenario_id": 1, "catalog_only": False})
