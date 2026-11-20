# Perbedaan Manual MITI 4.2.1 dengan Rubrik dan Ilustrasi SafeSesi

Dokumen ini mencatat bagian pengodean yang berbeda atau tidak diatur tegas di antara:

- **Manual**: Moyers, Manuel, & Ernst (2015), *MITI Coding Manual 4.2.1*
- **Rubrik**: Pedoman Penilaian dan Rubrik SafeSesi (final)
- **Ilustrasi**: Ilustrasi Sesi Simulasi dan Evaluasi SafeSesi (final), lima sesi contoh
- **CASAA**: tiga transkrip latihan MITI 4 yang dikodekan ahli (smoker, Emmy, Cheryl)

Prinsip sistem: **manual diikuti**. Kasus yang tidak diatur tegas oleh manual diisi dengan
keputusan peneliti, dan keputusan itu ditandai `PENGISIAN CELAH` di kode
(`backend/services/evaluation/miti_rules.py`). Label di fixture Ilustrasi dan CASAA disimpan
apa adanya, tidak diubah agar cocok dengan sistem.

Status setiap butir: **perlu ditinjau ahli**.

---

## A. Keputusan pengisian celah (manual tidak memberi aturan tegas)

### A1. Ragu antara Confront dan Persuade
- **Manual (E.4.g.3):** jika Persuade dan Confront tumpang tindih, Confront dipakai. Manual tidak
  memberi default untuk kasus ragu. Aturan "jika ragu pakai kode yang lebih rendah" hanya
  dinyatakan untuk MIA (E.4.f.1).
- **Rubrik 2.1:** "Jika satu unit **jelas** memenuhi Confront sekaligus Persuade, digunakan
  Confront." Kasus ragu tidak diatur.
- **Keputusan:** jika ragu, dipakai **Persuade**. Jika keduanya jelas, tetap Confront.
- **Dampak:** Total MINA tidak berubah (P dan Confront sama-sama MINA). Yang berubah adalah
  distribusinya di antara kedua kode.

### A2. Persuade dan Persuade with Permission di unit berbeda dalam satu giliran
- **Manual:** E.1.a menetapkan satu slot "Persuade (Persuade or Persuade with)" per volley.
  E.4.c.1 hanya mengatur P dan PWP pada **unit yang sama**: yang dipakai PWP.
- **Rubrik 2.1:** "Setiap giliran hanya menerima satu kode persuasi", tanpa menyebut mana yang
  menang. Trigger database `check_miti_rules` menolak P dan PWP sekaligus pada satu giliran.
- **Keputusan:** **PWP menang**, sebagai perluasan E.4.c.1. Persuasi yang tidak dikode
  tercermin pada skor Partnership, sesuai semangat E.4.c.1.
- **Dampak:** P (MINA) bisa lebih rendah daripada jika P yang dipilih.

### A3. Three strikes untuk Affirm
- **Manual (E.4.f.2.a):** afirmasi yang diulang berkali-kali biasanya dikode hanya pada "two or
  three" kemunculan pertama. Tidak jelas apakah maksudnya afirmasi yang sama atau afirmasi
  secara umum.
- **Rubrik 2.2:** "Afirmasi **sama** yang diulang umumnya hanya dikodekan pada dua atau tiga
  kemunculan awal." Ambangnya tidak dipilih.
- **Keputusan (adaptasi):** ambang **3**, hanya untuk **afirmasi yang sama**. Agen menandai
  pengulangan (`same_affirmation_as_turn`); Python menghitung rantainya dan tidak mengode
  kemunculan ke-4 dan seterusnya.
- **Dampak:** kecil pada fixture (setiap sesi paling banyak 1–2 AF).

### A4. Sesi 5 menit atau kurang
- **Manual (Lampiran B FAQ 1):** pada sesi sangat pendek (2–5 menit) "it may be best" hanya
  mengode hitungan perilaku. Pada sesi di bawah 10 menit, skor global lebih sulit ditetapkan.
- **Rubrik 2.1:** pada sesi ≤5 menit "**hanya kode perilaku yang ditampilkan**"; pada sesi <10
  menit, hasil diberi keterangan keterbatasan skor global.
- **Keputusan:** sesi ≤300 detik hanya mendapat kode perilaku dan ukuran yang dihitung dari
  jumlah kode (%CR, R:Q, Total MIA, Total MINA). Skor global (serta Technical/Relational
  Global), pengamatan proses MI, dan umpan balik dilewati, dengan keterangan di
  `limitation_notes`. Sesi 300–599 detik tetap dinilai, dengan keterangan keterbatasan.
- **Dampak:** mahasiswa dengan sesi sangat pendek tidak menerima umpan balik naratif.

---

## B. Label Ilustrasi yang meragukan menurut manual

Label Ilustrasi tidak diubah. Butir di bawah adalah tempat sistem kemungkinan berbeda dari
dokumen, dan perbedaannya akan muncul di `compare_miti_fixtures.py`.

### B1. HEN K04: Persuade saja, atau Persuade + Confront
- **Teks:** "Tapi Bapak tahu kan rokok itu merusak kesehatan, dan keluarga Bapak bergantung pada
  Bapak. Sebaiknya Bapak mulai kurangi dari sekarang."
- **Ilustrasi:** P saja; "nada menceramahi belum cukup jelas untuk Confront".
- **Manual:** E.1.a memecah volley per pikiran lengkap, sehingga ada dua unit. Unit pertama
  (pertanyaan retoris yang mengingatkan ketergantungan keluarga) mirip contoh Confront di E.4.g.2
  ("Think of your kids, for crying out loud"). Unit kedua adalah nasihat tanpa izin (P). Bila
  unit pertama jelas Confront, volley menerima P dan Confront. Bila ragu, keputusan A1 berlaku:
  P, sama dengan Ilustrasi.
- **Dampak:** Total MINA HEN bisa 2, bukan 1.

### B2. NAD K09: Persuade
- **Teks:** "Pengalaman itu menunjukkan bahwa meminta bantuan tidak selalu membuat orang kecewa."
- **Ilustrasi:** P ("menyimpulkan sendiri argumen ... untuk meyakinkan klien tanpa izin").
- **Manual:** E.4.b sengaja memasang batas tinggi untuk P (jika ragu antara P dan GI, pakai GI).
  E.4.e.2 membolehkan refleksi kompleks menekankan sebagian ucapan klien "to make a point".
  Karena kalimat ini menyimpulkan pengalaman klien sendiri (C08), ia juga dapat dibaca sebagai
  CR berarah, atau GI.
- **Dampak:** kemungkinan selisih P −1/CR +1. Total MINA NAD bisa 1, bukan 2, dan %CR naik.

### B3. NAD K08: Affirm
- **Teks:** "Kamu berusaha menjaga tanggung jawab sekaligus mulai mempertimbangkan batas
  kemampuanmu."
- **Ilustrasi:** AF.
- **Manual:** AF menang atas refleksi bila jelas (E.4.f.2). Bila ragu antara MIA dan kode lain,
  dipakai kode lain (E.4.f.1.a). Ini kasus batas antara AF dan CR.
- **Dampak:** kemungkinan selisih AF/CR. Ini label yang meragukan, bukan pertentangan aturan.

---

## C. Perbedaan antara manual dan pengodean ahli CASAA

### C1. Cheryl #25 ("Cutting down."): ragu antara Confront dan refleksi
- **Manual (E.4.g.2, decision rule):** "In the relatively unusual circumstance where the coder is
  not certain whether to code an utterance as a Confrontation or Reflection, **no code should be
  assigned**."
- **CASAA (kode ahli):** SR, dengan penjelasan "Defaulted to SR versus confront due to decision
  rule if not clearly confront to default to other code."
- **Sistem:** mengikuti manual, yaitu **tanpa kode**. Fixture tetap memakai label ahli (SR).
- **Dampak:** pada perbandingan CASAA, butir ini akan tercatat sebagai SR yang terlewat (false
  negative), meskipun sistem mengikuti teks manual.

### C2. Catatan notasi CASAA (bukan perbedaan aturan)
- **SAME:** lanjutan volley konselor yang hanya diselingi ujaran klien fasilitatif, sesuai
  manual E.3. Kodenya ikut volley sebelumnya dan tidak dihitung lagi (Emmy #23, #43, #45, #73,
  #87, #91, #93, #99).
- **EMP di Emmy #53** dibaca sebagai Emphasize (ujarannya menegaskan klien sebagai satu-satunya
  pengambil keputusan), bukan Empathy.
- **Emmy #37** ("GI / Support, NC / AF"): NC berlaku hanya untuk unit pernyataan dukungan,
  sehingga volley tetap menerima GI dan AF. Ditetapkan manual di parser (`OVERRIDES`).
- **Smoker #25** tercetak "22" di PDF (salah ketik di sumber). Fixture memakai nomor urut.
- **Target perubahan** ketiga transkrip tidak dicantumkan di sumber. Target ditetapkan peneliti
  (`change_target_assumed: true`):
  - smoker: "quit smoking";
  - Cheryl: "reduce drinking";
  - Emmy: "increase safety for herself and her baby (safety planning)".

---

## D. Adaptasi Rubrik yang sejalan dengan manual (dicatat untuk kelengkapan)

- **Panjang sampel:** manual (B, G) merekomendasikan segmen 20 menit dan mengingatkan agar
  berhati-hati pada segmen yang lebih panjang. Rubrik menilai seluruh sesi tanpa batas durasi.
- **Penyebut nol:** %CR dan R:Q ditampilkan sebagai "tidak dapat dihitung" beserta jumlah
  mentahnya. Ini aturan penyajian SafeSesi; manual tidak mengaturnya.
- **Contoh di Rubrik 2.1, 2.2, dan 2.5** memakai skenario Nadia, yaitu skenario yang sama
  dengan fixture SS-NAD-01. Contoh tersebut tidak dipakai di prompt evaluator agar hasil uji
  tidak bias.
