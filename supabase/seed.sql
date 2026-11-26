-- =====================================================================
-- SafeSesi - Seed (Idempotent), database LOKAL
-- Isi keempat skenario sama dengan Ilustrasi_Sesi_dan_Evaluasi_SafeSesi_final.docx
-- (sumber: backend/evals/fixtures/ilustrasi/ilustrasi_state_sessions.json).
-- Skenario: Nadia Maharani (SS-NAD-01), Pak Hendra (SS-HEN-01), Bu Rina (SS-RIN-01),
--           Sari Wulandari (SS-SAR-01)
-- Data uji LOKAL: satu mahasiswa uji dan satu kelas uji (password khusus pengembangan).
-- =====================================================================

SET search_path TO public, extensions;

DO $$
DECLARE
    v_owner_id bigint;
    v_nadia_id bigint;
    v_hendra_id bigint;
    v_rina_id bigint;
    v_sari_id bigint;
    v_student_id bigint;
    v_admin_id bigint;
    v_external_id bigint;
    v_class_id bigint;
    v_kls_id bigint;
    v_other_class_id bigint;
BEGIN
    -- =================================================================
    -- 1. Pastikan user 'peneliti' tersedia sebagai pemilik skenario katalog awal
    -- =================================================================
    SELECT id INTO v_owner_id FROM public.users WHERE lower(email) = 'peneliti@safesesi.ac.id';
    IF v_owner_id IS NULL THEN
        INSERT INTO public.users (name, email, role, password_hash, activated_at)
        VALUES (
            'Peneliti SafeSesi',
            'peneliti@safesesi.ac.id',
            'lecturer'::public.user_role,
            -- password123 (argon2id)
            '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            now()
        )
        RETURNING id INTO v_owner_id;
    ELSE
        UPDATE public.users
        SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            activated_at = COALESCE(activated_at, now())
        WHERE id = v_owner_id;
    END IF;

    -- =================================================================
    -- 2. SKENARIO 1: Nadia Maharani (SS-NAD-01), sesuai Ilustrasi final
    -- =================================================================
    SELECT id INTO v_nadia_id FROM public.scenarios WHERE title = 'Kewalahan membagi waktu';
    IF v_nadia_id IS NULL THEN
        INSERT INTO public.scenarios (title, owner_id, visibility, review_status, change_target)
        VALUES (
            'Kewalahan membagi waktu',
            v_owner_id,
            'catalog'::public.scenario_visibility,
            'draft'::public.review_status,
            'Membagi atau membatasi tanggung jawab tambahan agar sesuai dengan kemampuan dan waktu yang tersedia.'
        )
        RETURNING id INTO v_nadia_id;

        INSERT INTO public.scenario_personas (
            scenario_id, name, age, gender, education, occupation, marital_status,
            family_background, personality, communication_style, additional_background, avatar_file
        ) VALUES (
            v_nadia_id,
            'Nadia Maharani',
            19,
            'Perempuan',
            'Mahasiswi psikologi semester 3.',
            'Mahasiswi penuh waktu.',
            'Belum menikah.',
            'Tinggal bersama orang tua dan adik. Orang tua menghargai tanggung jawab akademik; kondisi ekonomi keluarga tidak menjadi fokus masalah.',
            'Menjaga komitmen, sulit menolak permintaan, dan khawatir mengecewakan orang lain.',
            'Pada awal pertemuan menjawab singkat dan berhati-hati; lebih elaboratif ketika merasa dipahami.',
            'Pertemanan dan pengalaman organisasi penting baginya. Rincian konflik yang langsung terkait masalah dicatat dalam Kasus.',
            'girl1.glb'
        );

        INSERT INTO public.scenario_cases (
            scenario_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        ) VALUES (
            v_nadia_id,
            'Nadia kewalahan membagi tanggung jawab pada dua kepanitiaan dan satu organisasi, sementara tugas kuliah juga perlu diselesaikan.',
            'Selama sekitar enam minggu, tenggat kegiatan dan tugas kuliah sering berdekatan. Tidur berkurang, dua tugas kuliah terlambat, dan Nadia lebih mudah kesal serta sulit fokus.',
            'Harapan awal: tetap terlibat dalam kegiatan organisasi yang memberi pertemanan dan pengalaman belajar tanpa membuat kuliah keteteran. Konteks perubahan perilaku: membagi atau membatasi tanggung jawab tambahan agar sesuai dengan kemampuan dan waktu yang tersedia.',
            'Tidak ada informasi kesehatan khusus. Kelelahan dijelaskan sebagai dampak kesibukan, bukan diagnosis.',
            'Nadia, 19 tahun, mahasiswi psikologi semester 3. Ia aktif di dua kepanitiaan dan satu organisasi, dan belakangan merasa kewalahan membagi waktu dengan kuliah. Ia datang untuk membicarakannya. Arah latihan: bantu Nadia memperjelas keinginannya dan, bila ia mau, cara membagi atau membatasi tanggung jawab tambahan.'
        );

        INSERT INTO public.scenario_hidden_facts (scenario_id, code, short_title, fact, sort_order, min_disclosure_level)
        VALUES
            (v_nadia_id, 'H1', 'Kekhawatiran terhadap penilaian teman', 'Nadia takut dianggap tidak serius atau tidak dapat diandalkan jika meminta pengurangan tanggung jawab atau menolak tugas tambahan.', 1, 'medium'::public.disclosure_level),
            (v_nadia_id, 'H2', 'Pengalaman komentar kurang kompak', 'Pada kepanitiaan sebelumnya, seorang teman pernah menyebut Nadia kurang kompak ketika ia tidak dapat membantu karena tugas kuliah.', 2, 'medium'::public.disclosure_level),
            (v_nadia_id, 'H3', 'Pengalaman meminta bantuan desain', 'Pada acara sebelumnya, Nadia pernah meminta bantuan desain dan teman bersedia membantu. Pada kepanitiaan saat ini, ia belum meminta bantuan.', 3, 'medium'::public.disclosure_level),
            (v_nadia_id, 'H4', 'Pengalaman bersama orang tua soal tanggung jawab', 'Nadia pernah merasa bersalah setelah orang tua mempertanyakan tanggung jawab yang tidak ia tuntaskan.', 4, 'high'::public.disclosure_level);

        INSERT INTO public.scenario_initial_states (
            scenario_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
            reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        ) VALUES (
            v_nadia_id,
            'Cemas dan kewalahan',
            'Tenggat kuliah serta kegiatan organisasi bertumpuk.',
            'guarded'::public.disclosure_level,
            'Awal sesi; bersedia membicarakan kesibukan, belum langsung menyampaikan kekhawatiran pribadi.',
            'Ingin beban berkurang agar kuliah tidak keteteran.',
            'Ingin tetap terlibat dalam kegiatan yang bermakna.',
            'both'::public.ambivalence_lean,
            false,
            NULL,
            NULL
        );
    END IF;

    -- =================================================================
    -- 3. SKENARIO 2: Hendra Saputra (Pak Hendra) (SS-HEN-01), sesuai Ilustrasi final
    -- =================================================================
    SELECT id INTO v_hendra_id FROM public.scenarios WHERE title = 'Diminta berhenti merokok';
    IF v_hendra_id IS NULL THEN
        INSERT INTO public.scenarios (title, owner_id, visibility, review_status, change_target)
        VALUES (
            'Diminta berhenti merokok',
            v_owner_id,
            'catalog'::public.scenario_visibility,
            'draft'::public.review_status,
            'Mengurangi atau menghentikan kebiasaan merokok.'
        )
        RETURNING id INTO v_hendra_id;

        INSERT INTO public.scenario_personas (
            scenario_id, name, age, gender, education, occupation, marital_status,
            family_background, personality, communication_style, additional_background, avatar_file
        ) VALUES (
            v_hendra_id,
            'Hendra Saputra (Pak Hendra)',
            27,
            'Laki-laki',
            'Lulusan SMK jurusan otomotif; detail riwayat sekolah tidak menjadi fokus skenario.',
            'Pemilik bengkel motor kecil.',
            'Menikah.',
            'Tinggal bersama istri dan seorang anak laki-laki berusia 8 tahun. Istrinya beberapa kali meminta ia berhenti merokok dan sering mengingatkannya, termasuk di depan orang lain.',
            'Mandiri, terbiasa memutuskan sendiri, dan mudah bersikap defensif ketika merasa diatur atau digurui.',
            'Ringkas dan lugas; kadang bercanda untuk menghindari topik berat; menjawab lebih panjang ketika lawan bicara tidak terdengar menggurui.',
            'Merokok sejak masa SMK. Rekan kerja di bengkel juga merokok, dan waktu istirahat selama bekerja singkat.',
            'man1.glb'
        );

        INSERT INTO public.scenario_cases (
            scenario_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        ) VALUES (
            v_hendra_id,
            'Istri Pak Hendra memintanya berhenti merokok, sedangkan ia sendiri belum yakin perlu atau sanggup berubah sekarang.',
            'Pak Hendra merokok sekitar dua bungkus per hari sejak masa SMK. Ia mengakui rokok makin mahal, bajunya sering bolong terkena bara, dan rasanya tidak seenak dulu. Perdebatan dengan istri membuatnya merasa dinasihati dan dikontrol.',
            'Harapan awal: belum meminta rencana berhenti; ingin diperlakukan sebagai orang yang memutuskan sendiri. Konteks perubahan perilaku: mengurangi atau menghentikan kebiasaan merokok.',
            NULL,
            'Pak Hendra, 27 tahun, pemilik bengkel motor kecil. Ia datang karena istrinya meminta ia berhenti merokok, dan ia belum tentu ingin berubah. Arah latihan: bantu Pak Hendra memperjelas pandangannya tentang kebiasaan merokok dan, bila ia mau, cara mengurangi atau menghentikannya.'
        );

        INSERT INTO public.scenario_hidden_facts (scenario_id, code, short_title, fact, sort_order, min_disclosure_level)
        VALUES
            (v_hendra_id, 'H1', 'Pengalaman mencoba berhenti', 'Pak Hendra pernah mencoba berhenti dua sampai tiga hari. Ia menjadi uring-uringan dan memarahi karyawan bengkelnya, lalu kembali merokok.', 1, 'medium'::public.disclosure_level),
            (v_hendra_id, 'H2', 'Kekhawatiran saat tidak merokok', 'Ia takut tidak kuat menahan gelisah dan mudah marah jika berhenti, baik di bengkel maupun di rumah. Ia juga tidak mau memakai obat atau permen bantu karena tidak ingin bergantung pada hal lain.', 2, 'medium'::public.disclosure_level),
            (v_hendra_id, 'H3', 'Kekhawatiran terhadap napas dan kesehatan', 'Belakangan ia mudah sesak napas ketika mendorong motor atau naik tangga. Ia khawatir itu tanda kesehatannya memburuk, tetapi gengsi mengakuinya pada istrinya.', 3, 'high'::public.disclosure_level);

        INSERT INTO public.scenario_initial_states (
            scenario_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
            reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        ) VALUES (
            v_hendra_id,
            'Kesal dan waspada',
            'Merasa kebiasaannya terus dipermasalahkan oleh istrinya.',
            'guarded'::public.disclosure_level,
            'Awal sesi; hanya bersedia mengakui kebiasaan merokok secara singkat di permukaan; belum membahas hal pribadi.',
            'Permintaan istri dan anak, serta rokok yang makin mahal dan kurang dinikmati (belum diungkapkan di awal).',
            'Rokok menjadi jeda kerja, dan ia tidak mau dipaksa.',
            'toward_status_quo'::public.ambivalence_lean,
            false,
            NULL,
            NULL
        );
    END IF;

    -- =================================================================
    -- 4. SKENARIO 3: Rina Kusumawati (SS-RIN-01), sesuai Ilustrasi final
    -- =================================================================
    SELECT id INTO v_rina_id FROM public.scenarios WHERE title = 'Sulit rutin bergerak';
    IF v_rina_id IS NULL THEN
        INSERT INTO public.scenarios (title, owner_id, visibility, review_status, change_target)
        VALUES (
            'Sulit rutin bergerak',
            v_owner_id,
            'catalog'::public.scenario_visibility,
            'draft'::public.review_status,
            'Memulai aktivitas berjalan kaki secara bertahap sesuai ketersediaan waktu.'
        )
        RETURNING id INTO v_rina_id;

        INSERT INTO public.scenario_personas (
            scenario_id, name, age, gender, education, occupation, marital_status,
            family_background, personality, communication_style, additional_background, avatar_file
        ) VALUES (
            v_rina_id,
            'Rina Kusumawati',
            36,
            'Perempuan',
            NULL,
            'Karyawan kantor dan ibu.',
            'Menikah.',
            'Tinggal bersama suami dan seorang anak. Pengasuhan serta jadwal kerja pasangan berpengaruh pada waktu luang.',
            'Bertanggung jawab terhadap pekerjaan dan keluarga, tetapi cenderung menyalahkan diri ketika kebiasaan baru tidak bertahan.',
            'Cukup terbuka mengenai kegiatan sehari-hari, namun ragu ketika membicarakan kegagalan atau penampilan tubuh.',
            'Lebih menikmati aktivitas santai yang dapat dilakukan bersama keluarga daripada aktivitas yang terasa seperti kewajiban.',
            'woman1.glb'
        );

        INSERT INTO public.scenario_cases (
            scenario_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        ) VALUES (
            v_rina_id,
            'Bu Rina ingin lebih aktif secara fisik, tetapi kesulitan menjaga kebiasaan berjalan atau olahraga ringan secara rutin.',
            'Pernah memulai jalan pagi selama beberapa minggu, lalu berhenti saat pekerjaan menumpuk. Ia cepat lelah ketika bermain bersama anak dan merasa kecewa pada diri sendiri.',
            'Harapan awal: menemukan aktivitas ringan yang sesuai dengan waktu, tenaga, dan kondisi keluarganya tanpa terbebani kewajiban setiap hari. Konteks perubahan perilaku: memulai aktivitas berjalan kaki secara bertahap sesuai ketersediaan waktu.',
            'Memperoleh anjuran umum untuk lebih banyak bergerak setelah pemeriksaan kesehatan kantor; tidak digunakan untuk menetapkan diagnosis.',
            'Bu Rina, 36 tahun, karyawan kantor dan ibu satu anak. Setelah pemeriksaan kesehatan kantor, ia dianjurkan lebih banyak bergerak, dan ia ingin lebih aktif tetapi merasa sulit menjaga kebiasaannya. Arah latihan: bantu Bu Rina memperjelas keinginannya dan, bila ia mau, langkah kecil berjalan kaki yang cocok untuknya.'
        );

        INSERT INTO public.scenario_hidden_facts (scenario_id, code, short_title, fact, sort_order, min_disclosure_level)
        VALUES
            (v_rina_id, 'H1', 'Pengalaman berjalan bersama anak', 'Bu Rina menikmati jalan santai bersama anaknya pada akhir pekan karena bisa mengobrol tanpa terasa seperti kewajiban olahraga, serta ingin menjadi contoh aktif bagi anaknya.', 1, 'medium'::public.disclosure_level),
            (v_rina_id, 'H2', 'Dukungan keluarga dan jadwal pasangan', 'Waktu pagi dan sore terasa padat karena urusan anak, namun suaminya pernah menawarkan menemani atau bergantian menjaga anak bila jadwal kerjanya memungkinkan.', 2, 'medium'::public.disclosure_level),
            (v_rina_id, 'H3', 'Rasa kecewa karena pola mulai lalu berhenti', 'Bu Rina merasa gagal ketika kebiasaan jalan pagi sebelumnya terhenti saat pekerjaan menumpuk, sehingga ragu membuat janji target rutin baru.', 3, 'high'::public.disclosure_level);

        INSERT INTO public.scenario_initial_states (
            scenario_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
            reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        ) VALUES (
            v_rina_id,
            'Berharap dapat lebih aktif, sekaligus ragu dan lelah',
            'Waktu serta tenaga terbatas setelah bekerja.',
            'medium'::public.disclosure_level,
            'Awal sesi; bersedia menceritakan kendala sehari-hari dan pengalaman aktivitas sebelumnya ketika ditanya secara terbuka.',
            'Ingin tubuh lebih segar dan tidak cepat lelah saat bermain dengan anak.',
            'Kelelahan sepulang kerja dan takut gagal menjaga konsistensi.',
            'both'::public.ambivalence_lean,
            false,
            NULL,
            NULL
        );
    END IF;

    -- =================================================================
    -- 5. SKENARIO 4: Sari Wulandari (SS-SAR-01), sesuai Ilustrasi final
    -- =================================================================
    SELECT id INTO v_sari_id FROM public.scenarios WHERE title = 'Ragu melanjutkan kuliah';
    IF v_sari_id IS NULL THEN
        INSERT INTO public.scenarios (title, owner_id, visibility, review_status, change_target)
        VALUES (
            'Ragu melanjutkan kuliah',
            v_owner_id,
            'catalog'::public.scenario_visibility,
            'draft'::public.review_status,
            'Mencari informasi dan mendaftar kuliah kelas karyawan.'
        )
        RETURNING id INTO v_sari_id;

        INSERT INTO public.scenario_personas (
            scenario_id, name, age, gender, education, occupation, marital_status,
            family_background, personality, communication_style, additional_background, avatar_file
        ) VALUES (
            v_sari_id,
            'Sari Wulandari',
            28,
            'Perempuan',
            'Pernah kuliah di program studi administrasi sampai semester 5, lalu berhenti.',
            'Staf administrasi di sebuah toko bahan bangunan dengan jadwal kerja bergilir (shift).',
            'Belum menikah.',
            'Tinggal bersama ibu. Kakak laki-lakinya sudah lulus kuliah dan bekerja di kantor. Kondisi ekonomi keluarga cukup untuk kebutuhan sehari-hari, tetapi tidak berlebih.',
            'Tekun bekerja, jarang menyampaikan keinginannya sendiri, dan cenderung meremehkan kemampuan dirinya.',
            'Pada awal pertemuan menjawab singkat dan datar; lebih banyak bercerita ketika merasa didengarkan.',
            'Beberapa teman seangkatannya sudah lulus. Rincian yang langsung terkait masalah dicatat dalam Kasus.',
            'girl3.glb'
        );

        INSERT INTO public.scenario_cases (
            scenario_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        ) VALUES (
            v_sari_id,
            'Sari ingin melanjutkan kuliah yang terhenti, tetapi ragu apakah ia sanggup menjalaninya sambil bekerja.',
            'Sekitar empat tahun lalu Sari berhenti kuliah pada semester 5 karena biaya dan memilih bekerja. Pekerjaannya sekarang terasa tidak berkembang: tugas dan posisinya sama selama beberapa tahun, dan ia merasa tertinggal dari teman-temannya.',
            'Harapan awal: ingin tahu apakah melanjutkan kuliah mungkin dilakukan dan dapat membuat pekerjaannya lebih baik. Konteks perubahan perilaku: mencari informasi dan mendaftar kuliah kelas karyawan.',
            'Tidak ada informasi kesehatan khusus.',
            'Sari, 28 tahun, bekerja sebagai staf administrasi di sebuah toko. Beberapa tahun lalu ia berhenti kuliah, dan belakangan ia mulai memikirkan untuk kuliah lagi. Ia datang untuk membicarakan hal itu. Arah latihan: bantu Sari memperjelas pandangannya tentang kuliah lagi dan langkah yang mungkin ia ambil, yaitu mencari informasi atau mendaftar kuliah kelas karyawan.'
        );

        INSERT INTO public.scenario_hidden_facts (scenario_id, code, short_title, fact, sort_order, min_disclosure_level)
        VALUES
            (v_sari_id, 'H1', 'Pertimbangan biaya dan waktu', 'Sari sudah menghitung kasar biaya kuliah kelas karyawan dan merasa tabungannya belum cukup. Ia juga khawatir penghasilannya berkurang jika jam kerjanya dikurangi untuk kuliah.', 1, 'medium'::public.disclosure_level),
            (v_sari_id, 'H2', 'Dukungan kakak', 'Kakaknya sudah lulus dan pernah menawarkan diri mencarikan informasi kelas karyawan. Sari belum menanggapi tawaran itu.', 2, 'medium'::public.disclosure_level),
            (v_sari_id, 'H3', 'Pernah membuka laman pendaftaran', 'Sari pernah membuka laman pendaftaran sebuah kampus, tetapi menutupnya sebelum selesai karena bingung harus mulai dari mana.', 3, 'medium'::public.disclosure_level),
            (v_sari_id, 'H4', 'Rasa malu dan takut gagal lagi', 'Sari malu karena dulu berhenti di tengah jalan. Ia takut gagal lagi dan dibandingkan dengan teman-temannya yang sudah lulus.', 4, 'high'::public.disclosure_level);

        INSERT INTO public.scenario_initial_states (
            scenario_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
            reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        ) VALUES (
            v_sari_id,
            'Ragu dan sedikit canggung',
            'Ingin membicarakan kuliah, tetapi belum yakin hal itu realistis.',
            'guarded'::public.disclosure_level,
            'Awal sesi; bersedia menyebutkan hal faktual tentang pekerjaan dan kuliahnya, belum menyampaikan perasaan pribadi.',
            'Ingin pekerjaan lebih baik dan menyelesaikan kuliah yang tertunda.',
            'Biaya, jadwal kerja bergilir, dan keraguan terhadap kemampuan diri.',
            'both'::public.ambivalence_lean,
            false,
            NULL,
            NULL
        );
    END IF;

    -- =================================================================
    -- 6. DATA UJI LOKAL: mahasiswa uji, admin uji, kelas uji, dan keanggotaan kelas
    -- Password KHUSUS PENGEMBANGAN: 'password123' (hash argon2id)
    -- =================================================================
    SELECT id INTO v_student_id FROM public.users WHERE lower(email) = 'mahasiswa.uji@safesesi.local' AND deleted_at IS NULL;
    IF v_student_id IS NULL THEN
        INSERT INTO public.users (name, email, role, password_hash, activated_at)
        VALUES (
            'Mahasiswa Uji (DEV)',
            'mahasiswa.uji@safesesi.local',
            'student'::public.user_role,
            '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            now()
        )
        RETURNING id INTO v_student_id;
    ELSE
        UPDATE public.users
        SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            activated_at = COALESCE(activated_at, now())
        WHERE id = v_student_id;
    END IF;

    SELECT id INTO v_admin_id FROM public.users WHERE lower(email) = 'admin.uji@safesesi.local' AND deleted_at IS NULL;
    IF v_admin_id IS NULL THEN
        INSERT INTO public.users (name, email, role, password_hash, activated_at)
        VALUES (
            'Admin Uji (DEV)',
            'admin.uji@safesesi.local',
            'admin'::public.user_role,
            '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            now()
        )
        RETURNING id INTO v_admin_id;
    ELSE
        UPDATE public.users
        SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            activated_at = COALESCE(activated_at, now())
        WHERE id = v_admin_id;
    END IF;

    -- Mahasiswa dari kampus lain: tanpa NPM, asal_institusi wajib terisi.
    SELECT id INTO v_external_id FROM public.users WHERE lower(email) = 'mahasiswa.luar@safesesi.local' AND deleted_at IS NULL;
    IF v_external_id IS NULL THEN
        INSERT INTO public.users (name, email, role, password_hash, activated_at)
        VALUES (
            'Mahasiswa Kampus Lain (DEV)',
            'mahasiswa.luar@safesesi.local',
            'student'::public.user_role,
            '$argon2id$v=19$m=65536,t=3,p=4$NizDYlQ2wPLLLwQqQzXorw$MH6Zlm0XEQkgLV/rPrHJV7ZtedftBXm+jVqopBIP6eI',
            now()
        )
        RETURNING id INTO v_external_id;
    END IF;

    -- Profil uji: nilai fiktif yang jelas bukan NPM/NIP asli.
    INSERT INTO public.students (user_id, npm, asal_institusi)
    VALUES (v_student_id, 'DEV-NPM-0001', NULL), (v_external_id, NULL, 'Kampus Fiktif (DEV)')
    ON CONFLICT (user_id) DO NOTHING;

    INSERT INTO public.lecturers (user_id, nip)
    VALUES (v_owner_id, 'DEV-NIP-0001')
    ON CONFLICT (user_id) DO NOTHING;

    SELECT id INTO v_class_id FROM public.classes WHERE name = 'Kelas Uji Pengembangan (DEV)' AND academic_year = '2026/2027' AND deleted_at IS NULL;
    IF v_class_id IS NULL THEN
        INSERT INTO public.classes (name, academic_year)
        VALUES ('Kelas Uji Pengembangan (DEV)', '2026/2027')
        RETURNING id INTO v_class_id;
    END IF;

    INSERT INTO public.class_members (class_id, user_id)
    SELECT v_class_id, u.id FROM (VALUES (v_student_id), (v_owner_id)) AS u(id)
    WHERE NOT EXISTS (
        SELECT 1 FROM public.class_members cm
        WHERE cm.class_id = v_class_id AND cm.user_id = u.id AND cm.deleted_at IS NULL
    );

    -- Skenario Nadia ditugaskan ke kelas uji oleh dosen Peneliti SafeSesi
    INSERT INTO public.class_scenarios (class_id, scenario_id, assigned_by)
    VALUES (v_class_id, v_nadia_id, v_owner_id)
    ON CONFLICT (class_id, scenario_id) DO NOTHING;

    -- =================================================================
    -- 7. DATA UJI LOKAL: skenario KHUSUS KELAS dan satu kelas lain tanpa mahasiswa uji
    -- Skenario kelas = salinan skenario Rina (isi klinis tidak ditulis ulang, disalin lewat SELECT)
    -- dengan visibility 'class': hanya terlihat oleh anggota kelas yang menerima penugasannya dan
    -- tidak pernah muncul di katalog umum. Kelas lain dipakai untuk menguji akses ditolak.
    -- =================================================================
    SELECT id INTO v_kls_id FROM public.scenarios
    WHERE title = 'Sulit rutin bergerak (Kelas Uji, DEV)' AND deleted_at IS NULL;
    IF v_kls_id IS NULL THEN
        INSERT INTO public.scenarios (title, owner_id, visibility, review_status, change_target)
        SELECT 'Sulit rutin bergerak (Kelas Uji, DEV)', owner_id, 'class'::public.scenario_visibility,
               review_status, change_target
        FROM public.scenarios WHERE id = v_rina_id
        RETURNING id INTO v_kls_id;

        INSERT INTO public.scenario_personas (
            scenario_id, name, age, gender, education, occupation, marital_status,
            family_background, personality, communication_style, additional_background, avatar_file
        )
        SELECT v_kls_id, name, age, gender, education, occupation, marital_status,
               family_background, personality, communication_style, additional_background, avatar_file
        FROM public.scenario_personas WHERE scenario_id = v_rina_id;

        INSERT INTO public.scenario_cases (
            scenario_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        )
        SELECT v_kls_id, main_problem, history_impact, expectation_change_context, health_condition, initial_summary
        FROM public.scenario_cases WHERE scenario_id = v_rina_id;

        INSERT INTO public.scenario_initial_states (
            scenario_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
            reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        )
        SELECT v_kls_id, emotion_type, emotion_cause, disclosure_level, disclosure_trigger,
               reasons_to_change, reasons_to_maintain, ambivalence_lean, discord_present, discord_context, discord_response
        FROM public.scenario_initial_states WHERE scenario_id = v_rina_id;

        INSERT INTO public.scenario_hidden_facts (scenario_id, code, short_title, fact, sort_order, min_disclosure_level)
        SELECT v_kls_id, code, short_title, fact, sort_order, min_disclosure_level
        FROM public.scenario_hidden_facts WHERE scenario_id = v_rina_id;
    END IF;

    INSERT INTO public.class_scenarios (class_id, scenario_id, assigned_by)
    VALUES (v_class_id, v_kls_id, v_owner_id)
    ON CONFLICT (class_id, scenario_id) DO NOTHING;

    SELECT id INTO v_other_class_id FROM public.classes
    WHERE name = 'Kelas Lain (DEV, tanpa mahasiswa uji)' AND academic_year = '2026/2027' AND deleted_at IS NULL;
    IF v_other_class_id IS NULL THEN
        INSERT INTO public.classes (name, academic_year)
        VALUES ('Kelas Lain (DEV, tanpa mahasiswa uji)', '2026/2027')
        RETURNING id INTO v_other_class_id;
    END IF;

    INSERT INTO public.class_members (class_id, user_id)
    SELECT v_other_class_id, v_owner_id
    WHERE NOT EXISTS (
        SELECT 1 FROM public.class_members cm
        WHERE cm.class_id = v_other_class_id AND cm.user_id = v_owner_id AND cm.deleted_at IS NULL
    );

    INSERT INTO public.class_scenarios (class_id, scenario_id, assigned_by)
    VALUES (v_other_class_id, v_kls_id, v_owner_id)
    ON CONFLICT (class_id, scenario_id) DO NOTHING;

    RAISE NOTICE 'Seed skenario berhasil disiapkan secara idempotent.';
END $$;
