-- Aksi audit baru: pembuatan akun dan pengiriman ulang tautan aktivasi.
-- Tidak membuat tabel, view, atau fungsi baru, jadi tidak ada hak yang perlu dicabut.
-- Setelah diterapkan di lokal, jalankan supabase/local/check_public_access.sql (hasil yang benar: LULUS).

ALTER TABLE public.admin_audit_log
    DROP CONSTRAINT admin_audit_log_action_check,
    ADD CONSTRAINT admin_audit_log_action_check
        CHECK (action IN ('issue_reset_token', 'create_user', 'resend_activation'));
