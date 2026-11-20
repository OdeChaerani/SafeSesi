-- Evaluasi MITI: pesan kegagalan, jejak debug pengodean, dan bukti umpan balik.

ALTER TABLE public.evaluations
    ADD COLUMN error_message text,  -- diisi saat status = 'failed'
    ADD COLUMN coding_debug jsonb;  -- unit sebelum/sesudah aturan penghitungan + aturan yang berlaku

ALTER TABLE public.feedback_items
    ADD COLUMN excerpt text,
    ADD COLUMN evidence_turn_nos integer[] NOT NULL DEFAULT '{}';
