"""Pengujian Matriks Hak Akses (BRD 7.1 no. 16, BRD 5, dan Keputusan Arsitektur).

Aturan Akses Sesi:
| Aksi | Mahasiswa Pemilik | Dosen Kelas Sesi Itu | Dosen Lain / Sesi Mandiri | Admin |
| Lihat Sesi, Transkrip, Topik, Evaluasi, Audio | OK | OK (kelas saja) | 403 | 403 (BRD 7.1 & Keputusan 1) |
| Kirim Giliran, Transkripsi, Akhiri, Minta Evaluasi | OK | 403 | 403 | 403 |
| Buat Sesi Baru (POST /sessions) | OK | 403 | 403 | 403 |
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Response

from api.deps import can_view_session, ensure_can_view_session, ensure_session_owner
from api.evaluations import get_evaluation, start_evaluation
from api.sessions import (
    create_new_session,
    end_active_session,
    get_briefing_topics,
    get_session_detail,
    send_counselor_turn,
)
from api.speech import client_turn_audio, transcribe_counselor_audio
from schemas.session import CreateSessionRequest, CreateTurnRequest
from tests.base import BaseTestCase


class TestAccessMatrix(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.conn = self.create_mock_connection()

        self.student_owner = self.get_sample_user(user_id=10, role="student", name="Pemilik Sesi")
        self.student_other = self.get_sample_user(user_id=11, role="student", name="Mahasiswa Lain")
        self.lecturer_course = self.get_sample_user(user_id=20, role="lecturer", name="Dosen Kelas")
        self.lecturer_other = self.get_sample_user(user_id=21, role="lecturer", name="Dosen Luar")
        self.admin_user = self.get_sample_user(user_id=1, role="admin", name="Admin")

        # Sesi Mandiri (tanpa kelas)
        self.session_independent = {
            "id": 101,
            "student_id": 10,
            "scenario_id": 1,
            "class_id": None,
            "status": "active",
            "scenario_snapshot": self.get_sample_snapshot(),
        }

        # Sesi Kelas (terkait class_id 5)
        self.session_class = {
            "id": 102,
            "student_id": 10,
            "scenario_id": 1,
            "class_id": 5,
            "status": "active",
            "scenario_snapshot": self.get_sample_snapshot(),
        }

    # =========================================================================
    # 1. can_view_session Logic
    # =========================================================================
    @patch("api.deps.lecturer_manages_session", new_callable=AsyncMock)
    def test_can_view_session_independent(self, mock_manages):
        """Sesi mandiri HANYA bisa dilihat oleh mahasiswa pemiliknya."""
        mock_manages.return_value = True  # meski helper mengembalikan True, class_id None harus ditolak

        # Mahasiswa pemilik: Boleh
        self.assertTrue(self.run_async(can_view_session(self.conn, self.session_independent, self.student_owner)))

        # Mahasiswa lain: Ditolak
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_independent, self.student_other)))

        # Dosen: Ditolak (BRD 7.1 no 16: hasil latihan mandiri hanya diakses mahasiswa bersangkutan)
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_independent, self.lecturer_course)))

        # Admin: Ditolak (Keputusan 1 & BRD 5: admin tidak membaca sesi/transkrip)
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_independent, self.admin_user)))

    @patch("api.deps.lecturer_manages_session", new_callable=AsyncMock)
    def test_can_view_session_class(self, mock_manages):
        """Sesi kelas dapat dilihat oleh mahasiswa pemilik dan dosen pengampu kelas itu saja."""
        # Mahasiswa pemilik: Boleh
        self.assertTrue(self.run_async(can_view_session(self.conn, self.session_class, self.student_owner)))

        # Mahasiswa lain: Ditolak
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_class, self.student_other)))

        # Dosen pengampu kelas: Boleh
        mock_manages.return_value = True
        self.assertTrue(self.run_async(can_view_session(self.conn, self.session_class, self.lecturer_course)))

        # Dosen luar kelas: Ditolak
        mock_manages.return_value = False
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_class, self.lecturer_other)))

        # Admin: Ditolak (Keputusan 1)
        self.assertFalse(self.run_async(can_view_session(self.conn, self.session_class, self.admin_user)))

    # =========================================================================
    # 2. ensure_session_owner Logic (Write / Action Guard)
    # =========================================================================
    def test_ensure_session_owner_permits_only_student_owner(self):
        """Hanya mahasiswa pemilik yang boleh berpraktik (kirim giliran, akhiri sesi, minta evaluasi)."""
        # Mahasiswa pemilik: Lolos tanpa error
        ensure_session_owner(self.session_independent, self.student_owner)
        ensure_session_owner(self.session_class, self.student_owner)

        # Mahasiswa lain: 403
        with self.assertRaises(HTTPException) as ctx:
            ensure_session_owner(self.session_class, self.student_other)
        self.assertEqual(ctx.exception.status_code, 403)

        # Dosen pengampu: 403 (dosen tidak boleh mengisi giliran ke sesi mahasiswa!)
        with self.assertRaises(HTTPException) as ctx:
            ensure_session_owner(self.session_class, self.lecturer_course)
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin: 403
        with self.assertRaises(HTTPException) as ctx:
            ensure_session_owner(self.session_class, self.admin_user)
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 3. Endpoint: GET /sessions/{id} (get_session_detail)
    # =========================================================================
    @patch("api.deps.lecturer_manages_session", new_callable=AsyncMock)
    @patch("api.sessions.get_session_turns", new_callable=AsyncMock, return_value=[])
    @patch("api.sessions.get_latest_topic_notes", new_callable=AsyncMock, return_value=[])
    def test_get_session_detail_access(self, _notes, _turns, mock_manages):
        self.conn.fetchrow.return_value = self.session_class

        # Mahasiswa pemilik: 200
        res = self.run_async(get_session_detail(102, user=self.student_owner, conn=self.conn))
        self.assertEqual(res["id"], 102)

        # Mahasiswa lain: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_session_detail(102, user=self.student_other, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Dosen kelas: 200
        mock_manages.return_value = True
        res_lec = self.run_async(get_session_detail(102, user=self.lecturer_course, conn=self.conn))
        self.assertEqual(res_lec["id"], 102)

        # Dosen sesi mandiri: 403
        self.conn.fetchrow.return_value = self.session_independent
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_session_detail(101, user=self.lecturer_course, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin: 403
        self.conn.fetchrow.return_value = self.session_class
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_session_detail(102, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 4. Endpoint: POST /sessions/{id}/turns & end
    # =========================================================================
    @patch("api.sessions.get_session_by_id", new_callable=AsyncMock)
    def test_turn_and_end_forbidden_for_non_owner(self, mock_get_sess):
        mock_get_sess.return_value = self.session_class
        payload = CreateTurnRequest(content="Halo Nadia")

        # Mahasiswa lain: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(send_counselor_turn(102, payload, user=self.student_other, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Dosen: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(send_counselor_turn(102, payload, user=self.lecturer_course, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(send_counselor_turn(102, payload, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # End active session juga 403 untuk selain pemilik
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(end_active_session(102, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 5. Endpoint: Evaluasi (GET & POST)
    # =========================================================================
    @patch("api.evaluations.get_session_by_id", new_callable=AsyncMock)
    @patch("api.deps.lecturer_manages_session", new_callable=AsyncMock)
    def test_evaluation_access_admin_and_lecturer(self, mock_manages, mock_get_sess):
        mock_get_sess.return_value = self.session_class

        # Admin tidak boleh melihat evaluasi: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(get_evaluation(102, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin tidak boleh membuat evaluasi: 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(start_evaluation(102, MagicMock(), Response(), user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Dosen tidak boleh membuat evaluasi (hanya mahasiswa pemilik yang minta): 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(start_evaluation(102, MagicMock(), Response(), user=self.lecturer_course, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 6. Endpoint: Audio Klien & Transkripsi (Speech)
    # =========================================================================
    @patch("api.speech.get_session_by_id", new_callable=AsyncMock)
    def test_speech_access_rules(self, mock_get_sess):
        mock_get_sess.return_value = self.session_class

        # Transkripsi suara konselor: hanya pemilik (admin ditolak 403)
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(transcribe_counselor_audio(102, b"fakewebm", preview=False, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)

        # Audio klien: admin ditolak 403
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(client_turn_audio(102, 1, user=self.admin_user, conn=self.conn))
        self.assertEqual(ctx.exception.status_code, 403)
