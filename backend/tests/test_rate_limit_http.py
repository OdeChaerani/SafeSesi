"""Pembatasan percobaan lewat HTTP sungguhan (FastAPI TestClient): status 429, Retry-After, dan IP klien."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import router
from api.deps import get_db
from core import rate_limit
from core.security import hash_password
from tests.base import BaseTestCase
from tests.test_auth import _settings

USER = {
    "id": 10,
    "name": "Rani",
    "email": "rani@safesesi.ac.id",
    "role": "student",
    "password_hash": hash_password("password123"),
    "activated_at": datetime.now(timezone.utc),
}


class TestRateLimitHttp(BaseTestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        conn = self.create_mock_connection()

        async def fake_db():
            yield conn

        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)
        rate_limit.set_store(None)
        self.addCleanup(rate_limit.set_store, None)

        async def find_user(_conn, email):
            return USER if email.strip().lower() == USER["email"] else None

        for p in (
            patch("api.auth.get_user_for_login", side_effect=find_user),
            patch.dict(rate_limit.RULES, {"login_pair": (3, 60)}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self._use(_settings(RATE_LIMIT_ENABLED=True))

    def _use(self, settings):
        p = patch("api.auth.get_settings", return_value=settings)
        p.start()
        self.addCleanup(p.stop)

    def _login(self, email="rani@safesesi.ac.id", headers=None):
        return self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": "salah"}, headers=headers or {}
        )

    def test_repeated_failures_end_in_429_with_retry_after(self):
        for _ in range(3):
            self.assertEqual(self._login().status_code, 401)
        res = self._login()
        self.assertEqual(res.status_code, 429)
        self.assertGreaterEqual(int(res.headers["Retry-After"]), 1)
        self.assertLessEqual(int(res.headers["Retry-After"]), 60)

    def test_forwarded_header_ignored_when_proxy_not_trusted(self):
        # Klien mengganti X-Forwarded-For tiap permintaan, tapi tetap satu IP sungguhan: tetap terkunci.
        for i in range(3):
            self.assertEqual(self._login(headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code, 401)
        self.assertEqual(self._login(headers={"X-Forwarded-For": "9.9.9.99"}).status_code, 429)

    def test_forwarded_header_last_entry_used_when_proxy_trusted(self):
        self._use(_settings(RATE_LIMIT_ENABLED=True, TRUST_PROXY_HEADERS=True))
        # Entri pertama dipalsukan klien, entri terakhir (dari proxy kita) tetap: dihitung sebagai satu klien.
        for i in range(3):
            self.assertEqual(self._login(headers={"X-Forwarded-For": f"6.6.6.{i}, 1.2.3.4"}).status_code, 401)
        self.assertEqual(self._login(headers={"X-Forwarded-For": "6.6.6.99, 1.2.3.4"}).status_code, 429)
        # Klien lain di belakang proxy yang sama tidak ikut terkunci.
        self.assertEqual(self._login(headers={"X-Forwarded-For": "1.2.3.5"}).status_code, 401)

    def test_429_identical_for_registered_and_unregistered_email(self):
        results = {}
        for email in ("rani@safesesi.ac.id", "tidakada@safesesi.ac.id"):
            for _ in range(3):
                self.assertEqual(self._login(email=email).status_code, 401)
            res = self._login(email=email)
            self.assertEqual(res.status_code, 429)
            results[email] = (res.json(), res.headers["Retry-After"])
        known, unknown = results.values()
        self.assertEqual(known, unknown)
