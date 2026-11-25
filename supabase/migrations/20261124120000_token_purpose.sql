-- Token sekali pakai di users (activation_token_*) kini punya tujuan: 'activation' (akun belum aktif)
-- atau 'reset' (atur ulang kata sandi oleh admin, hanya untuk akun yang sudah aktif).
-- Baris lama otomatis 'activation'.

ALTER TABLE public.users
    ADD COLUMN activation_token_purpose text NOT NULL DEFAULT 'activation'
    CONSTRAINT users_activation_token_purpose_check CHECK (activation_token_purpose IN ('activation', 'reset'));
