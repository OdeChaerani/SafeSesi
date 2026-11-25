-- Profil mahasiswa dan dosen. Admin tidak punya baris profil.
-- npm / asal_institusi hanya data identitas: TIDAK menentukan akses kelas.
-- FK gabungan (user_id, role) menjamin profil hanya menempel ke pengguna dengan role yang cocok, dan
-- role pengguna yang sudah punya profil tidak bisa diganti diam-diam.
-- ON DELETE RESTRICT: akun dihapus secara soft delete (deleted_at); hard delete harus gagal selama
-- profil masih ada, agar identitas tidak ikut terhapus tanpa disadari.

ALTER TABLE public.users
    ADD CONSTRAINT users_id_role_key UNIQUE (id, role);

CREATE TABLE public.students (
    user_id        bigint PRIMARY KEY,
    role           public.user_role NOT NULL DEFAULT 'student'
                   CONSTRAINT students_role_check CHECK (role = 'student'),
    npm            text
                   CONSTRAINT students_npm_check
                   CHECK (npm IS NULL OR (npm = btrim(npm) AND char_length(npm) BETWEEN 1 AND 30)),
    asal_institusi text
                   CONSTRAINT students_asal_institusi_check
                   CHECK (asal_institusi IS NULL
                          OR (asal_institusi = btrim(asal_institusi) AND char_length(asal_institusi) BETWEEN 1 AND 100)),
    CONSTRAINT students_identity_check CHECK (npm IS NOT NULL OR asal_institusi IS NOT NULL),
    CONSTRAINT students_user_fkey FOREIGN KEY (user_id, role)
        REFERENCES public.users (id, role) ON DELETE RESTRICT
);

-- Tanpa filter deleted_at: NPM milik satu orang; akun yang dihapus dipulihkan, bukan dibuat ulang.
CREATE UNIQUE INDEX uq_students_npm ON public.students (lower(npm));

CREATE TABLE public.lecturers (
    user_id bigint PRIMARY KEY,
    role    public.user_role NOT NULL DEFAULT 'lecturer'
            CONSTRAINT lecturers_role_check CHECK (role = 'lecturer'),
    nip     text NOT NULL
            CONSTRAINT lecturers_nip_check CHECK (nip = btrim(nip) AND char_length(nip) BETWEEN 1 AND 30),
    CONSTRAINT lecturers_user_fkey FOREIGN KEY (user_id, role)
        REFERENCES public.users (id, role) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX uq_lecturers_nip ON public.lecturers (lower(nip));

-- Sama seperti tabel lain: RLS aktif tanpa policy, dan role API Supabase tidak diberi akses
-- (default privileges proyek memberi ALL ke anon/authenticated untuk tabel baru).
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lecturers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.students, public.lecturers FROM anon, authenticated;
