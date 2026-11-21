"""Password (argon2id), access token JWT, get_current_user dengan Bearer, dan penjaga konfigurasi auth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from fastapi import HTTPException

from api.deps import get_current_user
from core.config import DEV_JWT_SECRET, Settings
from core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    password_problem,
    verify_password,
)
from tests.base import BaseTestCase, MockTx

SECRET = "test-secret-key-that-is-at-least-32-chars-long"
USER = {"id": 10, "name": "Rani", "email": "r@s.ac.id", "role": "student"}


def settings(**kw: Any) -> Settings:
    base = {"JWT_SECRET": SECRET, "APP_ENV": "development", "GEMINI_VALIDATE_ON_STARTUP": False}
    return Settings(_env_file=None, **{**base, **kw})


class TestPasswords(BaseTestCase):
    def test_hash_is_argon2id_and_verifies(self):
        hashed = hash_password("rahasia-banget")
        self.assertTrue(hashed.startswith("$argon2id$"))
        self.assertNotIn("rahasia", hashed)
        self.assertTrue(verify_password("rahasia-banget", hashed))
        self.assertFalse(verify_password("salah", hashed))

    def test_missing_or_garbage_hash_never_verifies(self):
        self.assertFalse(verify_password("apa saja", None))  # akun belum aktif
        self.assertFalse(verify_password("apa saja", "bukan-hash"))
        # password milik hash pembanding internal tetap tidak boleh lolos untuk akun tanpa hash
        self.assertFalse(verify_password("dummy-password-untuk-waktu-konstan", None))

    def test_password_rules(self):
        self.assertIsNotNone(password_problem("pendek"))
        self.assertIsNotNone(password_problem("x" * 129))
        self.assertIsNone(password_problem("12345678"))


class TestAccessToken(BaseTestCase):
    def setUp(self):
        self.settings = settings()

    def test_round_trip(self):
        payload = decode_access_token(create_access_token(USER, self.settings), self.settings)
        self.assertEqual((payload["sub"], payload["role"], payload["type"]), ("10", "student", "access"))

    def test_expired_token_rejected(self):
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        self.assertIsNone(decode_access_token(create_access_token(USER, self.settings, now=old), self.settings))

    def test_tampered_or_foreign_token_rejected(self):
        token = create_access_token(USER, self.settings)
        self.assertIsNone(decode_access_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB"), self.settings))
        self.assertIsNone(decode_access_token(token, settings(JWT_SECRET="secret-lain-yang-juga-lebih-dari-32-karakter")))
        self.assertIsNone(decode_access_token("bukan.jwt.sama-sekali", self.settings))

    def test_wrong_type_or_algorithm_rejected(self):
        exp = datetime.now(timezone.utc) + timedelta(minutes=5)
        refresh_like = jwt.encode({"sub": "10", "type": "refresh", "exp": exp}, SECRET, algorithm=JWT_ALGORITHM)
        self.assertIsNone(decode_access_token(refresh_like, self.settings))
        unsigned = jwt.encode({"sub": "10", "type": "access", "exp": exp}, None, algorithm="none")
        self.assertIsNone(decode_access_token(unsigned, self.settings))  # "alg: none" tidak diterima


class TestCurrentUserCredentials(BaseTestCase):
    def setUp(self):
        self.settings = settings()
        self.db_user = {**USER, "activated_at": datetime.now(timezone.utc)}
        self.request = MagicMock()
        self.request.app.state.db_pool.acquire = MagicMock(side_effect=lambda: MockTx())

    def call(self, authorization=None, dev_id=None, db_user: Any = "default", cfg: Settings | None = None):
        db_user = self.db_user if db_user == "default" else db_user
        with patch("api.deps.get_settings", return_value=cfg or self.settings), \
             patch("api.deps.get_user_by_id", AsyncMock(return_value=db_user)):
            return self.run_async(get_current_user(self.request, authorization=authorization, x_dev_user_id=dev_id))

    def bearer(self, **kw: Any) -> str:
        return f"Bearer {create_access_token(USER, self.settings, **kw)}"

    def status_of(self, **kw: Any) -> int:
        with self.assertRaises(HTTPException) as ctx:
            self.call(**kw)
        return ctx.exception.status_code

    def test_valid_bearer(self):
        self.assertEqual(self.call(authorization=self.bearer())["id"], 10)

    def test_invalid_bearer_variants_are_401(self):
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        self.assertEqual(self.status_of(authorization=self.bearer(now=old)), 401)
        self.assertEqual(self.status_of(authorization="Bearer sampah"), 401)
        self.assertEqual(self.status_of(authorization=self.bearer().replace("Bearer", "Basic")), 401)

    def test_deleted_or_unactivated_account_is_401(self):
        self.assertEqual(self.status_of(authorization=self.bearer(), db_user=None), 401)
        self.assertEqual(self.status_of(authorization=self.bearer(), db_user={**self.db_user, "activated_at": None}), 401)

    def test_dev_header_only_in_development(self):
        self.assertEqual(self.call(dev_id=10)["id"], 10)
        self.assertEqual(self.status_of(dev_id=10, cfg=settings(APP_ENV="production", JWT_SECRET=SECRET)), 401)

    def test_bearer_wins_over_dev_header(self):
        # Token tidak sah tidak boleh "diselamatkan" oleh header dev.
        self.assertEqual(self.status_of(authorization="Bearer sampah", dev_id=10), 401)


class TestAuthSettingsGuards(BaseTestCase):
    def test_development_may_use_default_secret(self):
        settings(JWT_SECRET=DEV_JWT_SECRET).validate_auth_settings()

    def test_production_rejects_default_or_short_secret(self):
        for secret in (DEV_JWT_SECRET, "pendek"):
            with self.assertRaises(ValueError):
                settings(APP_ENV="production", JWT_SECRET=secret).validate_auth_settings()
        settings(APP_ENV="production", JWT_SECRET=SECRET).validate_auth_settings()

    def test_wildcard_cors_origin_rejected(self):
        with self.assertRaises(ValueError):
            settings(CORS_ORIGINS="*")
        with self.assertRaises(ValueError):
            settings(CORS_ORIGINS='["https://safesesi.ac.id", "*"]')
