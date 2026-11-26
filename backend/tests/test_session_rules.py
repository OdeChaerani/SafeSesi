"""Aturan pembuatan sesi: latihan kelas, ulangi (repeat), dan lanjutkan (continue). DB dan Gemini di-mock."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from api.sessions import create_new_session
from repositories.scenarios import validate_class_access
from schemas.session import CreateSessionRequest
from tests.base import BaseTestCase

STUDENT = 10


class TestCreateSessionRules(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.get_sample_user(user_id=STUDENT, role="student")
        self.conn = self.create_mock_connection()
        self.snapshot = self.get_sample_snapshot()

    def source(self, **kw: Any) -> dict[str, Any]:
        """Sesi sumber (induk/asal) yang selesai, milik mahasiswa, di kelas 3."""
        base = {
            "id": 50, "student_id": STUDENT, "scenario_id": 1, "class_id": 3, "status": "completed",
            "scenario_snapshot": {**self.snapshot, "persona": {**self.snapshot["persona"], "name": "Snapshot Lama"}},
        }
        return {**base, **kw}

    def create(self, payload: CreateSessionRequest, *, visibility="catalog", source=None, class_access=True):
        async def fake_create_session(**kw: Any) -> dict[str, Any]:
            return {"id": 200, "status": "in_progress", "started_at": "2026-11-21T10:00:00Z", "ended_at": None,
                    "duration_seconds": None, **kw}

        self.mocks = {
            "scenario": AsyncMock(return_value={"id": 1, "visibility": visibility}),
            "source": AsyncMock(return_value=source),
            "access": AsyncMock(return_value=class_access),
            "build": AsyncMock(return_value=self.snapshot),
            "create": AsyncMock(side_effect=fake_create_session),
            "state": AsyncMock(return_value=None),
            "notes": AsyncMock(),
        }
        m = self.mocks
        with patch("api.sessions.get_scenario_by_id", m["scenario"]), \
             patch("api.sessions.get_session_by_id", m["source"]), \
             patch("api.sessions.validate_class_access", m["access"]), \
             patch("api.sessions.build_scenario_snapshot", m["build"]), \
             patch("api.sessions.create_session", m["create"]), \
             patch("api.sessions.create_session_topics_from_snapshot", AsyncMock(return_value=[{"id": 1}])), \
             patch("api.sessions.save_client_state", m["state"]), \
             patch("api.sessions.save_topic_note", AsyncMock()), \
             patch("api.sessions.get_latest_client_state", AsyncMock(return_value=None)), \
             patch("api.sessions.copy_topic_notes_from_parent", m["notes"]):
            return self.run_async(create_new_session(payload=payload, user=self.user, conn=self.conn))

    def status_of(self, payload: CreateSessionRequest, **kw: Any) -> int:
        with self.assertRaises(HTTPException) as ctx:
            self.create(payload, **kw)
        return ctx.exception.status_code

    # --- latihan kelas ---------------------------------------------------------------------

    def test_class_session_requires_active_membership_and_assignment(self):
        payload = CreateSessionRequest(scenario_id=1, class_id=3)
        self.assertEqual(self.status_of(payload, class_access=False), 403)
        self.mocks["create"].assert_not_called()

    def test_class_session_saves_class_id(self):
        res = self.create(CreateSessionRequest(scenario_id=1, class_id=3))
        self.assertEqual(res["class_id"], 3)
        self.mocks["access"].assert_awaited_once_with(self.conn, 1, 3, STUDENT)
        self.assertEqual(self.mocks["create"].call_args.kwargs["class_id"], 3)

    def test_class_scenario_not_allowed_as_independent_practice(self):
        # skenario khusus kelas tidak boleh dilatih mandiri (tanpa class_id)
        self.assertEqual(self.status_of(CreateSessionRequest(scenario_id=1), visibility="class"), 403)

    def test_membership_query_ignores_removed_members(self):
        self.conn.fetchrow.return_value = None
        self.assertFalse(self.run_async(validate_class_access(self.conn, 1, 3, STUDENT)))
        sql = self.conn.fetchrow.call_args.args[0]
        self.assertIn("cm.deleted_at IS NULL", sql)
        self.assertIn("cm.user_id = $3", sql)

    # --- lanjutkan -------------------------------------------------------------------------

    def cont(self, **kw: Any) -> CreateSessionRequest:
        return CreateSessionRequest(scenario_id=1, mode="continue", parent_session_id=50, **kw)

    def test_continue_other_students_session_forbidden(self):
        self.assertEqual(self.status_of(self.cont(), source=self.source(student_id=99)), 403)

    def test_continue_unfinished_session_rejected(self):
        self.assertEqual(self.status_of(self.cont(), source=self.source(status="in_progress")), 400)

    def test_continue_with_different_scenario_rejected(self):
        self.assertEqual(self.status_of(self.cont(), source=self.source(scenario_id=2)), 400)

    def test_continue_missing_parent_404(self):
        self.assertEqual(self.status_of(self.cont(), source=None), 404)

    def test_continue_requires_parent_id(self):
        self.assertEqual(self.status_of(CreateSessionRequest(scenario_id=1, mode="continue")), 400)

    def test_continue_follows_parent_class_and_snapshot(self):
        res = self.create(self.cont(), source=self.source())
        self.assertEqual((res["class_id"], res["parent_session_id"]), (3, 50))
        self.mocks["access"].assert_awaited_once_with(self.conn, 1, 3, STUDENT)  # akses kelas dicek ulang
        self.mocks["build"].assert_not_called()  # versi skenario sesi pertama, bukan versi terbaru
        self.assertEqual(self.mocks["create"].call_args.kwargs["scenario_snapshot"]["persona"]["name"], "Snapshot Lama")
        self.mocks["notes"].assert_awaited_once_with(self.conn, 50, 200)

    def test_continue_of_independent_session_stays_independent(self):
        res = self.create(self.cont(), source=self.source(class_id=None))
        self.assertIsNone(res["class_id"])
        self.mocks["access"].assert_not_called()

    def test_continue_class_id_mismatch_rejected(self):
        self.assertEqual(self.status_of(self.cont(class_id=4), source=self.source()), 400)
        # sesi mandiri tidak boleh "dipindahkan" ke kelas lewat permintaan
        self.assertEqual(self.status_of(self.cont(class_id=4), source=self.source(class_id=None)), 400)

    def test_continue_class_session_after_membership_removed(self):
        self.assertEqual(self.status_of(self.cont(), source=self.source(), class_access=False), 403)

    # --- ulangi ----------------------------------------------------------------------------

    def rep(self, **kw: Any) -> CreateSessionRequest:
        return CreateSessionRequest(scenario_id=1, mode="repeat", repeat_of_session_id=50, **kw)

    def test_repeat_copies_class_without_parent_and_starts_from_initial_state(self):
        res = self.create(self.rep(), source=self.source(status="in_progress"))  # tidak wajib selesai
        self.assertEqual((res["class_id"], res["parent_session_id"]), (3, None))
        self.mocks["build"].assert_awaited_once()  # snapshot terbaru dari skenario
        self.mocks["notes"].assert_not_called()
        self.mocks["state"].assert_awaited_once_with(self.conn, 200, turn_id=None, state=self.snapshot["initial_state"])

    def test_repeat_of_other_students_session_forbidden(self):
        self.assertEqual(self.status_of(self.rep(), source=self.source(student_id=99)), 403)

    def test_repeat_with_different_scenario_rejected(self):
        self.assertEqual(self.status_of(self.rep(), source=self.source(scenario_id=2)), 400)

    def test_repeat_class_mismatch_rejected(self):
        self.assertEqual(self.status_of(self.rep(class_id=4), source=self.source()), 400)

    def test_repeat_without_origin_behaves_like_new(self):
        res = self.create(CreateSessionRequest(scenario_id=1, mode="repeat"))
        self.assertEqual((res["class_id"], res["parent_session_id"]), (None, None))
        self.mocks["source"].assert_not_called()
