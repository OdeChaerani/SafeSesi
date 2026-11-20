# SafeSesi Backend Refactoring Plan (Spesifikasi Sistem Alignment)

Dokumen ini disusun sebagai luaran **Fase 0 (Audit dan Rencana)** dalam rangka menyelaraskan backend SafeSesi dengan dokumen acuan final:
1. **Spesifikasi Sistem SafeSesi, khususnya Bagian 6.1.2–6.1.4 dan Lampiran 1–3.
2. **Pedoman Penilaian dan Rubrik SafeSesi v3** (`docs/Rubrik_Penilaian_SafeSesi.docx`).
3. **Ilustrasi Sesi Simulasi dan Evaluasi SafeSesi Final v6** (`docs/Ilustrasi_Sesi_dan_Evaluasi_SafeSesi.docx`).
4. **Database Schema PostgreSQL SafeSesi** (`docs/schema.sql`).

---

## 1. Audit Komponen Lama

Berikut adalah hasil audit menyeluruh terhadap kode lama di `backend/` sebelum refactoring:

| Komponen / Berkas Lama | Status | Alasan Berdasarkan Spesifikasi Sistem / Dokumen Acuan |
| :--- | :--- | :--- |
| **`backend/data/demo_case.py`** | **Dihapus** | Skenario demo statis (Rani) dan profil Big Five dihapus total. Spesifikasi Sistem Lampiran 1 menegaskan bahwa karakteristik pribadi menggunakan deskripsi konkret tanpa profil Big Five. Seluruh skenario bersumber dari database (`scenarios`, `scenario_personas`, `scenario_cases`, `scenario_initial_states`, `scenario_hidden_facts`). |
| **`backend/schemas/client_state.py`** | **Diganti Total** | State lama menggunakan skor numerik Chen (willingness 1–5, depth 1–5), skala numerik ambivalensi (1–5), dan discord (1–5). Menurut Spesifikasi Sistem 6.1.4.B & Lampiran 2, Client State bersifat kualitatif sesuai kolom tabel `client_state_log`: `emotion_type`, `emotion_cause`, `disclosure_level` (enum: guarded, medium, high), `disclosure_trigger`, `reasons_to_change`, `reasons_to_maintain`, `ambivalence_lean` (enum: toward_change, toward_status_quo, both), `discord_present` (boolean), `discord_context`, dan `discord_response`. |
| **`backend/schemas/scenario.py`** | **Diganti Total** | Model lama memuat Big Five dan struktur CARE-Bench yang belum diadaptasi. Diganti model yang mencerminkan skema database: `Persona` (10 isian), `Case` (5 isian), `HiddenFact`, `InitialState`, dan `ScenarioSnapshot` (sesuai fungsi SQL `build_scenario_snapshot`). |
| **`backend/schemas/session.py`** | **Diganti** | Model lama memuat `TurnEvaluation` (Clinical Supervisor per giliran: skor empati, refleksi, saran). Spesifikasi Sistem 6.1.4.E menegaskan penilaian MITI dan umpan balik hanya dilakukan **setelah sesi berakhir** (`evaluations`), bukan per turn. Request/response sesi dan giliran diselaraskan dengan kontrak baru (turn response hanya memuat `turn_no` dan ucapan klien, tanpa membocorkan state internal kepada mahasiswa). |
| **`backend/services/state_engine.py`** | **Dihapus Total** | Rumus akumulasi skor keterbukaan Chen, threshold numerik, dan Heuristic Fallback Evaluator dihapus. Spesifikasi Sistem Lampiran 2 menegaskan kondisi klien dinilai secara kontekstual kualitatif oleh LLM (Peran A, State Updater), bukan melalui rumus matematika akumulasi skor per giliran. |
| **`backend/services/gemini_service.py`** | **Diganti Total** | Arsitektur lama menggabungkan evaluasi klinis per turn dan generasi respon. Diganti dengan wrapper client async terisolasi (`backend/services/llm/`) yang mendukung structured output via Pydantic (`client.aio.models.generate_content`) dan arsitektur 3 peran (`services/simulation/`): Peran A (State Updater), Peran B (Client Responder), dan Peran C (Notes Updater). |
| **`backend/services/intent_service.py`** | **Dipertahankan & Dimodifikasi** | Logika klasifikasi sapaan dipertahankan di balik fitur flag `GREETING_SHORTCUT_ENABLED`. Dihapus bagian evaluasi empati; cukup memberikan balasan sopan statis tanpa memanggil LLM, menyalin state tanpa perubahan, serta mencatat turn dan `client_state_log`. |
| **`backend/supabase_client.py`** | **Diganti Total** | Akses DB via `supabase-py` (REST PostgREST) diganti dengan koneksi PostgreSQL langsung (`asyncpg` pool di lifespan FastAPI) agar penulisan turn konselor, turn klien, `client_state_log`, dan `topic_notes_log` dapat dieksekusi dalam **satu transaksi database atomik**. Modul dipecah menjadi `repositories/` per agregat. |
| **`backend/api/sessions.py`** (dahulu `api/v1/sessions.py`) | **Diganti Total** | Mengganti in-memory store dengan transaksi PostgreSQL, menambahkan locking `asyncio.Lock` per `session_id`, penanganan snapshot skenario, session topics, dan endpoint `POST /api/v1/sessions/{id}/end`. |
| **`backend/api/system.py`** (dahulu `api/v1/system.py`) | **Dimodifikasi** | Endpoint `/health` disesuaikan untuk menjalankan query ringan `SELECT 1` langsung via asyncpg connection pool. |
| **`backend/main.py`** | **Dimodifikasi** | Disederhanakan untuk mengelola lifespan (inisialisasi & penutupan pool `asyncpg`), konfigurasi via `core/config.py`, registrasi router dari `api/` (dipasang di prefix `/api/v1`), dan middleware CORS. |
| **`backend/tests/`** | **Diganti Total** | Tes lama yang menguji willingness numerik dan TurnEvaluation dihapus. Digantikan dengan test suite berbasis `FakeLLM` (menguji transaksi atomik, locking turn, isolasi kepemilikan sesi mahasiswa, snapshot immutability, replay Nadia S01 & S02, serta replay Hendra dan Rina). |

---

## 2. Pemeriksaan Dokumen Final & Data 3 Skenario Lengkap

Pemeriksaan dokumen final `docs/Ilustrasi_Sesi_dan_Evaluasi_SafeSesi.docx` (v6) memastikan seluruh data skenario dan sesi konseling telah tersedia secara akurat:

### 2.1 Rangkuman Master 3 Skenario
| Atribut | Skenario 1 (Nadia) | Skenario 2 (Hendra) | Skenario 3 (Rina) |
| :--- | :--- | :--- | :--- |
| **Kode Skenario** | `SS-NAD-01` | `SS-HEN-01` | `SS-RIN-01` |
| **Nama Klien** | **Nadia Maharani** (nama fiktif) | **Hendra Saputra (Mas Hendra)** | **Rina Kusumawati (Bu Rina)** |
| **Profil Demografis** | 19 tahun, Perempuan, Mahasiswi psikologi semester 3, Mahasiswi penuh waktu, Belum menikah | 27 tahun, Laki-laki, Lulusan SMA, Pedagang toko kelontong kecil, Belum menikah (merencanakan pernikahan) | 36 tahun, Perempuan, Pendidikan tidak diisi (tidak relevan), Karyawan dan ibu, Menikah (1 anak) |
| **Target Perubahan (`change_target`)** | Membagi atau membatasi tanggung jawab tambahan agar sesuai kemampuan dan waktu | Mengurangi atau menghentikan kebiasaan merokok | Memulai aktivitas berjalan kaki secara bertahap sesuai ketersediaan waktu |
| **Jumlah Hidden Facts** | **4 fakta** | **3 fakta** | **3 fakta** |
| **Daftar Judul Hidden Facts** | 1. `H1`: Kekhawatiran terhadap penilaian teman<br>2. `H2`: Pengalaman komentar kurang kompak<br>3. `H3`: Pengalaman meminta bantuan desain<br>4. `H4`: Pengalaman bersama orang tua soal tanggung jawab | 1. `H1`: Kekhawatiran gelisah dan fokus kerja<br>2. `H2`: Pengalaman mencoba mengurangi<br>3. `H3`: Kekhawatiran terhadap rencana pernikahan | 1. `H1`: Pengalaman berjalan bersama anak<br>2. `H2`: Dukungan keluarga dan jadwal pasangan<br>3. `H3`: Rasa kecewa karena pola mulai lalu berhenti |
| **Kondisi Awal (Emotion)** | Cemas dan kewalahan karena tenggat kuliah serta kegiatan organisasi bertumpuk | Kesal dan waspada karena merasa kebiasaannya terus dipermasalahkan calon istri | Berharap dapat lebih aktif, sekaligus ragu dan lelah karena waktu & tenaga terbatas |
| **Kondisi Awal (Disclosure)** | `guarded` (Terbatas) | `guarded` (Terbatas) | `medium` (Sedang) |
| **Kondisi Awal (Ambivalence)** | `both` (Kedua sisi sama kuat) | `toward_status_quo` (Mempertahankan keadaan dominan) | `both` (Dua sisi berimbang) |
| **Kondisi Awal (Discord)** | `false` (Tidak tampak) | `false` (Tidak tampak) | `false` (Tidak tampak) |
| **Daftar Sesi Ilustratif** | **2 Sesi**:<br>• `SS-NAD-01-S01` (Sesi 1: 10 giliran K01–K10)<br>• `SS-NAD-01-S02` (Sesi 2 Lanjutan: 10 giliran K01–K10) | **1 Sesi**:<br>• `SS-HEN-01-S01` (Sesi 1: 10 giliran K01–K10) | **1 Sesi**:<br>• `SS-RIN-01-S01` (Sesi 1: 10 giliran K01–K10) |

---

## 3. Rencana Kerja Fase 1 – 4

### Fase 1: Struktur dan Lapisan Data
Target struktur folder:
```text
backend/
├── main.py
├── core/              # config (pydantic-settings), security (stub dev), errors
├── api/
│   ├── deps.py        # get_db, get_current_user (stub dev), require_role, cek kepemilikan
│   └── *.py           # system, sessions, scenarios (auth/classes/evaluations: stub); URL tetap di prefix /api/v1
├── schemas/           # persona, case, initial_state, snapshot, session, turn
├── repositories/      # users, scenarios, sessions, turns, client_state, topics
├── services/
│   ├── simulation/    # orchestrator, state_updater, responder, notes_updater, intent
│   ├── evaluation/    # kerangka kosong + TODO (Spesifikasi Sistem 6.1.4.E, Rubrik)
│   ├── observations/  # kerangka kosong + TODO (vokal, wajah)
│   └── llm/           # client Gemini async + parsing output terstruktur
├── prompts/           # prompt A/B/C, diberi konstanta versi
└── tests/
db/                    # schema.sql (salinan), seed_scenarios.sql
```
Langkah pengerjaan:
1.  **Konfigurasi (`core/config.py`)**:
    *   Membuat model `Settings` dengan `pydantic-settings`: `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL_STATE`, `GEMINI_MODEL_RESPONDER`, `GEMINI_MODEL_NOTES`, `NOTES_UPDATE_MODE` (inline/background, default inline), `GREETING_SHORTCUT_ENABLED` (default true), `DEBUG_INCLUDE_INTERNAL` (default false), `CORS_ORIGINS`.
2.  **Koneksi Database Langsung (`asyncpg`)**:
    *   Membuat connection pool `asyncpg` di lifespan FastAPI (`main.py`).
    *   Mengatur `statement_cache_size=0` untuk kompatibilitas Supabase Transaction Pooler (PgBouncer).
    *   Menghapus dependensi `supabase-py`. Endpoint `/health` cukup `SELECT 1`.
3.  **Lapisan Repository (`repositories/`)**:
    *   Memecah fungsi database menjadi repositori per agregat: `users.py`, `scenarios.py`, `sessions.py`, `turns.py`, `client_state.py`, `topics.py`. SQL berparameter tanpa f-string.
4.  **Tulis Ulang Schemas (`schemas/`)**:
    *   `schemas/scenario.py`: `Persona` (10 isian), `Case` (5 isian), `HiddenFact`, `InitialState`, `ScenarioSnapshot`.
    *   `schemas/client_state.py`: Kolom sama persis dengan tabel `client_state_log`.
    *   `schemas/session.py`: Request dan response pembuatan sesi dan giliran percakapan.
5.  **Autentikasi & Otorisasi Dev (`api/deps.py`)**:
    *   `get_current_user` membaca header `X-Dev-User-Id` (diberi tanda `TODO: JWT`).
    *   Pemeriksaan hak kepemilikan sesi (mahasiswa hanya boleh mengakses sesinya sendiri).
6.  **Pembersihan Kode Lama**:
    *   Menghapus `backend/data/` (`demo_case.py`), profil Big Five, dan semua referensi terkait.
7.  **Penyusunan Seed Data (`db/seed_scenarios.sql`)**:
    *   Menulis script SQL idempotent berisi akun peneliti (`role='lecturer'`, `password_hash=NULL`) sebagai pemilik.
    *   Mengisi **3 skenario lengkap** (Nadia Maharani, Hendra Saputra, Rina Kusumawati): persona, kasus, hidden facts, kondisi awal, `visibility='catalog'`, `review_status='draft'`.
    *   *Catatan*: Script tidak dijalankan sebelum persetujuan pengguna.

---

### Fase 2: Pembuatan Sesi (`POST /api/v1/sessions`)
Endpoint: `POST /api/v1/sessions` dengan body `{scenario_id, class_id?, mode: "new"|"repeat"|"continue", parent_session_id?}`.
Semua langkah dalam **SATU transaksi PostgreSQL**:
1.  **Validasi Hak Akses**:
    *   Latihan mandiri (`class_id` NULL): skenario harus `visibility='catalog'` dan `deleted_at IS NULL`.
    *   Latihan kelas (`class_id` terisi): mahasiswa harus terdaftar di `class_members` dan skenario ada di `class_scenarios`.
    *   Mode `continue`: `parent_session_id` harus milik mahasiswa yang bersangkutan dan memiliki `scenario_id` yang sama.
2.  **Pembuatan Snapshot Skenario**:
    *   Eksekusi `scenario_snapshot = SELECT build_scenario_snapshot(:scenario_id)`. Simulator hanya membaca snapshot ini.
3.  **Inisialisasi Topik Pembahasan (`session_topics`)**:
    *   Dibuat **sekali** di awal sesi (tidak bertambah selama sesi):
        *   "Permasalahan utama" (`source='main_problem'`)
        *   "Riwayat dan dampak masalah" (`source='history_impact'`, lewati jika kosong)
        *   "Harapan dan arah perubahan" (`source='expectation_change_context'`)
        *   Satu topik per hidden fact menggunakan `short_title` (`source='hidden_fact'`, `hidden_fact_code='H1'`, dst.).
4.  **Inisialisasi State & Catatan Awal**:
    *   Mode `new`/`repeat`: isi baris awal `client_state_log` (`turn_id=NULL`) dari `scenario_initial_states`, dan `topic_notes_log` awal (`turn_id=NULL`, `description=''`) untuk setiap topik.
    *   Mode `continue`: salin baris state terakhir dan catatan topik terakhir milik parent session.
5.  **Endpoint Pendamping**:
    *   `POST /api/v1/sessions/{id}/end`: ubah status `completed`, isi `ended_at = now()`, hitung `duration_seconds`.
    *   `GET /api/v1/sessions/{id}`: mengambil detail sesi beserta daftar turns.

---

### Fase 3: Pipeline Turn Percakapan Sesuai Spesifikasi Sistem
Endpoint: `POST /api/v1/sessions/{id}/turns` dengan body `{content, start_ms?, end_ms?}` (sesi harus `in_progress`, diproses bergantian dengan `asyncio.Lock` per `session_id`):
1.  **Pemuatan Konteks**:
    *   Muat snapshot, state terakhir, catatan topik terkini (baris terbaru per topik), dan riwayat transkrip (untuk sesi lanjutan sertakan transkrip parent).
2.  **Bypass Sapaan (`GREETING_SHORTCUT_ENABLED`)**:
    *   Jika ucapan berupa sapaan statis tanpa substansi: kembalikan respon santun statis tanpa LLM, salin state sebelumnya ke `client_state_log`, simpan turn konselor dan klien dalam 1 transaksi.
3.  **Peran A: State Updater (LLM)**:
    *   Input: Ucapan konselor, Client State terakhir, persona & kasus, riwayat transkrip.
    *   Output: Structured JSON tervalidasi Pydantic sesuai kolom `client_state_log` (`emotion_type`, `emotion_cause`, `disclosure_level`, `disclosure_trigger`, `reasons_to_change`, `reasons_to_maintain`, `ambivalence_lean`, `discord_present`, `discord_context`, `discord_response`).
    *   Aturan kualitatif sesuai Spesifikasi Sistem Lampiran 2 (tidak ada rumus skor angka).
4.  **Peran B: Client Responder (LLM)**:
    *   Input: Persona, kasus, state BARU (Peran A), catatan topik terkini, riwayat percakapan, ucapan konselor.
    *   *Pembatasan Kode (Code Boundary)*: hidden facts disaring di kode sebelum memanggil LLM. Aturan lengkap ada di bagian 6, "Aturan Disclosure dan Discord yang Berlaku".
    *   Output: Ucapan klien (teks) dalam Bahasa Indonesia.
5.  **Persistensi Atomik 1 Transaksi**:
    *   Simpan sekaligus dalam 1 transaksi database:
        1. Turn konselor (`speaker='counselor'`).
        2. Turn klien (`speaker='client'`).
        3. `client_state_log` baru (`turn_id = id_turn_klien`).
    *   Jika Peran A atau B gagal (retry 1x): transaksi di-rollback, state tidak berubah, balas HTTP 503 pesan Bahasa Indonesia.
6.  **Peran C: Notes Updater (LLM)**:
    *   Input: Daftar topik, deskripsi saat ini, ucapan konselor, dan respons riil yang diucapkan klien.
    *   Output: Topik-topik yang mengalami pembaruan pembahasan. Simpan ke `topic_notes_log` (`turn_id = id_turn_klien`).
7.  **Respon API Tanpa Kebocoran Informasi**:
    *   Respons hanya mengembalikan `turn_no` dan ucapan klien (`content`). State internal, catatan topik, dan hidden facts tidak dibocorkan, kecuali `DEBUG_INCLUDE_INTERNAL=true`.

---

### Fase 4: Pengujian dan Verifikasi
1.  **Unit & Integrasi Test dengan `FakeLLM`**:
    *   Persistensi turn konselor, turn klien, dan `client_state_log` dalam 1 transaksi atomik (rollback jika gagal).
    *   Konsistensi nomor urut turn (`turn_no`).
    *   Snapshot immutability (perubahan pada skenario master tidak memengaruhi sesi aktif).
    *   Inisialisasi baris awal state & notes pada mode `new`, `repeat`, dan `continue`.
    *   Kontrol akses (mahasiswa A tidak bisa membaca/mengirim turn ke sesi milik mahasiswa B).
    *   Tidak ada kebocoran state atau hidden facts di respons API mahasiswa.
2.  **Tes Khusus Mode `continue` (Nadia S01 $\rightarrow$ S02)**:
    *   Menjalankan sesi S01 hingga selesai (`POST /api/v1/sessions/{id}/end`).
    *   Membuat sesi baru dengan `mode: "continue", parent_session_id: s01_id`.
    *   Memvalidasi:
        *   Baris awal `client_state_log` S02 menyalin persis state akhir S01 (Emotion: cemas tetapi lebih terarah; Disclosure: `medium`; Ambivalence: `both`; Discord: `false`).
        *   Baris awal `topic_notes_log` S02 menyalin catatan topik terakhir dari S01.
        *   Transkrip dari S01 otomatis disertakan ke konteks riwayat percakapan prompt LLM pada S02.
3.  **Tes Replay Dokumen Ilustrasi (`@pytest.mark.llm`)**:
    *   Replay percakapan Nadia S01 K01–K10 untuk memeriksa transisi kunci kualitatif:
        *   Setelah K06 (saran sepihak): Discord muncul (`discord_present=true`). Disclosure tetap `medium` (tidak turun), dan klien menjawab singkat tanpa informasi baru.
        *   H2 dan H4 (tingkat minimal `high`) tidak muncul selama sesi 1 karena Disclosure hanya mencapai `medium`.
    *   Replay percakapan Nadia S02 K01–K10 untuk memeriksa kesinambungan eksplorasi pembagian tugas.
4.  **Pembersihan**:
    *   Menghapus pengujian lama berbasis skor numerik Chen. Memastikan `pytest` dan linter hijau.

---

## 4. Daftar Pertanyaan Terbuka (`TODO(tanya)`)

1.  **TODO(tanya: waktu ujaran turn berbasis teks)**:
    *   Tabel `turns` memiliki kolom wajib `start_ms` dan `end_ms` (integer). Pada antarmuka chat teks saat ini, waktu ms audio mentah belum ada.
    *   *Rencana*: Backend menyetel default `start_ms = 0` dan `end_ms = 0` (atau estimasi durasi pembacaan berdasarkan jumlah kata jika tidak dikirim frontend).
2.  **TODO(tanya: konkurensi multi-worker)**:
    *   Penguncian antrean giliran percakapan per sesi saat ini menggunakan `asyncio.Lock` di memori (asumsi 1 worker instance Uvicorn). Jika di masa depan dijalankan dengan multi-worker, diperlukan distributed locking (misalnya PostgreSQL advisory lock via `pg_advisory_xact_lock(session_id)`). Untuk fase saat ini menggunakan `asyncio.Lock` in-memory.
3.  **TODO(tanya: format branch git)**:
    *   Lingkungan sandbox Windows AppContainer secara default memproteksi folder `.git` (write denied pada `.git/refs/heads`). Perintah pembuatan branch `refactor/spec-alignment` dapat dijalankan langsung oleh pengguna di terminal lokal (`git checkout -b refactor/spec-alignment`).

---

## 5. Ringkasan Status

Fase 1–4 sudah diimplementasikan. Router dipindah dari `backend/api/v1/` ke `backend/api/`, dan URL tetap di prefix `/api/v1`. Dokumen acuan sekarang adalah `docs/BRD_SafeSesi_final.docx` dan `docs/Ilustrasi_Sesi_dan_Evaluasi_SafeSesi_final.docx`. Data skenario pada bagian 2 berasal dari Ilustrasi v6 dan perlu dicek ulang terhadap Ilustrasi final.

Tes dijalankan dari root repo dengan `python -m pytest` (konfigurasi di `pytest.ini`). CI memakai perintah yang sama.

---

## 6. Aturan Disclosure dan Discord yang Berlaku

Acuan: BRD final Lampiran 1–2 dan Ilustrasi final. Semua aturan ditegakkan di kode, tidak bergantung pada LLM.

| Aturan | Implementasi |
| :--- | :--- |
| Urutan tingkat: `guarded` < `medium` < `high`. | `services/simulation/disclosure.py` (`DISCLOSURE_ORDER`) |
| Setiap fakta tersembunyi punya `min_disclosure_level` (kolom `scenario_hidden_facts`, default `medium`). Fakta masuk prompt Peran B hanya jika tingkat saat ini ≥ tingkat minimal fakta. | `filter_hidden_facts`, dipanggil di `responder.py` |
| Saat `discord_present = true`, hanya fakta yang **sudah terungkap** yang masuk prompt. Fakta dianggap sudah terungkap jika topik `session_topics` dengan `hidden_fact_code` yang sama punya deskripsi tidak kosong pada catatan terbaru di `topic_notes_log`. | `filter_hidden_facts` + `revealed_fact_codes` |
| Disclosure **tidak pernah turun**: tingkat baru = max(sebelumnya, hasil LLM). Jika LLM mengembalikan tingkat lebih rendah, nilainya dikoreksi dan dicatat sebagai warning. | `resolve_disclosure` di `state_updater.py` |
| Saat Discord tampak, Disclosure **tetap** pada tingkat sebelumnya (tidak naik, tidak turun). Klien menjawab lebih singkat dan tidak mengungkap informasi baru. | `resolve_disclosure`; instruksi di `prompt_a_state.py` (v1.2.0) |
| Nilai tingkat yang tidak dikenal diperlakukan tertutup (fakta tidak dikirim, tingkat sebelumnya dipertahankan). | `disclosure.py` |

### Data yang dikirim ke frontend

- Katalog, briefing, dan respons sesi hanya memuat ringkasan publik (`PublicScenarioInfo`): judul, `change_target`, `initial_summary` (kolom `scenario_cases`), dan nama/usia/gender/peran klien. Hidden facts, persona lengkap, isi kasus, dan client state tidak pernah dikirim.
- `GET /api/v1/sessions/{id}`: `topics` (topik sesi ini) hanya untuk dosen/admin. `previous_topics` berisi catatan topik sesi induk. Mahasiswa hanya menerima topik yang deskripsi terakhirnya tidak kosong (nama + deskripsi). Sesi tanpa induk mengirim `[]`.
- `GET /api/v1/sessions/{id}/briefing-topics`: dipakai halaman briefing mode continue sebelum sesi lanjutan dibuat (`{id}` = calon `parent_session_id`). Filternya sama, dan hanya untuk pemilik sesi atau dosen/admin.

---

## 7. Pemakaian Koneksi Database — Wajib Diuji di Load Testing (target 40 pengguna bersamaan)

Sejak Peran C dijalankan di background dengan advisory lock per sesi (`services/simulation/turn_lock.py`), satu giliran memakai koneksi pool sebagai berikut:

| Koneksi | Dipegang selama | Perkiraan durasi (pengukuran 12 Nov 2026) |
| :--- | :--- | :--- |
| Koneksi request (`get_db`) | Seluruh request: muat data, Peran A, Peran B, simpan | ~7 detik |
| Koneksi lock (`DbTurnLock`) | Dari awal giliran sampai Peran C selesai dan catatan topik ter-commit | ~7 detik + Peran C (~1,3 detik dengan `gemini-3.5-flash-lite`) |
| Koneksi autentikasi (`get_current_user`) | Sebentar, satu query | <0,2 detik |

Jadi **2 koneksi per giliran yang sedang berjalan**, dan lock ditahan **sampai Peran C selesai**, bukan hanya sampai respons terkirim. Pool asyncpg dibuat dengan **`max_size=10` per worker** (`backend/main.py`).

Perkiraan kasar untuk 40 pengguna bersamaan, dengan satu giliran per ~66 detik per pengguna (10 giliran dalam ~11 menit pada Ilustrasi): 40 × (~7 + ~8,3 detik-koneksi) / 66 ≈ **9 koneksi terpakai rata-rata**. Angka ini sudah di batas `max_size=10` satu worker, sehingga lonjakan (beberapa pengguna mengirim bersamaan) akan membuat request menunggu `pool.acquire()`. `acquire()` sekarang tidak memakai batas waktu.

Yang harus diukur saat load testing:
- p50/p95 waktu respons giliran, `lock_wait_ms`, dan waktu tunggu `pool.acquire()` (log `safesesi.timing`).
- Jumlah respons 409 (lock giliran timeout) dan 503 (LLM).
- Jumlah koneksi aktif vs. `max_size` × jumlah worker, dan batas koneksi Supavisor/Supabase untuk paket yang dipakai (mode session, port 5432).
- Laju permintaan ke Gemini: 3 panggilan per giliran (≈ 40 × 3 / 66 ≈ 2 per detik, lebih tinggi saat lonjakan) terhadap kuota RPM/TPM tiap model.

Opsi jika pool menjadi hambatan (belum diimplementasikan): menaikkan `max_size` sesuai batas Supabase, menambah worker, memberi timeout pada `pool.acquire()`, atau melepas koneksi request selama Peran A/B berjalan dan meminjamnya lagi hanya untuk muat data dan simpan.

---

## 8. Masalah yang Diketahui

- **Dosen bisa membuka sesi di luar kelasnya.** `verify_session_ownership` (`backend/api/deps.py`) meloloskan semua pengguna ber-role `lecturer`/`admin` tanpa memeriksa kelas, sehingga endpoint sesi (`GET /sessions/{id}`, briefing-topics, dll.) dapat dibuka dosen untuk sesi kelas lain. Endpoint evaluasi (`/sessions/{id}/evaluation`) sudah memakai cek yang lebih ketat lewat `v_sessions_for_lecturer`. Akan dibatasi saat inkremen login dan role.
- **Evaluasi berjalan sebagai tugas background di proses aplikasi.** Jika server restart di tengah evaluasi, baris `evaluations` tertinggal berstatus `running`; setelah 15 menit tanpa perubahan, evaluasi itu dianggap macet dan `POST /sessions/{id}/evaluation` boleh menjalankannya ulang. Evaluasi lama yang ternyata masih berjalan setelah 15 menit dapat ikut menyimpan hasil; penyimpanan terakhir yang menang (hasil lama dihapus di transaksi yang sama).
