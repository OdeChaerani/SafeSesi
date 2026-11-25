-- Avatar 3D klien: nama file di frontend/public/models/ (mis. 'girl1.glb').
-- NULL = frontend memilih avatar default menurut gender. Bagian identitas dasar klien,
-- jadi boleh dikirim ke mahasiswa bersama nama/usia/gender.
-- Hanya nama file sederhana agar tidak bisa dipakai sebagai path ke lokasi lain.

ALTER TABLE public.scenario_personas
    ADD COLUMN avatar_file text
    CONSTRAINT scenario_personas_avatar_file_check CHECK (avatar_file ~ '^[A-Za-z0-9_-]+\.glb$');
