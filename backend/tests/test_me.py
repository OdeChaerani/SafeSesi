"""GET /auth/me: data akun milik pengguna yang sedang masuk, dari database."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import router
from api.deps import get_db
from core.security import create_access_token
from tests.base import BaseTestCase
from tests.test_auth import _settings

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
BASE_KEYS = {"id", "name", "email", "role", "status", "created_at", "activated_at"}


def _user(user_id: int, role: str) -> dict:
    # Sengaja memuat kolom rahasia: respons tidak boleh meneruskannya.
    return {
        "id": user_id,
        "name": f"User {user_id}",
        "email": f"u{user_id}@s.ac.id",
        "role": role,
        "created_at": NOW,
        "activated_at": NOW,
        "password_hash": "$argon2id$rahasia",
        "activation_token_hash": "hash-rahasia",
    }


class TestMe(BaseTestCase):
    def setUp(self):
        self.settings = _settings()
        self.users = {1: _user(1, "admin"), 10: _user(10, "student"), 11: _user(11, "lecturer"), 12: _user(12, "student")}
        self.conn = self.create_mock_connection()
        self.conn.fetchrow.return_value = None
        self.conn.fetch.return_value = []
        conn = self.conn

        class Acquire:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *args):
                pass

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.state.db_pool = MagicMock()
        app.state.db_pool.acquire = Acquire

        async def fake_db():
            yield conn

        app.dependency_overrides[get_db] = fake_db
        self.client = TestClient(app)

        async def find_user(_conn, user_id):
            row = self.users.get(user_id)
            return dict(row) if row else None

        for p in (
            patch("api.deps.get_settings", return_value=self.settings),
            patch("api.deps.get_user_by_id", find_user),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _get(self, user_id: int, query: str = "", token_role: str | None = None):
        role = token_role or self.users[user_id]["role"]
        token = create_access_token({"id": user_id, "role": role}, self.settings)
        return self.client.get(f"/api/v1/auth/me{query}", headers={"Authorization": f"Bearer {token}"})

    def test_requires_login(self):
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        bad = self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer palsu"})
        self.assertEqual(bad.status_code, 401)
        self.conn.fetchrow.assert_not_called()

    def test_student_with_empty_npm_and_classes(self):
        self.conn.fetchrow.return_value = {"npm": None, "asal_institusi": "Kampus Fiktif"}
        self.conn.fetch.return_value = [
            {"id": 3, "name": "Kelas A", "academic_year": "2026/2027", "lecturers": ["Dosen X"]}
        ]
        res = self._get(10)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(set(body), BASE_KEYS | {"npm", "asal_institusi", "classes"})
        self.assertIsNone(body["npm"])
        self.assertEqual(body["asal_institusi"], "Kampus Fiktif")
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["classes"][0]["lecturers"], ["Dosen X"])

    def test_lecturer_gets_nip_and_classes(self):
        self.conn.fetchrow.return_value = {"nip": "DEV-1"}
        body = self._get(11).json()
        self.assertEqual(set(body), BASE_KEYS | {"nip", "classes"})
        self.assertEqual(body["nip"], "DEV-1")

    def test_admin_has_no_profile_or_classes(self):
        res = self._get(1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(set(res.json()), BASE_KEYS)
        self.conn.fetchrow.assert_not_called()
        self.conn.fetch.assert_not_called()

    def test_old_account_without_profile_row(self):
        for user_id, empty in ((10, ("npm", "asal_institusi")), (11, ("nip",))):
            res = self._get(user_id)
            self.assertEqual(res.status_code, 200)
            for key in empty:
                self.assertIsNone(res.json()[key])
            self.assertEqual(res.json()["classes"], [])

    def test_no_secrets_in_response(self):
        for user_id in (1, 10, 11):
            text = self._get(user_id).text
            for secret in ("password", "argon2", "token", "hash-rahasia"):
                self.assertNotIn(secret, text)

    def test_only_own_data_even_when_another_id_is_requested(self):
        body = self._get(10, query="?user_id=12&id=12").json()
        self.assertEqual(body["id"], 10)
        self.assertEqual(self.conn.fetchrow.call_args.args[1], 10)
        self.assertEqual(self.conn.fetch.call_args.args[1], 10)

    def test_role_comes_from_database_not_token(self):
        body = self._get(10, token_role="admin").json()
        self.assertEqual(body["role"], "student")
