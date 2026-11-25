"""Profil mahasiswa/dosen: normalisasi isian dan pengambilan menurut role."""
from __future__ import annotations

from repositories.profiles import get_profile, normalize_lecturer_profile, normalize_student_profile
from schemas.profile import LecturerProfile, StudentProfile
from tests.base import BaseTestCase


class TestNormalize(BaseTestCase):
    def test_trims_and_turns_blank_into_none(self):
        profile = normalize_student_profile("  DEV-1  ", "   ")
        self.assertEqual((profile.npm, profile.asal_institusi), ("DEV-1", None))
        self.assertEqual(normalize_lecturer_profile(" DEV-2 ").nip, "DEV-2")

    def test_npm_and_nip_lose_every_space_institution_keeps_single_spaces(self):
        profile = normalize_student_profile(" 12 34\t56 ", "  Kampus   Fiktif \n Timur ")
        self.assertEqual((profile.npm, profile.asal_institusi), ("123456", "Kampus Fiktif Timur"))
        self.assertEqual(normalize_lecturer_profile("11111111 222222 3 444").nip, "111111112222223444")

    def test_empty_npm_accepted_with_institution(self):
        for npm in (None, "", "  "):
            profile = normalize_student_profile(npm, " Kampus Fiktif ")
            self.assertEqual((profile.npm, profile.asal_institusi), (None, "Kampus Fiktif"))

    def test_npm_and_institution_both_empty_rejected(self):
        with self.assertRaisesRegex(ValueError, "Asal institusi wajib diisi"):
            normalize_student_profile("  ", None)

    def test_empty_nip_rejected(self):
        for nip in (None, "", "   "):
            with self.assertRaisesRegex(ValueError, "NIP wajib"):
                normalize_lecturer_profile(nip)

    def test_length_limits_match_database(self):
        normalize_student_profile("x" * 30, "y" * 100)
        normalize_lecturer_profile(" x" * 30)  # batas dihitung setelah spasi dibuang
        for call in (
            lambda: normalize_student_profile("x" * 31, None),
            lambda: normalize_student_profile(None, "y" * 101),
            lambda: normalize_lecturer_profile("x" * 31),
        ):
            with self.assertRaisesRegex(ValueError, "maksimal"):
                call()


class TestGetProfile(BaseTestCase):
    def setUp(self):
        self.conn = self.create_mock_connection()

    def test_student_reads_students_table(self):
        self.conn.fetchrow.return_value = {"npm": None, "asal_institusi": "Kampus Fiktif"}
        profile = self.run_async(get_profile(self.conn, 10, "student"))
        self.assertEqual(profile, StudentProfile(npm=None, asal_institusi="Kampus Fiktif"))
        sql, user_id = self.conn.fetchrow.call_args.args
        self.assertIn("FROM students", sql)
        self.assertEqual(user_id, 10)

    def test_lecturer_reads_lecturers_table(self):
        self.conn.fetchrow.return_value = {"nip": "DEV-2"}
        self.assertEqual(self.run_async(get_profile(self.conn, 11, "lecturer")), LecturerProfile(nip="DEV-2"))
        self.assertIn("FROM lecturers", self.conn.fetchrow.call_args.args[0])

    def test_admin_has_no_profile_and_no_query(self):
        self.assertIsNone(self.run_async(get_profile(self.conn, 1, "admin")))
        self.conn.fetchrow.assert_not_called()

    def test_missing_profile_row_is_none(self):
        self.conn.fetchrow.return_value = None
        for role in ("student", "lecturer"):
            self.assertIsNone(self.run_async(get_profile(self.conn, 10, role)))
