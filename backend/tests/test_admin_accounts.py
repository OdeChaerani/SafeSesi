"""Pembuatan akun oleh admin beserta profilnya, lewat HTTP dengan database tiruan yang bisa rollback."""
from __future__ import annotations

import copy
import logging
from unittest.mock import patch

import asyncpg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import admin
from api.deps import get_current_user, get_db
from core.security import hash_token
from tests.base import BaseTestCase
from tests.test_auth import _settings

ADMIN = {"id": 1, "name": "Admin", "email": "a@s.ac.id", "role": "admin"}


def _duplicate(constraint: str) -> asyncpg.UniqueViolationError:
    error = asyncpg.UniqueViolationError("duplikat")
    error.constraint_name = constraint
    return error


class FakeDb:
    """Meniru indeks unik lower(...) dan rollback transaksi."""

    def __init__(self) -> None:
        self.users: list[dict] = []
        self.students: list[dict] = []
        self.lecturers: list[dict] = []
        self.audit: list[tuple] = []
        self.fail_profile: Exception | None = None

    def transaction(self):
        db = self

        class Tx:
            async def __aenter__(self):
                self.snapshot = copy.deepcopy((db.users, db.students, db.lecturers, db.audit))

            async def __aexit__(self, exc_type, exc, tb):
                if exc_type:
                    db.users, db.students, db.lecturers, db.audit = self.snapshot
                return False

        return Tx()

    async def fetchrow(self, query, name, email, role, token_hash, expires_at):
        if any(u["email"].lower() == email.lower() for u in self.users):
            raise _duplicate("uq_users_email_active")
        user = {"id": len(self.users) + 100, "name": name, "email": email, "role": role}
        self.users.append({**user, "token_hash": token_hash})
        return user

    async def execute(self, query, user_id, *values):
        if "INTO admin_audit_log" in query:
            self.audit.append((user_id, *values))  # (pelaku, sasaran, aksi, ip)
            return
        if self.fail_profile:
            raise self.fail_profile
        if "INTO students" in query:
            npm, institution = values
            if npm and any((s["npm"] or "").lower() == npm.lower() for s in self.students):
                raise _duplicate("uq_students_npm")
            self.students.append({"user_id": user_id, "npm": npm, "asal_institusi": institution})
        else:
            (nip,) = values
            if any(r["nip"].lower() == nip.lower() for r in self.lecturers):
                raise _duplicate("uq_lecturers_nip")
            self.lecturers.append({"user_id": user_id, "nip": nip})


class TestAdminCreateAccount(BaseTestCase):
    def setUp(self):
        self.db = FakeDb()
        self.current = dict(ADMIN)
        app = FastAPI()
        app.include_router(admin.router, prefix="/api/v1")

        async def fake_db():
            yield self.db

        app.dependency_overrides[get_db] = fake_db
        app.dependency_overrides[get_current_user] = lambda: self.current
        self.client = TestClient(app, raise_server_exceptions=False)
        p = patch("api.admin.get_settings", return_value=_settings())
        p.start()
        self.addCleanup(p.stop)
        self.count = 0

    def _create(self, role="student", **fields):
        self.count += 1
        body = {"name": "Uji", "email": f"u{self.count}@s.ac.id", "role": role, **fields}
        return self.client.post("/api/v1/admin/users", json=body)

    def _assert_rejected(self, res, status, field):
        self.assertEqual(res.status_code, status, res.text)
        self.assertEqual(res.json()["field"], field)

    def _counts(self):
        return len(self.db.users), len(self.db.students), len(self.db.lecturers)

    def test_student_with_npm(self):
        res = self._create(npm=" DEV 001 ")
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(self.db.students, [{"user_id": 100, "npm": "DEV001", "asal_institusi": None}])
        token = res.json()["activation_url"].split("#token=")[1]
        self.assertEqual(self.db.users[0]["token_hash"], hash_token(token))

    def test_student_without_npm_with_institution(self):
        self.assertEqual(self._create(asal_institusi="  Kampus   Fiktif ").status_code, 201)
        self.assertEqual(self.db.students[0]["asal_institusi"], "Kampus Fiktif")
        self.assertIsNone(self.db.students[0]["npm"])

    def test_student_without_either_rejected(self):
        res = self._create(npm="   ")
        self._assert_rejected(res, 422, "asal_institusi")
        self.assertIn("Asal institusi wajib", res.json()["detail"])
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_lecturer_without_nip_rejected(self):
        for fields in ({}, {"nip": "  "}):
            self._assert_rejected(self._create("lecturer", **fields), 422, "nip")
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_nip_stored_without_inner_spaces(self):
        self.assertEqual(self._create("lecturer", nip="11111111 222222 3 444").status_code, 201)
        self.assertEqual(self.db.lecturers[0]["nip"], "111111112222223444")

    def test_admin_without_profile_ok_and_with_profile_rejected(self):
        self.assertEqual(self._create("admin").status_code, 201)
        self.assertEqual(self._counts(), (1, 0, 0))
        for field in ("npm", "asal_institusi", "nip"):
            for value in ("X", ""):
                self._assert_rejected(self._create("admin", **{field: value}), 422, field)
        self.assertEqual(self._counts(), (1, 0, 0))

    def test_field_of_other_role_rejected(self):
        self._assert_rejected(self._create("student", npm="DEV1", nip="DEV2"), 422, "nip")
        self._assert_rejected(self._create("lecturer", nip="DEV2", npm="DEV1"), 422, "npm")

    def test_duplicate_npm_ignores_case_and_spaces(self):
        self.assertEqual(self._create(npm="Dev-Abc").status_code, 201)
        res = self._create(npm=" DEV - ABC ")
        self._assert_rejected(res, 409, "npm")
        self.assertEqual(res.json()["detail"], "NPM sudah dipakai oleh akun lain.")
        self.assertEqual(self._counts(), (1, 1, 0))

    def test_duplicate_nip_ignores_case_and_spaces(self):
        self.assertEqual(self._create("lecturer", nip="Dev 12").status_code, 201)
        res = self._create("lecturer", nip="DEV12")
        self._assert_rejected(res, 409, "nip")
        self.assertEqual(res.json()["detail"], "NIP sudah dipakai oleh akun lain.")
        self.assertEqual(self._counts(), (1, 0, 1))

    def test_duplicate_email_409(self):
        body = {"name": "Uji", "email": "sama@s.ac.id", "role": "student", "npm": "DEV1"}
        self.assertEqual(self.client.post("/api/v1/admin/users", json=body).status_code, 201)
        res = self.client.post("/api/v1/admin/users", json={**body, "email": "SAMA@s.ac.id", "npm": "DEV2"})
        self._assert_rejected(res, 409, "email")

    def test_profile_failure_leaves_no_user_or_token(self):
        self.db.fail_profile = RuntimeError("tulis profil gagal")
        self.assertEqual(self._create(npm="DEV1").status_code, 500)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_create_user_audited_without_token_or_personal_data(self):
        res = self._create(npm="DEV1")
        self.assertEqual(self.db.audit, [(ADMIN["id"], 100, "create_user", None)])
        token = res.json()["activation_url"].split("#token=")[1]
        self.assertNotIn(token, str(self.db.audit))
        self.assertNotIn(hash_token(token), str(self.db.audit))

    def test_rejected_creation_writes_no_audit(self):
        self._create(npm="DEV1")
        self._create(npm="dev1")  # ganda
        self._create("lecturer")  # tanpa NIP
        self.db.fail_profile = RuntimeError("gagal")
        self._create(npm="DEV2")
        self.assertEqual(len(self.db.audit), 1)

    def test_non_admin_forbidden(self):
        for role in ("student", "lecturer"):
            self.current = {**ADMIN, "id": 5, "role": role}
            self.assertEqual(self._create(npm="DEV1").status_code, 403)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_activation_token_never_logged(self):
        messages: list[str] = []

        class Capture(logging.Handler):
            def emit(self, record):
                messages.append(record.getMessage())

        root, handler = logging.getLogger(), Capture(level=logging.DEBUG)
        previous = root.level
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        self.addCleanup(root.setLevel, previous)
        self.addCleanup(root.removeHandler, handler)

        token = self._create(npm="DEV1").json()["activation_url"].split("#token=")[1]
        self.db.fail_profile = RuntimeError("gagal")
        self._create(npm="DEV2")
        logged = "\n".join(messages)
        self.assertTrue(messages)  # penangkap log memang aktif
        self.assertNotIn(token, logged)
        self.assertNotIn(hash_token(token), logged)
