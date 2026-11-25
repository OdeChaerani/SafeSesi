-- Tutup akses lewat API Supabase. Aplikasi hanya mengakses database lewat backend (DATABASE_URL),
-- jadi role anon dan authenticated tidak butuh hak apa pun di skema public.
-- Hak postgres (pemilik) dan service_role tidak diubah.

-- (a) View dijalankan dengan hak PEMANGGIL, sehingga RLS tabel di bawahnya berlaku.
ALTER VIEW public.v_sessions_for_lecturer SET (security_invoker = true);
ALTER VIEW public.v_code_counts SET (security_invoker = true);
ALTER VIEW public.v_summary_measures SET (security_invoker = true);

-- (b) Cabut semua hak yang sudah ada. "ALL TABLES" mencakup view.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM anon, authenticated;

-- (c) Objek BARU buatan postgres (role yang menjalankan migrasi) tidak lagi diberi hak.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;
-- PostgreSQL tetap memberi EXECUTE ke PUBLIC pada setiap fungsi baru (default global, sengaja tidak
-- diubah di sini). WAJIB: setiap migrasi yang membuat fungsi di skema public mencabutnya sendiri:
--   REVOKE EXECUTE ON FUNCTION public.nama_fungsi(tipe) FROM PUBLIC, anon, authenticated;

-- (d) Fungsi yang sudah ada (termasuk fungsi pemicu): tutup juga jalur PUBLIC.
-- Pemicu yang sudah terpasang tetap jalan; hak EXECUTE hanya diperiksa saat pemicu dibuat.
REVOKE EXECUTE ON FUNCTION
    public.build_scenario_snapshot(bigint),
    public.purge_deleted_sessions(integer),
    public.purge_old_refresh_tokens(integer),
    public.check_miti_rules(),
    public.set_updated_at()
FROM PUBLIC, anon, authenticated;
