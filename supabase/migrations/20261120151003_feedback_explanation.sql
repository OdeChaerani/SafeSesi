-- Penjelasan Feedback Agent untuk alternative_response (content berisi kalimat alternatifnya).
-- Nullable: jenis feedback lain menyimpan penjelasan di content, dan evaluasi lama tidak punya nilai ini.

ALTER TABLE public.feedback_items
    ADD COLUMN explanation text;
