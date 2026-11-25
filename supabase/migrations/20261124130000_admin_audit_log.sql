-- Catatan audit tindakan admin. Sengaja TIDAK menyimpan token, hash token, maupun tautan.
-- Belum ada endpoint baca. Kolom action dibatasi; tambahkan nilai baru lewat migrasi tersendiri.

CREATE TABLE public.admin_audit_log (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id       bigint NOT NULL REFERENCES public.users (id),
    target_user_id bigint NOT NULL REFERENCES public.users (id),
    action         text NOT NULL CONSTRAINT admin_audit_log_action_check CHECK (action IN ('issue_reset_token')),
    ip             text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_admin_audit_log_target ON public.admin_audit_log (target_user_id, created_at DESC);

-- Sama seperti tabel lain: tanpa ini role API Supabase (anon/authenticated) bisa membaca dan menulisnya.
ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.admin_audit_log FROM anon, authenticated;
