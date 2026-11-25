-- HANYA untuk database dev LOKAL yang sudah berisi pengguna sebelum migrasi user_profiles.
-- Sengaja bukan migrasi, agar nilai sementara ini tidak pernah masuk production.
-- Tidak diperlukan setelah `supabase db reset` (seed.sql sudah membuat profilnya).
-- Ganti nilai 'DATA LOKAL' dan 'TEMP-<id>' dengan data yang benar; baris yang diisi ditampilkan di bawah.

INSERT INTO public.students (user_id, asal_institusi)
SELECT id, 'DATA LOKAL' FROM public.users WHERE role = 'student'
ON CONFLICT (user_id) DO NOTHING
RETURNING user_id, asal_institusi;

INSERT INTO public.lecturers (user_id, nip)
SELECT id, 'TEMP-' || id FROM public.users WHERE role = 'lecturer'
ON CONFLICT (user_id) DO NOTHING
RETURNING user_id, nip;
