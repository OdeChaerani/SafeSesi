"""Pembatasan percobaan endpoint auth: login (IP + email, dan IP), activate, refresh."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException, Response

from api.auth import activate_account, login, refresh_session
from core import rate_limit
from core.rate_limit import RATE_LIMITED_MESSAGE, InMemoryRateLimitStore, client_ip
from core.security import hash_password, new_opaque_token
from schemas.auth import ActivateRequest, LoginRequest
from tests.base import BaseTestCase, make_request
from tests.test_auth import _settings

PASSWORD = "password123"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestRateLimit(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.clock = FakeClock()
        self.store = InMemoryRateLimitStore(max_keys=1000, clock=self.clock)
        rate_limit.set_store(self.store)
        self.addCleanup(rate_limit.set_store, None)
        self.settings = _settings(RATE_LIMIT_ENABLED=True)
        rules = patch.dict(
            rate_limit.RULES,
            {"login_pair": (3, 60), "login_ip": (50, 60), "activate": (2, 60), "refresh": (2, 60)},
        )
        rules.start()
        self.addCleanup(rules.stop)
        self.user = {
            "id": 10,
            "name": "Rani",
            "email": "rani@safesesi.ac.id",
            "role": "student",
            "password_hash": hash_password(PASSWORD),
            "activated_at": datetime.now(timezone.utc),
        }
        for target in ("api.auth.get_settings",):
            p = patch(target, return_value=self.settings)
            p.start()
            self.addCleanup(p.stop)
        p = patch("api.auth.get_user_for_login", side_effect=self._find_user)
        p.start()
        self.addCleanup(p.stop)
        for name in ("insert_refresh_token",):
            p = patch(f"api.auth.{name}")
            p.start()
            self.addCleanup(p.stop)

    async def _find_user(self, _conn, email):
        return self.user if email.strip().lower() == self.user["email"] else None

    def _login(self, email="rani@safesesi.ac.id", password="salah", ip="10.0.0.1"):
        return self.run_async(
            login(LoginRequest(email=email, password=password), Response(), request=make_request(ip), conn=self.conn)
        )

    def _expect(self, status, **kw):
        with self.assertRaises(HTTPException) as ctx:
            self._login(**kw)
        self.assertEqual(ctx.exception.status_code, status)
        return ctx.exception

    def test_blocked_after_max_failures_with_retry_after(self):
        for _ in range(3):
            self._expect(401)
        err = self._expect(429)
        self.assertEqual(err.detail, RATE_LIMITED_MESSAGE)
        self.assertEqual(err.headers["Retry-After"], "60")
        # Walau sekarang memakai password benar, kunci tetap berlaku sampai jendela habis.
        self._expect(429, password=PASSWORD)

    def test_window_expires_and_resets(self):
        for _ in range(3):
            self._expect(401)
        self._expect(429)
        self.clock.now += 61
        self._expect(401)  # boleh mencoba lagi

    def test_retry_after_counts_down(self):
        for _ in range(3):
            self._expect(401)
        self.clock.now += 20
        self.assertEqual(self._expect(429).headers["Retry-After"], "40")

    def test_different_ip_not_affected(self):
        for _ in range(3):
            self._expect(401, ip="10.0.0.1")
        self._expect(429, ip="10.0.0.1")
        res = self._login(password=PASSWORD, ip="10.0.0.2")  # pengguna sah dari IP lain
        self.assertIn("access_token", res)

    def test_success_resets_failure_count(self):
        for _ in range(2):
            self._expect(401)
        self.assertIn("access_token", self._login(password=PASSWORD))
        for _ in range(3):  # kembali dari nol, bukan 2 + 3
            self._expect(401)
        self._expect(429)

    def test_email_is_normalized(self):
        for email in ("rani@safesesi.ac.id", " RANI@safesesi.ac.id", "Rani@Safesesi.ac.id"):
            self._expect(401, email=email)
        self._expect(429, email="rani@safesesi.ac.id")

    def test_same_429_for_registered_and_unknown_email(self):
        for email in ("rani@safesesi.ac.id", "tidakada@safesesi.ac.id"):
            for _ in range(3):
                self._expect(401, email=email)
        known = self._expect(429, email="rani@safesesi.ac.id")
        unknown = self._expect(429, email="tidakada@safesesi.ac.id")
        self.assertEqual(known.detail, unknown.detail)
        self.assertEqual(known.headers, unknown.headers)

    def test_per_ip_layer_blocks_many_emails(self):
        with patch.dict(rate_limit.RULES, {"login_ip": (4, 60)}):
            for i in range(4):
                self._expect(401, email=f"orang{i}@safesesi.ac.id")
            self._expect(429, email="orang99@safesesi.ac.id")
            self._expect(401, email="orang99@safesesi.ac.id", ip="10.0.0.9")

    def test_disabled_never_blocks(self):
        with patch("api.auth.get_settings", return_value=_settings(RATE_LIMIT_ENABLED=False)):
            for _ in range(10):
                self._expect(401)

    def test_activate_limited_per_ip(self):
        payload = ActivateRequest(token=new_opaque_token(), password="x")  # ditolak aturan password (422)
        for _ in range(2):
            with self.assertRaises(HTTPException) as ctx:
                self.run_async(activate_account(payload, request=make_request(), conn=self.conn))
            self.assertEqual(ctx.exception.status_code, 422)
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(activate_account(payload, request=make_request(), conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)

    def test_refresh_limited_per_ip(self):
        def call(ip="10.0.0.1"):
            return self.run_async(refresh_session(Response(), request=make_request(ip), conn=self.conn, refresh_cookie=None))

        for _ in range(2):
            with self.assertRaises(HTTPException) as ctx:
                call()
            self.assertEqual(ctx.exception.status_code, 401)
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, 429)
        with self.assertRaises(HTTPException) as ctx:
            call("10.0.0.2")
        self.assertEqual(ctx.exception.status_code, 401)


class TestStoreAndClientIp(BaseTestCase):
    def test_sweep_removes_expired_keys(self):
        clock = FakeClock()
        store = InMemoryRateLimitStore(clock=clock)
        for i in range(5):
            store.acquire(f"k{i}", 3, 10)
        self.assertEqual(len(store._entries), 5)
        clock.now += 100
        store.acquire("baru", 3, 10)
        self.assertEqual(list(store._entries), ["baru"])

    def test_max_keys_evicts_least_recently_used(self):
        store = InMemoryRateLimitStore(max_keys=3, clock=FakeClock())
        for key in ("a", "b", "c", "d"):
            store.acquire(key, 3, 10)
        self.assertEqual(list(store._entries), ["b", "c", "d"])

    def test_forwarded_header_ignored_by_default(self):
        request = make_request("10.0.0.1", {"x-forwarded-for": "1.2.3.4"})
        self.assertEqual(client_ip(request, _settings()), "10.0.0.1")

    def test_forwarded_header_uses_last_entry_when_trusted(self):
        request = make_request("10.0.0.1", {"x-forwarded-for": "6.6.6.6, 1.2.3.4"})
        self.assertEqual(client_ip(request, _settings(TRUST_PROXY_HEADERS=True)), "1.2.3.4")

    def test_invalid_forwarded_header_falls_back_to_socket(self):
        request = make_request("10.0.0.1", {"x-forwarded-for": "bukan-ip"})
        self.assertEqual(client_ip(request, _settings(TRUST_PROXY_HEADERS=True)), "10.0.0.1")
