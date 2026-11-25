# backend/evals — alat ukur ketepatan dan perilaku LLM

Folder ini berisi alat untuk **mengukur** seberapa tepat dan seberapa stabil komponen LLM SafeSesi
bekerja, untuk kebutuhan pengembangan dan skripsi. Isinya tidak dipakai aplikasi saat berjalan.

> ⚠️ **Skrip di `scripts/` memanggil Gemini sungguhan dan memakan kuota**, kecuali dijalankan
> dengan `--dry-run` atau berupa pembangun fixture (`build_*`, `replay_state_ilustrasi.py
> build-fixture`). `sim_timing.py` juga **menulis ke database** di `DATABASE_URL`. Jangan
> jalankan skrip-skrip ini di CI. Skrip pembanding MITI menolak jalan saat `APP_ENV=production`
> kecuali diberi `--allow-production`.

## Bedanya dengan folder lain

| Folder | Isi | Kapan dipakai |
| --- | --- | --- |
| `backend/services/evaluation/` | **Fitur aplikasi**: pipeline yang menilai sesi mahasiswa dengan MITI 4.2.1 (agen LLM, aturan penghitungan, ukuran ringkasan). | Saat aplikasi berjalan (`POST /sessions/{id}/evaluation`). |
| `backend/evals/` | **Alat ukur** untuk fitur di atas dan simulator: membandingkan hasil LLM dengan label dokumen/ahli, replay Peran A, serta pengukuran latensi. | Dijalankan manual oleh peneliti. |
| `backend/tests/` | Tes otomatis yang cepat dan deterministik, dengan Gemini dan database di-mock, memakai fixture kecil buatan sendiri. Tidak bergantung pada apa pun di `backend/evals/`. | Setiap perubahan, dan di GitHub Actions. |
| `backend/evals/tests/` | Tes untuk skrip evals dan konsistensi fixture (mis. frekuensi kode fixture Ilustrasi cocok dengan tabel dokumen). Tanpa Gemini. | Manual, setelah mengubah skrip atau fixture evals. |

## Struktur

```
backend/evals/
  scripts/
    compare_miti_fixtures.py       # evaluator MITI sungguhan vs fixture (Gemini)
    miti_fixtures.py               # pemuat fixture untuk skrip dan evals/tests
    build_ilustrasi_miti_fixtures.py
    build_casaa_fixtures.py
    replay_state_ilustrasi.py      # replay Peran A (Gemini); build-fixture tanpa Gemini
    sim_timing.py                  # simulasi latensi giliran (Gemini + database)
  fixtures/
    ilustrasi/                     # di-commit: SS-*.json (MITI) + ilustrasi_state_sessions.json (replay)
    casaa/                         # TIDAK di-commit (hak cipta CASAA); bangun sendiri
  results/                         # hasil run compare_miti_fixtures.py
  tests/
```

## Fixture

**Ilustrasi** (di-commit) dibangun dari `docs/Ilustrasi_Sesi_dan_Evaluasi_SafeSesi_final.docx`:

```powershell
backend/venv/Scripts/python backend/evals/scripts/replay_state_ilustrasi.py build-fixture
backend/venv/Scripts/python backend/evals/scripts/build_ilustrasi_miti_fixtures.py
```

**CASAA** tidak di-commit karena hak cipta CASAA. Bangun di setiap mesin dari PDF di
`docs/coded-transcript-miti/`. Pembangun ini membutuhkan `pdftotext` (xpdf/poppler) di PATH:

```powershell
backend/venv/Scripts/python backend/evals/scripts/build_casaa_fixtures.py
backend/venv/Scripts/python backend/evals/scripts/build_casaa_fixtures.py --only smoker --show 10
```

Target perubahan ketiga transkrip CASAA ditetapkan peneliti (`change_target_assumed: true`), karena
transkrip aslinya tidak mencantumkan target. Isi fixture mana pun **tidak boleh** dipakai sebagai
contoh di prompt; `evals/tests/test_evals_fixtures.py` memeriksa hal ini.

## Menjalankan pembanding MITI

Jalankan dari root repo:

```powershell
# Perkiraan jumlah panggilan dan token, tanpa memanggil Gemini
backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --dry-run --set all --sessions all

# Default: satu sesi (SS-NAD-01-S01)
backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py

# Ketiga transkrip CASAA
backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --set casaa --sessions all

# Uji sensitivitas target perubahan Emmy
backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --set casaa --sessions casaa_emmy `
    --change-target-override 'casaa_emmy=return to work'

# Semua fixture, thinking dimatikan, hanya Behavior Coding Agent
backend/venv/Scripts/python backend/evals/scripts/compare_miti_fixtures.py --set all --sessions all `
    --thinking-budget 0 --agents behavior_coding
```

Hasil lengkap (per volley, per kode, skor global, durasi, panggilan API, dan token per agen)
ditulis ke `backend/evals/results/<tanggal-jam>_<set>_<model>_tb<budget>.json`. Lokasinya bisa
diganti dengan `--output`. Hasil run CASAA memuat kutipan transkrip CASAA, jadi jangan di-commit.

## Menjalankan evals/tests

Tes ini tidak ikut terkumpul oleh `python -m pytest` dari root (`pytest.ini` hanya mengumpulkan
`backend/tests`). Jalankan secara eksplisit:

```powershell
backend/venv/Scripts/python -m pytest backend/evals/tests
```

Tes CASAA otomatis dilewati jika fixture CASAA belum dibangun.
