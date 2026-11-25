"""Daftar pengguna admin dan kirim ulang tautan aktivasi."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import admin, auth
from api.deps import get_current_user, get_db
from core.security import hash_token
from repositories.users import ACCOUNT_STATUS_SQL
from tests.base import BaseTestCase, MockTx
from tests.test_auth import _settings

ADMIN = {"id": 1, "name": "Admin", "email": "a@s.ac.id", "role": "admin"}


def _client(testcase, db, current):
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")

    async def fake_db():
        yield db

    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_current_user] = lambda: current()
    for target in ("api.admin.get_settings", "api.auth.get_settings"):
        p = patch(target, return_value=_settings())
        p.start()
        testcase.addCleanup(p.stop)
    return TestClient(app)


class TestListUsers(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()
        self.conn.fetchval.return_value = 60
        # Baris sengaja memuat kolom rahasia: skema respons harus membuangnya.
        self.conn.fetch.return_value = [
            {
                "id": i, "name": f"U{i}", "email": f"u{i}@s.ac.id", "role": "student", "npm": f"DEV{i}",
                "asal_institusi": None, "nip": None, "status": "menunggu", "classes": ["Kelas A"],
                "password_hash": "$argon2id$rahasia", "activation_token_hash": "hash-rahasia",
            }
            for i in range(50)
        ]
        self.current = dict(ADMIN)
        self.client = _client(self, self.conn, lambda: self.current)

    def _list(self, query=""):
        return self.client.get(f"/api/v1/admin/users{query}")

    def test_non_admin_forbidden(self):
        for role in ("student", "lecturer"):
            self.current = {**ADMIN, "id": 5, "role": role}
            self.assertEqual(self._list().status_code, 403)
        self.conn.fetch.assert_not_called()

    def test_response_has_explicit_columns_only(self):
        res = self._list()
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(
            set(res.json()["items"][0]),
            {"id", "name", "email", "role", "npm", "asal_institusi", "nip", "status", "classes"},
        )
        for secret in ("password", "argon2", "token", "hash-rahasia"):
            self.assertNotIn(secret, res.text)

    def test_constant_number_of_queries(self):
        self._list("?page_size=100")
        self.assertEqual(self.conn.fetchval.await_count + self.conn.fetch.await_count, 2)
        self.conn.fetchrow.assert_not_called()
        self.conn.execute.assert_not_called()

    def test_filters_search_and_pagination_reach_the_query(self):
        res = self._list("?page=3&page_size=25&q=%20Rani%20&role=lecturer&status=kedaluwarsa&class_id=7")
        self.assertEqual((res.json()["total"], res.json()["page"], res.json()["page_size"]), (60, 3, 25))
        sql, *args = self.conn.fetch.call_args.args
        self.assertEqual(args, ["%Rani%", "lecturer", 7, "kedaluwarsa", 25, 50])
        self.assertEqual(list(self.conn.fetchval.call_args.args[1:]), ["%Rani%", "lecturer", 7, "kedaluwarsa"])
        for part in ("u.name ILIKE", "u.email ILIKE", "s.npm ILIKE", "l.nip ILIKE", "u.deleted_at IS NULL"):
            self.assertIn(part, sql)

    def test_like_wildcards_are_literal_and_blank_search_ignored(self):
        self._list("?q=50%25_x")
        self.assertEqual(self.conn.fetch.call_args.args[1], "%50\\%\\_x%")
        self._list("?q=%20%20")
        self.assertIsNone(self.conn.fetch.call_args.args[1])

    def test_invalid_parameters_rejected(self):
        for query in ("?page_size=101", "?page=0", "?status=lain", "?role=root", f"?q={'a' * 101}"):
            self.assertEqual(self._list(query).status_code, 422, query)
        self.conn.fetch.assert_not_called()


class TestAccountStatus(BaseTestCase):
    """Ekspresi status asli dijalankan di SQLite agar ketiga kondisinya benar-benar dievaluasi."""

    def test_three_conditions(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.create_function("now", 0, lambda: "2026-11-26T12:00:00")
        db.execute("CREATE TABLE u (id INTEGER, password_hash TEXT, activation_token_expires_at TEXT)")
        db.executemany(
            "INSERT INTO u VALUES (?, ?, ?)",
            [
                (1, "hash", None),
                (2, "hash", "2026-01-01T00:00:00"),  # sudah punya password: token lama tidak berpengaruh
                (3, None, "2026-11-27T00:00:00"),
                (4, None, "2026-11-25T00:00:00"),
                (5, None, None),
            ],
        )
        rows = db.execute(f"SELECT {ACCOUNT_STATUS_SQL} FROM u u ORDER BY u.id").fetchall()
        self.assertEqual([r[0] for r in rows], ["aktif", "aktif", "menunggu", "kedaluwarsa", "kedaluwarsa"])


class FakeAccounts:
    """Satu slot token per akun, seperti kolom activation_token_* di tabel users."""

    def __init__(self):
        self.audit: list[tuple] = []
        past = datetime.now(timezone.utc) - timedelta(days=1)
        self.users = {
            20: {"role": "student", "activated_at": None, "hash": "hash-lama", "expires": past},
            21: {"role": "lecturer", "activated_at": past, "hash": None, "expires": None},
            22: {"role": "admin", "activated_at": None, "hash": None, "expires": None},
        }

    def transaction(self):
        return MockTx()

    async def fetchrow(self, query, key, *args):
        if "UPDATE users" in query:
            user = self.users[key]
            user["hash"], user["expires"] = args
            return {"id": key, "name": "U", "email": "u@s.ac.id", "role": user["role"]}
        if "activation_token_hash = $1" in query:
            for user_id, user in self.users.items():
                if user["hash"] == key:
                    return {
                        "id": user_id, "activation_token_expires_at": user["expires"],
                        "activation_token_purpose": "activation", "activated_at": user["activated_at"],
                    }
            return None
        user = self.users.get(key)
        return {"id": key, "role": user["role"], "activated_at": user["activated_at"]} if user else None

    async def execute(self, query, *args):
        if "INTO admin_audit_log" in query:
            self.audit.append(args)


class TestResendActivation(BaseTestCase):
    def setUp(self):
        self.db = FakeAccounts()
        self.current = dict(ADMIN)
        self.client = _client(self, self.db, lambda: self.current)

    def _resend(self, user_id=20):
        return self.client.post(f"/api/v1/admin/users/{user_id}/resend-activation")

    def _activate(self, token):
        return self.client.post("/api/v1/auth/activate", json={"token": token, "password": "kata-sandi-baru"})

    def test_new_link_returned_once_and_only_hash_stored(self):
        res = self._resend()
        self.assertEqual(res.status_code, 200, res.text)
        token = res.json()["activation_url"].split("#token=")[1]
        self.assertIn("/aktivasi#token=", res.json()["activation_url"])
        self.assertEqual(self.db.users[20]["hash"], hash_token(token))
        hours = (self.db.users[20]["expires"] - datetime.now(timezone.utc)).total_seconds() / 3600
        self.assertAlmostEqual(hours, _settings().ACTIVATION_TOKEN_HOURS, delta=0.1)

    def test_previous_link_stops_working(self):
        first = self._resend().json()["activation_url"].split("#token=")[1]
        second = self._resend().json()["activation_url"].split("#token=")[1]
        self.assertEqual(self._activate(first).status_code, 400)
        self.assertEqual(self._activate(second).status_code, 200)

    def test_active_account_rejected_409(self):
        res = self._resend(21)
        self.assertEqual(res.status_code, 409)
        self.assertIn("sudah aktif", res.json()["detail"])

    def test_admin_target_unknown_target_and_non_admin_rejected(self):
        self.assertEqual(self._resend(22).status_code, 403)
        self.assertEqual(self._resend(99).status_code, 404)
        self.current = {**ADMIN, "id": 5, "role": "lecturer"}
        self.assertEqual(self._resend().status_code, 403)
        self.assertEqual(self.db.users[20]["hash"], "hash-lama")
        self.assertEqual(self.db.audit, [])

    def test_audit_has_only_actor_target_action(self):
        token = self._resend().json()["activation_url"].split("#token=")[1]
        self._resend(21)  # ditolak: tidak dicatat
        self.assertEqual(self.db.audit, [(ADMIN["id"], 20, "resend_activation", None)])
        self.assertNotIn(token, str(self.db.audit))
