-- Penanda waktu per kata dari STT untuk giliran konselor yang diucapkan (pengamatan vokal, Rubrik 2.6).
-- Isi: [{"word": "...", "start_ms": 0, "end_ms": 0}], milidetik sejak awal sesi.
-- NULL untuk giliran klien dan giliran konselor yang diketik.

ALTER TABLE public.turns
    ADD COLUMN word_timestamps jsonb;
