"""Atur ulang kata sandi oleh admin (endpoint, penyelesaian lewat /auth/activate) dan skrip pemulihan darurat."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api import admin
from api.auth import activate_account
from api.deps import get_current_user, get_db
from core.security import hash_token, new_opaque_token, verify_password
from repositories.audit import log_admin_action
from repositories.auth import issue_reset_token
from schemas.auth import ActivateRequest
from scripts.reset_user_password import ResetError, reset_user_password
from tests.base import BaseTestCase, make_request
from tests.test_auth import _settings

ADMIN = {"id": 1, "name": "Admin", "email": "a@s.ac.id", "role": "admin"}


class TestAdminResetEndpoint(BaseTestCase):
    def setUp(self):
        self.settings = _settings(RESET_TOKEN_MINUTES=30)
        self.current = dict(ADMIN)
        app = FastAPI()
        app.include_router(admin.router, prefix="/api/v1")
        conn = self.create_mock_connection()

        async def fake_db():
            yield conn

        app.dependency_overrides[get_db] = fake_db
        app.dependency_overrides[get_current_user] = lambda: self.current
        self.client = TestClient(app)
        self.target = {"id": 20, "role": "student", "activated_at": datetime.now(timezone.utc)}

        async def find_target(*_):
            return self.target

        self.issue = AsyncMock(return_value={"id": 20, "name": "Mhs", "email": "m@s.ac.id", "role": "student"})
        self.audit = AsyncMock()
        for p in (
            patch("api.admin.get_settings", return_value=self.settings),
            patch("api.admin.get_user_for_admin_reset", find_target),
            patch("api.admin.issue_reset_token", self.issue),
            patch("api.admin.log_admin_action", self.audit),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _reset(self, user_id=20):
        return self.client.post(f"/api/v1/admin/users/{user_id}/reset-password")

    def test_admin_gets_link_once_and_only_hash_is_stored(self):
        res = self._reset()
        self.assertEqual(res.status_code, 200)
        body = res.json()
        token = body["reset_url"].split("#token=")[1]
        self.assertTrue(body["reset_url"].startswith("http://localhost:5173/reset-password#"))
        self.assertNotIn("password_hash", body["user"])
        _conn, user_id, stored_hash, expires = self.issue.call_args.args
        self.assertEqual((user_id, stored_hash), (20, hash_token(token)))
        self.assertNotEqual(stored_hash, token)
        self.assertAlmostEqual((expires - datetime.now(timezone.utc)).total_seconds(), 30 * 60, delta=5)

    def _assert_nothing_issued_or_logged(self):
        self.issue.assert_not_called()
        self.audit.assert_not_called()

    def test_non_admin_forbidden(self):
        for role in ("student", "lecturer"):
            self.current = {"id": 5, "name": "X", "email": "x@s.ac.id", "role": role}
            self.assertEqual(self._reset().status_code, 403)
        self._assert_nothing_issued_or_logged()

    def test_admin_cannot_reset_self(self):
        self.assertEqual(self._reset(user_id=ADMIN["id"]).status_code, 400)
        self._assert_nothing_issued_or_logged()

    def test_unknown_account_404(self):
        self.target = None
        self.assertEqual(self._reset().status_code, 404)
        self._assert_nothing_issued_or_logged()

    def test_not_yet_activated_account_rejected(self):
        self.target = {"id": 20, "role": "student", "activated_at": None}
        self.assertEqual(self._reset().status_code, 409)
        self._assert_nothing_issued_or_logged()

    def test_reset_of_another_admin_forbidden(self):
        self.target = {"id": 21, "role": "admin", "activated_at": datetime.now(timezone.utc)}
        res = self._reset(user_id=21)
        self.assertEqual(res.status_code, 403)
        self.assertIn("skrip pemulihan", res.json()["detail"])
        self._assert_nothing_issued_or_logged()

    def test_successful_reset_writes_exactly_one_audit_row(self):
        self._reset()
        self.assertEqual(self.audit.call_count, 1)
        _conn, actor_id, target_id, action, ip = self.audit.call_args.args
        self.assertEqual((actor_id, target_id, action, ip), (1, 20, "issue_reset_token", "testclient"))

    def test_audit_row_never_contains_token_hash_or_link(self):
        body = self._reset().json()
        token = body["reset_url"].split("#token=")[1]
        logged = " ".join(str(a) for a in self.audit.call_args.args[1:])
        for secret in (token, hash_token(token), body["reset_url"]):
            self.assertNotIn(secret, logged)

    def test_no_audit_row_when_token_could_not_be_issued(self):
        self.issue.return_value = None
        self.assertEqual(self._reset().status_code, 404)
        self.audit.assert_not_called()


class TestAuditRepository(BaseTestCase):
    def test_insert_has_no_token_columns(self):
        conn = self.create_mock_connection()
        self.run_async(log_admin_action(conn, 1, 20, "issue_reset_token", "10.0.0.1"))
        sql, *args = conn.execute.call_args.args
        self.assertEqual(
            sql, "INSERT INTO admin_audit_log (actor_id, target_user_id, action, ip) VALUES ($1, $2, $3, $4)"
        )
        self.assertEqual(args, [1, 20, "issue_reset_token", "10.0.0.1"])


class TestIssueResetTokenSql(BaseTestCase):
    def test_overwrites_the_single_token_slot_for_active_accounts_only(self):
        """Satu slot token per pengguna: menerbitkan yang baru menimpa (membatalkan) yang lama."""
        conn = self.create_mock_connection()
        conn.fetchrow.return_value = {"id": 20, "name": "M", "email": "m@s.ac.id", "role": "student"}
        expires = datetime.now(timezone.utc)
        self.run_async(issue_reset_token(conn, 20, "hash-baru", expires))
        sql, *args = conn.fetchrow.call_args.args
        self.assertIn("SET activation_token_hash = $2", sql)
        self.assertIn("activation_token_purpose = 'reset'", sql)
        self.assertIn("activated_at IS NOT NULL", sql)
        self.assertIn("deleted_at IS NULL", sql)
        self.assertEqual(args, [20, "hash-baru", expires])


class TestResetCompletion(BaseTestCase):
    """Penyelesaian lewat /auth/activate yang sama dengan aktivasi."""

    def setUp(self):
        self.conn = self.create_mock_connection()
        self.token = new_opaque_token()
        self.row = {
            "id": 20,
            "activation_token_expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            "activation_token_purpose": "reset",
            "activated_at": datetime.now(timezone.utc),
        }
        self.activate_user = AsyncMock()
        self.revoke_all = AsyncMock()
        self.lookup = AsyncMock(return_value=self.row)
        for p in (
            patch("api.auth.get_settings", return_value=_settings()),
            patch("api.auth.get_user_by_activation_hash", self.lookup),
            patch("api.auth.activate_user", self.activate_user),
            patch("api.auth.revoke_all_refresh_families", self.revoke_all),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _complete(self):
        payload = ActivateRequest(token=self.token, password="kata-sandi-baru")
        return self.run_async(activate_account(payload, request=make_request(), conn=self.conn))

    def _rejected(self, detail_part):
        with self.assertRaises(HTTPException) as ctx:
            self._complete()
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn(detail_part, ctx.exception.detail)
        self.activate_user.assert_not_called()
        self.revoke_all.assert_not_called()

    def test_reset_saves_hash_clears_token_and_revokes_all_families(self):
        res = self._complete()
        self.assertIn("diatur ulang", res["message"])
        self.lookup.assert_called_once_with(self.conn, hash_token(self.token))
        _conn, user_id, new_hash = self.activate_user.call_args.args
        self.assertEqual(user_id, 20)
        self.assertTrue(verify_password("kata-sandi-baru", new_hash))
        self.revoke_all.assert_called_once_with(self.conn, 20)

    def test_token_cannot_be_used_twice(self):
        self._complete()
        self.lookup.return_value = None  # hash dihapus oleh activate_user pada pemakaian pertama
        with self.assertRaises(HTTPException) as ctx:
            self._complete()
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(self.activate_user.call_count, 1)

    def test_expired_reset_token_rejected(self):
        self.row["activation_token_expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self._rejected("kedaluwarsa")

    def test_reset_token_rejected_for_unactivated_account(self):
        self.row["activated_at"] = None
        self._rejected("tidak valid")

    def test_activation_token_rejected_for_activated_account(self):
        self.row["activation_token_purpose"] = "activation"
        self._rejected("tidak valid")

    def test_normal_activation_does_not_revoke_sessions(self):
        self.row.update(activation_token_purpose="activation", activated_at=None)
        res = self._complete()
        self.assertIn("diaktifkan", res["message"])
        self.revoke_all.assert_not_called()


class TestEmergencyScript(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.revoke_all = AsyncMock()
        p = patch("scripts.reset_user_password.revoke_all_refresh_families", self.revoke_all)
        p.start()
        self.addCleanup(p.stop)

    def _run(self, *, fetchrow=None, fetchval=None, password="kata-sandi-baru", **kw):
        self.conn.fetchrow = AsyncMock(side_effect=fetchrow if isinstance(fetchrow, list) else [fetchrow])
        self.conn.fetchval = AsyncMock(return_value=fetchval)
        self.conn.execute = AsyncMock()
        return self.run_async(reset_user_password(self.conn, "Admin@Kampus.ac.id", password, **kw))

    def test_resets_existing_account_and_revokes_all_sessions(self):
        res = self._run(fetchrow={"id": 7, "email": "admin@kampus.ac.id"})
        self.assertEqual(res, {"email": "admin@kampus.ac.id", "created": False})
        sql, user_id, new_hash = self.conn.execute.call_args.args
        self.assertIn("COALESCE(activated_at, now())", sql)
        self.assertIn("activation_token_hash = NULL", sql)
        self.assertEqual(user_id, 7)
        self.assertTrue(new_hash.startswith("$argon2id$") and verify_password("kata-sandi-baru", new_hash))
        self.revoke_all.assert_called_once_with(self.conn, 7)

    def test_unknown_account_refused(self):
        with self.assertRaisesRegex(ResetError, "tidak ditemukan"):
            self._run(fetchrow=None, fetchval=None)
        self.conn.execute.assert_not_called()

    def test_deleted_account_refused(self):
        with self.assertRaisesRegex(ResetError, "sudah dihapus"):
            self._run(fetchrow=None, fetchval=1, create_admin=True, name="Admin")
        self.conn.execute.assert_not_called()
        self.revoke_all.assert_not_called()

    def test_create_admin_inserts_activated_admin(self):
        res = self._run(fetchrow=[None, {"email": "admin@kampus.ac.id"}], create_admin=True, name=" Nama Admin ")
        self.assertEqual(res, {"email": "admin@kampus.ac.id", "created": True})
        sql, name, email, pw_hash = self.conn.fetchrow.call_args.args
        self.assertIn("'admin'::user_role", sql)
        self.assertEqual((name, email), ("Nama Admin", "Admin@Kampus.ac.id"))
        self.assertTrue(verify_password("kata-sandi-baru", pw_hash))

    def test_create_admin_needs_name_and_refuses_existing_account(self):
        with self.assertRaisesRegex(ResetError, "--name"):
            self._run(fetchrow=None, create_admin=True)
        with self.assertRaisesRegex(ResetError, "sudah ada"):
            self._run(fetchrow={"id": 7, "email": "admin@kampus.ac.id"}, create_admin=True, name="X")

    def test_weak_password_refused_before_touching_database(self):
        with self.assertRaisesRegex(ResetError, "minimal 8"):
            self._run(fetchrow=None, password="pendek")
        self.conn.fetchrow.assert_not_called()
