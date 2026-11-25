"""Pengujian Autentikasi: Login, Refresh Token Rotation, Logout, Aktivasi, Admin Create User, dan get_current_user."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
from fastapi import HTTPException, Response
import jwt

from api.admin import create_user
from api.auth import REFRESH_COOKIE, activate_account, change_password, login, logout, refresh_session
from api.deps import get_current_user, require_role
from core.config import Settings
from core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from schemas.auth import ActivateRequest, ChangePasswordRequest, CreateUserRequest, LoginRequest
from tests.base import BaseTestCase, make_request


def _settings(**kw: Any) -> Settings:
    base = {
        "JWT_SECRET": "test-secret-key-that-is-at-least-32-chars-long",
        "ACCESS_TOKEN_MINUTES": 15,
        "REFRESH_TOKEN_DAYS": 7,
        "ACTIVATION_TOKEN_HOURS": 72,
        "FRONTEND_URL": "http://localhost:5173",
        "APP_ENV": "development",
        "GEMINI_VALIDATE_ON_STARTUP": False,
        "RATE_LIMIT_ENABLED": False,  # pembatasan percobaan diuji terpisah di test_rate_limit.py
    }
    return Settings(_env_file=None, **{**base, **kw})


class TestLogin(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.settings = _settings()
        self.plain_pw = "password123"
        self.pw_hash = hash_password(self.plain_pw)
        self.user_data = {
            "id": 10,
            "name": "Rani Aulia",
            "email": "rani@safesesi.ac.id",
            "role": "student",
            "password_hash": self.pw_hash,
            "activated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

    @patch("api.auth.get_settings")
    @patch("api.auth.get_user_for_login")
    @patch("api.auth.insert_refresh_token", new_callable=AsyncMock)
    def test_login_success(self, mock_insert, mock_get_user, mock_get_settings):
        mock_get_settings.return_value = self.settings
        mock_get_user.return_value = self.user_data

        response = Response()
        payload = LoginRequest(email="rani@safesesi.ac.id", password=self.plain_pw)
        res = self.run_async(login(payload, response, request=make_request(), conn=self.conn))

        self.assertIn("access_token", res)
        self.assertEqual(res["token_type"], "bearer")
        self.assertEqual(res["user"]["email"], "rani@safesesi.ac.id")
        self.assertEqual(res["user"]["role"], "student")
        self.assertTrue(mock_insert.called)

        # Cookie header harus disetel
        cookie_header = response.headers.get("set-cookie", "")
        self.assertIn(REFRESH_COOKIE, cookie_header)
        self.assertIn("HttpOnly", cookie_header)

    @patch("api.auth.get_settings")
    @patch("api.auth.get_user_for_login")
    def test_login_wrong_password(self, mock_get_user, mock_get_settings):
        mock_get_settings.return_value = self.settings
        mock_get_user.return_value = self.user_data

        response = Response()
        payload = LoginRequest(email="rani@safesesi.ac.id", password="wrongpassword")
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(login(payload, response, request=make_request(), conn=self.conn))

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Email atau kata sandi salah.")

    @patch("api.auth.get_settings")
    @patch("api.auth.get_user_for_login")
    def test_login_user_not_found(self, mock_get_user, mock_get_settings):
        mock_get_settings.return_value = self.settings
        mock_get_user.return_value = None

        response = Response()
        payload = LoginRequest(email="nonexistent@safesesi.ac.id", password=self.plain_pw)
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(login(payload, response, request=make_request(), conn=self.conn))

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Email atau kata sandi salah.")

    @patch("api.auth.get_settings")
    @patch("api.auth.get_user_for_login")
    def test_login_unactivated_account(self, mock_get_user, mock_get_settings):
        unactivated = dict(self.user_data)
        unactivated["activated_at"] = None
        mock_get_settings.return_value = self.settings
        mock_get_user.return_value = unactivated

        response = Response()
        payload = LoginRequest(email="rani@safesesi.ac.id", password=self.plain_pw)
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(login(payload, response, request=make_request(), conn=self.conn))

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Email atau kata sandi salah.")


class TestRefresh(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.settings = _settings()
        self.raw_token = new_opaque_token()
        self.user_row = {
            "id": 10,
            "name": "Rani",
            "email": "rani@safesesi.ac.id",
            "role": "student",
            "deleted_at": None,
            "activated_at": datetime.now(timezone.utc),
        }
        self.token_row = {
            "id": 100,
            "user_id": 10,
            "family_id": 100,
            "token_hash": hash_token(self.raw_token),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "revoked_at": None,
            "replaced_by": None,
            "name": "Rani",
            "email": "rani@safesesi.ac.id",
            "role": "student",
            "activated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

    @patch("api.auth.get_settings")
    def test_refresh_missing_cookie(self, mock_get_settings):
        mock_get_settings.return_value = self.settings
        response = Response()
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(refresh_session(response, request=make_request(), conn=self.conn, refresh_cookie=None))
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("api.auth.get_settings")
    @patch("api.auth.get_refresh_token_for_update")
    @patch("api.auth.get_user_for_login")
    @patch("api.auth.mark_refresh_token_replaced", new_callable=AsyncMock)
    @patch("api.auth.insert_refresh_token", new_callable=AsyncMock)
    def test_refresh_success(self, mock_insert, mock_replace, mock_user, mock_row, mock_settings):
        mock_settings.return_value = self.settings
        mock_row.return_value = self.token_row
        mock_user.return_value = self.user_row

        response = Response()
        res = self.run_async(refresh_session(response, request=make_request(), conn=self.conn, refresh_cookie=self.raw_token))

        self.assertIn("access_token", res)
        self.assertEqual(res["user"]["email"], "rani@safesesi.ac.id")
        self.assertTrue(mock_replace.called)
        self.assertTrue(mock_insert.called)

        # Cookie baru harus disetel
        cookie_header = response.headers.get("set-cookie", "")
        self.assertIn(REFRESH_COOKIE, cookie_header)

    @patch("api.auth.get_settings")
    @patch("api.auth.get_refresh_token_for_update")
    def test_refresh_expired_token(self, mock_row, mock_settings):
        expired_row = dict(self.token_row)
        expired_row["expires_at"] = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_settings.return_value = self.settings
        mock_row.return_value = expired_row

        response = Response()
        res = self.run_async(refresh_session(response, request=make_request(), conn=self.conn, refresh_cookie=self.raw_token))
        self.assertEqual(res.status_code, 401)

    @patch("api.auth.get_settings")
    @patch("api.auth.get_refresh_token_for_update")
    @patch("api.auth.revoke_refresh_family", new_callable=AsyncMock)
    def test_refresh_token_reuse_revokes_entire_family(self, mock_revoke, mock_row, mock_settings):
        """Token yang sudah di-replace/revoked tapi dipakai lagi dianggap dicuri: seluruh family dicabut."""
        reused_row = dict(self.token_row)
        reused_row["replaced_by"] = 101  # sudah pernah dipakai sebelumnya
        reused_row["revoked_at"] = datetime.now(timezone.utc)
        mock_settings.return_value = self.settings
        mock_row.return_value = reused_row

        response = Response()
        res = self.run_async(refresh_session(response, request=make_request(), conn=self.conn, refresh_cookie=self.raw_token))

        self.assertEqual(res.status_code, 401)
        # Pastikan revoke_refresh_family dipanggil dengan family_id token yang bersangkutan
        mock_revoke.assert_called_once_with(self.conn, self.token_row["family_id"])


class TestLogout(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.settings = _settings()

    @patch("api.auth.get_settings")
    @patch("api.auth.get_refresh_token_for_update")
    @patch("api.auth.revoke_refresh_family", new_callable=AsyncMock)
    def test_logout_with_valid_cookie(self, mock_revoke, mock_row, mock_settings):
        mock_settings.return_value = self.settings
        mock_row.return_value = {"family_id": 88}

        response = Response()
        res = self.run_async(logout(response, conn=self.conn, refresh_cookie="token-xyz"))

        self.assertEqual(res.status_code, 204)
        mock_revoke.assert_called_once_with(self.conn, 88)
        # Cookie dihapus (max-age 0 atau expires masa lalu)
        self.assertIn(f'{REFRESH_COOKIE}=""', response.headers.get("set-cookie", ""))


class TestActivation(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.token = new_opaque_token()
        self.user_data = {
            "id": 15,
            "name": "Budi",
            "email": "budi@safesesi.ac.id",
            "activation_token_expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
            "activation_token_purpose": "activation",
            "activated_at": None,
        }

    def test_activate_password_too_short(self):
        payload = ActivateRequest(token=self.token, password="short")
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(activate_account(payload, request=make_request(), conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 422)

    @patch("api.auth.get_user_by_activation_hash")
    @patch("api.auth.activate_user", new_callable=AsyncMock)
    def test_activate_success(self, mock_activate, mock_user):
        mock_user.return_value = self.user_data

        payload = ActivateRequest(token=self.token, password="validpassword123")
        res = self.run_async(activate_account(payload, request=make_request(), conn=self.conn))

        self.assertIn("message", res)
        self.assertIn("berhasil diaktifkan", res["message"])
        self.assertTrue(mock_activate.called)

    @patch("api.auth.get_user_by_activation_hash")
    def test_activate_token_not_found_or_already_used(self, mock_user):
        mock_user.return_value = None

        payload = ActivateRequest(token=self.token, password="validpassword123")
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(activate_account(payload, request=make_request(), conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("tidak valid atau sudah dipakai", ctx.exception.detail)

    @patch("api.auth.get_user_by_activation_hash")
    def test_activate_expired_token(self, mock_user):
        expired = dict(self.user_data)
        expired["activation_token_expires_at"] = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_user.return_value = expired

        payload = ActivateRequest(token=self.token, password="validpassword123")
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(activate_account(payload, request=make_request(), conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("kedaluwarsa", ctx.exception.detail)


class TestAdminUsers(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.admin = {"id": 1, "name": "Admin", "role": "admin"}
        self.settings = _settings()

    @patch("api.admin.insert_profile", new_callable=AsyncMock)
    @patch("api.admin.get_settings")
    @patch("api.admin.create_user_with_activation", new_callable=AsyncMock)
    def test_admin_create_user_success(self, mock_create, mock_settings, _mock_profile):
        mock_settings.return_value = self.settings
        mock_create.return_value = {"id": 20, "name": "Mhs Baru", "email": "mhs@safesesi.ac.id", "role": "student"}

        payload = CreateUserRequest(name="Mhs Baru", email="mhs@safesesi.ac.id", role="student", npm="DEV-1")
        res = self.run_async(create_user(payload, admin=self.admin, conn=self.conn))

        self.assertIn("activation_url", res)
        self.assertIn("#token=", res["activation_url"])
        self.assertEqual(res["user"]["email"], "mhs@safesesi.ac.id")

    @patch("api.admin.get_settings")
    @patch("api.admin.create_user_with_activation", new_callable=AsyncMock)
    def test_admin_create_user_duplicate_email(self, mock_create, mock_settings):
        mock_settings.return_value = self.settings
        mock_create.side_effect = asyncpg.UniqueViolationError()

        payload = CreateUserRequest(name="Mhs", email="duplicate@safesesi.ac.id", role="student", npm="DEV-1")
        res = self.run_async(create_user(payload, admin=self.admin, conn=self.conn))
        self.assertEqual(res.status_code, 409)


class TestAuthDependencies(BaseTestCase):
    def setUp(self):
        self.settings = _settings()
        self.user = {"id": 10, "name": "Rani", "email": "r@s.ac.id", "role": "student", "activated_at": datetime.now(timezone.utc)}

    def test_require_role_matching(self):
        checker = require_role("admin", "lecturer")
        res = self.run_async(checker(user={"id": 1, "role": "admin"}))
        self.assertEqual(res["role"], "admin")

    def test_require_role_mismatch(self):
        checker = require_role("admin")
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(checker(user={"id": 10, "role": "student"}))
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("api.deps.get_settings")
    def test_get_current_user_no_credentials(self, mock_settings):
        mock_settings.return_value = self.settings
        mock_request = MagicMock()
        mock_request.app.state.db_pool = None

        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_current_user(mock_request, authorization=None, x_dev_user_id=None))
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("api.deps.get_settings")
    def test_get_current_user_dev_header_rejected_in_production(self, mock_settings):
        mock_settings.return_value = _settings(APP_ENV="production")
        mock_request = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_current_user(mock_request, authorization=None, x_dev_user_id=10))
        self.assertEqual(ctx.exception.status_code, 401)


class TestChangePassword(BaseTestCase):
    OLD, NEW = "password-lama-1", "password-baru-2"

    def setUp(self):
        self.conn = self.create_mock_connection()
        self.settings = _settings()
        self.user = {"id": 10, "name": "Rani", "email": "rani@safesesi.ac.id", "role": "student"}
        self.calls = MagicMock()
        patches = {
            "get_password_hash_for_update": AsyncMock(return_value=hash_password(self.OLD)),
            "set_password_hash": AsyncMock(),
            "revoke_all_refresh_families": AsyncMock(),
            "insert_refresh_token": AsyncMock(),
        }
        for name, mock in patches.items():
            self.calls.attach_mock(mock, name)
            p = patch(f"api.auth.{name}", mock)
            p.start()
            self.addCleanup(p.stop)
        p = patch("api.auth.get_settings", return_value=self.settings)
        p.start()
        self.addCleanup(p.stop)

    def _change(self, current=None, new=None, response=None):
        payload = ChangePasswordRequest(current_password=current or self.OLD, new_password=new or self.NEW)
        return self.run_async(
            change_password(payload, response or Response(), request=make_request(), user=self.user, conn=self.conn)
        )

    def _rejected(self, status, **kw):
        with self.assertRaises(HTTPException) as ctx:
            self._change(**kw)
        self.assertEqual(ctx.exception.status_code, status)
        self.calls.set_password_hash.assert_not_called()
        self.calls.revoke_all_refresh_families.assert_not_called()
        return ctx.exception

    def test_wrong_current_password_rejected_with_400_not_401(self):
        err = self._rejected(400, current="bukan-yang-lama")
        self.assertEqual(err.detail, "Kata sandi saat ini salah.")

    def test_new_password_same_as_current_rejected(self):
        self._rejected(422, new=self.OLD)

    def test_new_password_too_short_rejected(self):
        self._rejected(422, new="pendek")

    def test_success_revokes_all_families_then_issues_new_session(self):
        response = Response()
        res = self._change(response=response)

        self.assertIn("access_token", res)
        self.assertEqual(res["user"]["email"], "rani@safesesi.ac.id")
        self.assertIn(REFRESH_COOKIE, response.headers.get("set-cookie", ""))
        # Hash baru benar-benar argon2 dari kata sandi baru, bukan teks biasa.
        new_hash = self.calls.set_password_hash.call_args.args[2]
        self.assertTrue(verify_password(self.NEW, new_hash))
        # Urutan: cabut semua family DULU, baru terbitkan token perangkat ini (kalau terbalik, sesinya ikut tercabut).
        names = [c[0] for c in self.calls.mock_calls]
        self.assertLess(names.index("revoke_all_refresh_families"), names.index("insert_refresh_token"))
        self.calls.revoke_all_refresh_families.assert_called_once_with(self.conn, 10)

    def test_old_refresh_token_cannot_refresh_after_revocation(self):
        """Setelah dicabut, token lama (revoked_at terisi) ditolak /auth/refresh dan cookie-nya dihapus."""
        raw = new_opaque_token()
        row = {
            "id": 100, "user_id": 10, "family_id": 100, "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "revoked_at": datetime.now(timezone.utc), "replaced_by": None, "name": "Rani",
            "email": "rani@safesesi.ac.id", "role": "student", "activated_at": datetime.now(timezone.utc), "deleted_at": None,
        }
        with patch("api.auth.get_refresh_token_for_update", AsyncMock(return_value=row)), patch(
            "api.auth.revoke_refresh_family", AsyncMock()
        ):
            res = self.run_async(refresh_session(Response(), request=make_request(), conn=self.conn, refresh_cookie=raw))
        self.assertEqual(res.status_code, 401)

    def test_failed_attempts_are_rate_limited_and_success_resets(self):
        from core import rate_limit

        rate_limit.set_store(None)
        self.addCleanup(rate_limit.set_store, None)
        settings = _settings(RATE_LIMIT_ENABLED=True)
        with patch("api.auth.get_settings", return_value=settings), patch.dict(
            rate_limit.RULES, {"change_password": (2, 60)}
        ):
            self._rejected(400, current="salah-1")
            self._change()  # berhasil: hitungan direset
            self.calls.reset_mock()
            self._rejected(400, current="salah-1")
            self._rejected(400, current="salah-2")
            self._rejected(429, current=self.OLD)  # terkunci walau kata sandi benar


class TestChangePasswordRoute(BaseTestCase):
    def test_requires_login(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.auth import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.state.db_pool = None
        res = TestClient(app).post(
            "/api/v1/auth/change-password", json={"current_password": "x", "new_password": "yyyyyyyy"}
        )
        self.assertEqual(res.status_code, 401)
