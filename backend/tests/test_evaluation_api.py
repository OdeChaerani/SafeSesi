"""API evaluasi MITI (POST/GET /sessions/{id}/evaluation) dengan DB dan Gemini di-mock."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Response

from api.evaluations import build_input, get_evaluation, run_evaluation_job, start_evaluation
from tests.base import BaseTestCase


def session(status: str = "completed", student_id: int = 10, class_id: int | None = None, duration: int = 700) -> dict[str, Any]:
    return {
        "id": 5, "student_id": student_id, "class_id": class_id, "status": status, "duration_seconds": duration,
        "scenario_snapshot": {
            "scenario": {"change_target": "Membagi tanggung jawab"},
            "case": {"initial_summary": "Ringkasan publik"},
            "hidden_facts": [{"fact": "RAHASIA"}],
            "persona": {"name": "X", "personality": "RAHASIA-PERSONA"},
        },
    }


def evaluation(status: str = "completed") -> dict[str, Any]:
    return {"id": 77, "session_id": 5, "status": status, "guideline_version": "MITI 4.2.1 / Rubrik SafeSesi v1",
            "model_version": "m", "assessed_duration_seconds": 700, "limitation_notes": None,
            "error_message": None, "coding_debug": {"units": []}, "completed_at": None}


DETAILS = {
    "codes": [
        {"turn_no": 1, "unit_no": 1, "code": "SR", "excerpt": "e", "reason": "r", "uncertainty_note": None},
        {"turn_no": 1, "unit_no": 2, "code": "Q", "excerpt": "e", "reason": "r", "uncertainty_note": None},
        {"turn_no": 3, "unit_no": 1, "code": "CR", "excerpt": "e", "reason": "r", "uncertainty_note": None},
    ],
    "globals": [{"dimension": d, "score": 4, "reason": "r", "evidence_turn_nos": [1]}
                for d in ("cultivating_change_talk", "softening_sustain_talk", "partnership", "empathy")],
    "processes": [{"process": "focusing", "start_turn_no": None, "end_turn_no": None, "excerpt": None, "reason": "r"}],
    "feedback": [{"kind": "strength", "turn_no": 1, "excerpt": "e", "content": "c", "evidence_turn_nos": []}],
}


class TestStartEvaluation(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.request = MagicMock()
        self.student = self.get_sample_user(user_id=10)

    def call(self, user: dict[str, Any]) -> tuple[dict[str, Any], Response]:
        response = Response()
        res = self.run_async(start_evaluation(5, self.request, response, conn=self.conn, user=user))
        return res, response

    @patch("api.evaluations.get_session_by_id", new_callable=AsyncMock)
    def test_only_owner_can_start(self, get_session):
        get_session.return_value = session(student_id=99)
        with self.assertRaises(HTTPException) as ctx:
            self.call(self.student)
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HTTPException):
            self.call(self.get_sample_user(user_id=1, role="lecturer"))

    @patch("api.evaluations.get_session_by_id", new_callable=AsyncMock)
    def test_session_must_be_completed(self, get_session):
        get_session.return_value = session(status="in_progress")
        with self.assertRaises(HTTPException) as ctx:
            self.call(self.student)
        self.assertEqual(ctx.exception.status_code, 400)

    @patch("api.evaluations.spawn_background")
    @patch("api.evaluations.claim_evaluation", new_callable=AsyncMock)
    @patch("api.evaluations.get_session_by_id", new_callable=AsyncMock)
    def test_new_evaluation_runs_in_background(self, get_session, claim, spawn):
        get_session.return_value = session()
        claim.return_value = (evaluation("running"), True)
        res, response = self.call(self.student)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(res["status"], "running")
        spawn.assert_called_once()
        spawn.call_args.args[0].close()  # coroutine tidak dijalankan di tes ini
        self.assertEqual(claim.call_args.args[2], "MITI 4.2.1 / Rubrik SafeSesi v1")

    @patch("api.evaluations.spawn_background")
    @patch("api.evaluations.claim_evaluation", new_callable=AsyncMock)
    @patch("api.evaluations.get_session_by_id", new_callable=AsyncMock)
    def test_existing_evaluation_returned_without_rerun(self, get_session, claim, spawn):
        get_session.return_value = session()
        claim.return_value = (evaluation("completed"), False)
        res, response = self.call(self.student)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(res["status"], "completed")
        spawn.assert_not_called()


class TestGetEvaluation(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()

    def call(self, user: dict[str, Any]) -> dict[str, Any]:
        return self.run_async(get_evaluation(5, conn=self.conn, user=user))

    def patches(self, sess: dict[str, Any], ev: dict[str, Any] | None, manages: bool = False):
        return (
            patch("api.evaluations.get_session_by_id", AsyncMock(return_value=sess)),
            patch("api.evaluations.get_evaluation_by_session", AsyncMock(return_value=ev)),
            patch("api.evaluations.get_evaluation_details", AsyncMock(return_value=DETAILS)),
            patch("api.evaluations.lecturer_manages_session", AsyncMock(return_value=manages)),
        )

    def run_with(self, user, sess, ev, manages=False):
        p1, p2, p3, p4 = self.patches(sess, ev, manages)
        with p1, p2, p3, p4:
            return self.call(user)

    def test_student_sees_own_evaluation_without_debug(self):
        res = self.run_with(self.get_sample_user(user_id=10), session(), evaluation())
        self.assertEqual(res["frequencies"]["SR"], 1)
        self.assertEqual(res["frequencies"]["PWP"], 0)
        self.assertEqual(res["codes_by_turn"][0]["turn_no"], 1)
        self.assertEqual(res["summary_measures"]["reflection_question_ratio"]["value"], 2.0)
        self.assertEqual(res["summary_measures"]["technical_global"]["value"], 4.0)
        self.assertFalse(res["processes"][0]["evidence_found"])
        self.assertNotIn("coding_debug", res)

    def test_student_cannot_see_other_students_evaluation(self):
        with self.assertRaises(HTTPException) as ctx:
            self.run_with(self.get_sample_user(user_id=11), session(), evaluation())
        self.assertEqual(ctx.exception.status_code, 403)

    def test_lecturer_only_for_managed_class(self):
        lecturer = self.get_sample_user(user_id=2, role="lecturer")
        with self.assertRaises(HTTPException):
            self.run_with(lecturer, session(class_id=None), evaluation(), manages=True)
        with self.assertRaises(HTTPException):
            self.run_with(lecturer, session(class_id=3), evaluation(), manages=False)
        res = self.run_with(lecturer, session(class_id=3), evaluation(), manages=True)
        self.assertIn("coding_debug", res)

    def test_admin_sees_all(self):
        res = self.run_with(self.get_sample_user(user_id=1, role="admin"), session(), evaluation())
        self.assertIn("coding_debug", res)

    def test_running_returns_status_only(self):
        res = self.run_with(self.get_sample_user(user_id=10), session(), evaluation("running"))
        self.assertEqual(res["status"], "running")
        self.assertNotIn("frequencies", res)

    def test_missing_evaluation_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.run_with(self.get_sample_user(user_id=10), session(), None)
        self.assertEqual(ctx.exception.status_code, 404)


class TestEvaluationJob(BaseTestCase):
    def pool(self, conn):
        pool = MagicMock()
        acquire = MagicMock()
        acquire.__aenter__ = AsyncMock(return_value=conn)
        acquire.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = acquire
        return pool

    def test_build_input_sends_only_public_data(self):
        inp = build_input(session(), [{"id": 1, "turn_no": 1, "speaker": "counselor", "content": "Halo"}])
        self.assertEqual(inp.change_target, "Membagi tanggung jawab")
        self.assertEqual(inp.initial_summary, "Ringkasan publik")
        self.assertNotIn("RAHASIA", repr(inp))

    @patch("api.evaluations.save_evaluation_results", new_callable=AsyncMock)
    @patch("api.evaluations.run_evaluation", new_callable=AsyncMock)
    @patch("api.evaluations.get_session_turns", new_callable=AsyncMock)
    def test_job_saves_results(self, get_turns, run_eval, save):
        get_turns.return_value = [{"id": 41, "turn_no": 1, "speaker": "counselor", "content": "Halo"}]
        run_eval.return_value = MagicMock()
        conn = self.create_mock_connection()
        self.run_async(run_evaluation_job(self.pool(conn), session(), 77))
        save.assert_awaited_once()
        self.assertEqual(save.call_args.args[3], {1: 41})

    @patch("api.evaluations.mark_evaluation_failed", new_callable=AsyncMock)
    @patch("api.evaluations.save_evaluation_results", new_callable=AsyncMock)
    @patch("api.evaluations.run_evaluation", new_callable=AsyncMock)
    @patch("api.evaluations.get_session_turns", new_callable=AsyncMock)
    def test_job_failure_marks_failed_with_message(self, get_turns, run_eval, save, mark_failed):
        from services.evaluation.miti_evaluator import EvaluationError

        get_turns.return_value = []
        run_eval.side_effect = EvaluationError("Semua item umpan balik tidak valid")
        conn = self.create_mock_connection()
        with self.assertLogs("safesesi.evaluation", level="ERROR"):
            self.run_async(run_evaluation_job(self.pool(conn), session(), 77))
        save.assert_not_awaited()
        self.assertEqual(mark_failed.call_args.args[1:], (77, "Semua item umpan balik tidak valid"))
