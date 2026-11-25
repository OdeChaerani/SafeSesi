-- Uji manual setelah migrasi revoke_public_access, HANYA database lokal:
--   Get-Content supabase\local\check_public_access.sql -Raw | docker exec -i supabase_db_safesesi psql -U postgres -d postgres -v ON_ERROR_STOP=1
-- Hasil yang benar: satu baris "LULUS". Tabel probe dibuat untuk menguji default privileges,
-- lalu dibatalkan oleh ROLLBACK. Tidak ada probe fungsi: fungsi baru memang mendapat EXECUTE untuk
-- PUBLIC sampai migrasinya mencabutnya, dan fungsi yang lupa dicabut akan muncul di hasil.
BEGIN;
CREATE TABLE public.zz_probe_table (id bigint GENERATED ALWAYS AS IDENTITY);  -- probe

WITH r(role) AS (VALUES ('anon'), ('authenticated')),
violations(masalah, objek) AS (
    -- hak pada tabel, view, urutan (langsung atau lewat PUBLIC)
    SELECT 'hak ' || a.privilege_type || ' untuk ' || COALESCE(NULLIF(a.grantee, 0)::regrole::text, 'PUBLIC'),
           c.oid::regclass::text
    FROM pg_class c, aclexplode(c.relacl) a
    WHERE c.relnamespace = 'public'::regnamespace
      AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
    UNION ALL
    -- hak tingkat kolom
    SELECT 'hak kolom ' || a.privilege_type, c.oid::regclass::text || '.' || t.attname
    FROM pg_attribute t JOIN pg_class c ON c.oid = t.attrelid, aclexplode(t.attacl) a
    WHERE c.relnamespace = 'public'::regnamespace
      AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
    UNION ALL
    -- fungsi (termasuk pemicu) yang masih bisa dieksekusi, langsung atau lewat PUBLIC
    SELECT 'EXECUTE untuk ' || r.role, p.oid::regprocedure::text
    FROM pg_proc p CROSS JOIN r
    WHERE p.pronamespace = 'public'::regnamespace
      AND has_function_privilege(r.role, p.oid, 'EXECUTE')
    UNION ALL
    SELECT 'view tanpa security_invoker', c.oid::regclass::text
    FROM pg_class c
    WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'v'
      AND NOT COALESCE(c.reloptions @> ARRAY['security_invoker=true'], false)
)
SELECT masalah, objek FROM violations
UNION ALL
SELECT 'LULUS', 'tidak ada pelanggaran' WHERE NOT EXISTS (SELECT 1 FROM violations)
ORDER BY 1, 2;

ROLLBACK;
