// Data dummy halaman Hasil Evaluasi. Bentuknya mengikuti respons API:
// - GET /sessions/{id}/evaluation (backend/api/evaluations.py) + field reference_* baru
//   (lihat docs/rancangan_api_halaman_hasil.md)
// - GET /sessions/{id} (tampilan mahasiswa: ringkasan publik + turns)
// Isi percakapan ditulis sendiri untuk keperluan tampilan, bukan dari dokumen Ilustrasi/CASAA.

const MITI_CODES = ['GI', 'P', 'PWP', 'Q', 'SR', 'CR', 'AF', 'SEEK', 'EA', 'CONFRONT']

// Ambang MITI 4.2.1 bagian H (cukup = fair, baik = good).
const REFERENCES = {
  technical_global: { cukup: 3, baik: 4 },
  relational_global: { cukup: 3.5, baik: 4 },
  pct_complex_reflection: { cukup: 40, baik: 50 },
  reflection_question_ratio: { cukup: 1, baik: 2 },
}
const REFERENCE_NOTE =
  'Acuan dari MITI. Dipakai sebagai bahan belajar, bukan penentu lulus.'

function withReference(key, measure) {
  const t = REFERENCES[key]
  const v = measure.value
  const band = v == null ? null : v >= t.baik ? 'baik' : v >= t.cukup ? 'cukup' : 'di_bawah_acuan'
  return { ...measure, reference_band: band, reference_thresholds: t, reference_note: REFERENCE_NOTE }
}

const ratio = (num, den, scale, formula, counts) =>
  den === 0
    ? { value: null, label: 'tidak dapat dihitung', formula, counts }
    : { value: Math.round((scale * num * 100) / den) / 100, label: null, formula, counts }

const globalMean = (scores, a, b, formula) => {
  const s = { [a]: scores?.[a] ?? null, [b]: scores?.[b] ?? null }
  return s[a] == null || s[b] == null
    ? { value: null, label: 'tidak dinilai', formula, scores: s }
    : { value: (s[a] + s[b]) / 2, label: null, formula, scores: s }
}

// Cermin services/evaluation/summary.py agar angka dummy konsisten dengan kode yang dibuat.
function summaryMeasures(f, scores) {
  return {
    technical_global: withReference(
      'technical_global',
      globalMean(scores, 'cultivating_change_talk', 'softening_sustain_talk', '(Cultivating Change Talk + Softening Sustain Talk) / 2'),
    ),
    relational_global: withReference(
      'relational_global',
      globalMean(scores, 'partnership', 'empathy', '(Partnership + Empathy) / 2'),
    ),
    pct_complex_reflection: withReference(
      'pct_complex_reflection',
      ratio(f.CR, f.SR + f.CR, 100, 'CR / (SR + CR) × 100%', { SR: f.SR, CR: f.CR }),
    ),
    reflection_question_ratio: withReference(
      'reflection_question_ratio',
      ratio(f.SR + f.CR, f.Q, 1, '(SR + CR) / Q', { SR: f.SR, CR: f.CR, Q: f.Q }),
    ),
    total_mia: { value: f.AF + f.SEEK + f.EA, formula: 'AF + Seek + Emphasize', counts: { AF: f.AF, SEEK: f.SEEK, EA: f.EA } },
    total_mina: { value: f.P + f.CONFRONT, formula: 'P + Confront', counts: { P: f.P, CONFRONT: f.CONFRONT } },
  }
}

const SCENARIO = {
  id: 7,
  title: 'Begadang Main Gim dan Skripsi yang Tertunda',
  change_target: 'Mengurangi waktu bermain gim di malam hari agar ada waktu untuk menulis skripsi',
  client_name: 'Raka Pratama',
  client_age: 23,
  client_gender: 'Laki-laki',
  client_role: 'Mahasiswa tingkat akhir',
  initial_summary: 'Raka diminta dosen pembimbing mempercepat progres skripsinya dan datang untuk membicarakan kebiasaan malamnya.',
}

function turn(turn_no, speaker, content, sec) {
  return { turn_no, speaker, content, start_ms: sec * 1000, end_ms: (sec + 8) * 1000 }
}

const FULL_TURNS = [
  turn(1, 'counselor', 'Halo Raka, terima kasih sudah datang. Apa yang ingin kamu ceritakan hari ini?', 5),
  turn(2, 'client', 'Jadi gini, Kak. Dosen pembimbingku bilang progres skripsiku lambat. Padahal aku cuma main gim sebentar tiap malam, buat lepas stres.', 20),
  turn(3, 'counselor', 'Kamu merasa main gim itu caramu melepas penat, tapi sekarang ada tekanan dari dosen soal skripsi.', 60),
  turn(4, 'client', "Iya. Cuma 'sebentar' itu kadang sampai jam tiga pagi sih. Besoknya aku bangun siang dan nggak sempat nulis.", 80),
  turn(5, 'counselor', 'Begadang sampai pagi bikin waktu menulismu hilang. Apa yang paling bikin kamu khawatir dari situ?', 140),
  turn(6, 'client', 'Aku takut nggak lulus tepat waktu. Orang tuaku sudah nanya terus kapan wisuda.', 165),
  turn(7, 'counselor', 'Kamu harus berhenti main gim di hari kerja. Itu satu-satunya cara.', 230),
  turn(8, 'client', 'Ya... gampang ngomongnya, Kak. Kalau nggak main, aku malah nggak bisa tidur.', 250),
  turn(9, 'counselor', 'Kamu sudah jujur soal kebiasaanmu, itu tidak mudah. Bagian mana dari malammu yang menurutmu paling bisa kamu ubah?', 330),
  turn(10, 'client', 'Mungkin berhenti jam dua belas? Aku pernah coba seminggu, lumayan juga.', 360),
  turn(11, 'counselor', 'Ada bagian dari dirimu yang tahu tidur lebih awal itu membantumu. Kalau kamu mau, kita bisa pikirkan bersama apa yang membantumu waktu itu.', 450),
  turn(12, 'client', 'Boleh. Waktu itu aku taruh HP di luar kamar sih.', 480),
  turn(13, 'counselor', 'Bagaimana kalau minggu ini kamu coba lagi cara itu? Kamu yang paling tahu apa yang cocok untukmu.', 600),
  turn(14, 'client', 'Oke, aku coba mulai malam ini.', 630),
]

const unit = (unit_no, code, excerpt, reason, uncertainty_note = null) => ({ unit_no, code, excerpt, reason, uncertainty_note })

const FULL_CODES = [
  { turn_no: 1, codes: [unit(1, 'Q', 'Apa yang ingin kamu ceritakan hari ini?', 'Pertanyaan terbuka yang mengundang klien bercerita.')] },
  { turn_no: 3, codes: [unit(1, 'CR', 'Kamu merasa main gim itu caramu melepas penat, tapi sekarang ada tekanan dari dosen soal skripsi.', 'Menambahkan makna (gim sebagai cara melepas penat) dan menautkan dua sisi yang dirasakan klien, tidak sekadar mengulang.')] },
  {
    turn_no: 5,
    codes: [
      unit(1, 'SR', 'Begadang sampai pagi bikin waktu menulismu hilang.', 'Mengulang isi ucapan klien dengan kata lain tanpa menambah makna baru.'),
      unit(2, 'Q', 'Apa yang paling bikin kamu khawatir dari situ?', 'Pertanyaan terbuka tentang kekhawatiran klien.'),
    ],
  },
  { turn_no: 7, codes: [unit(1, 'P', 'Kamu harus berhenti main gim di hari kerja. Itu satu-satunya cara.', 'Memberi arahan dan solusi tanpa meminta izin atau menanyakan pendapat klien lebih dulu.')] },
  {
    turn_no: 9,
    codes: [
      unit(1, 'AF', 'Kamu sudah jujur soal kebiasaanmu, itu tidak mudah.', 'Menghargai usaha klien bersikap terbuka.'),
      unit(2, 'Q', 'Bagian mana dari malammu yang menurutmu paling bisa kamu ubah?', 'Pertanyaan yang mengundang klien memilih sendiri bagian yang ingin diubah.'),
    ],
  },
  {
    turn_no: 11,
    codes: [
      unit(1, 'CR', 'Ada bagian dari dirimu yang tahu tidur lebih awal itu membantumu.', 'Menangkap makna di balik pengalaman klien yang pernah mencoba berhenti lebih awal.'),
      unit(2, 'SEEK', 'Kalau kamu mau, kita bisa pikirkan bersama apa yang membantumu waktu itu.', 'Mengajak klien bekerja sama dan memberi pilihan.'),
    ],
  },
  {
    turn_no: 13,
    codes: [
      unit(1, 'Q', 'Bagaimana kalau minggu ini kamu coba lagi cara itu?', 'Pertanyaan tertutup yang berisi usulan langkah.', 'Bisa juga dibaca sebagai saran; nada suara tidak tersedia untuk memastikan.'),
      unit(2, 'EA', 'Kamu yang paling tahu apa yang cocok untukmu.', 'Menegaskan bahwa klien yang memegang keputusan.'),
    ],
  },
]

const SHORT_TURNS = [
  turn(1, 'counselor', 'Hai Raka, sesi kita kali ini singkat saja ya, sekitar lima menit.', 3),
  turn(2, 'client', 'Iya, Kak. Aku sebenarnya pengin cerita soal kebiasaan begadangku.', 15),
  turn(3, 'counselor', 'Kamu bilang begadang membuat skripsimu tertunda.', 70),
  turn(4, 'client', 'Iya, gara-gara itu bab tiga belum selesai.', 90),
  turn(5, 'counselor', 'Kamu ingin lulus tepat waktu, tapi malam hari terasa sulit dilepas.', 160),
  turn(6, 'client', 'Persis. Rasanya kayak dua hal itu tarik-menarik.', 185),
]

const SHORT_CODES = [
  { turn_no: 1, codes: [unit(1, 'GI', 'sesi kita kali ini singkat saja ya, sekitar lima menit.', 'Memberi informasi tentang lama sesi.')] },
  { turn_no: 3, codes: [unit(1, 'SR', 'Kamu bilang begadang membuat skripsimu tertunda.', 'Mengulang isi ucapan klien tanpa menambah makna.')] },
  { turn_no: 5, codes: [unit(1, 'CR', 'Kamu ingin lulus tepat waktu, tapi malam hari terasa sulit dilepas.', 'Menangkap dua sisi perasaan klien (ingin lulus dan sulit melepas kebiasaan).')] },
]

function frequenciesOf(codesByTurn) {
  const f = Object.fromEntries(MITI_CODES.map((c) => [c, 0]))
  codesByTurn.forEach((t) => t.codes.forEach((u) => (f[u.code] += 1)))
  return f
}

function statusPayload(id, sessionId, status, extra = {}) {
  return {
    evaluation_id: id,
    session_id: sessionId,
    status,
    error_message: null,
    guideline_version: 'MITI 4.2.1 / Rubrik SafeSesi v1',
    model_version: 'behavior_coding=gemini-3.8-flash (thinking=default)',
    assessed_duration_seconds: null,
    limitation_notes: [],
    completed_at: null,
    ...extra,
  }
}

const GLOBAL_SCORES = [
  {
    dimension: 'cultivating_change_talk',
    score: 3,
    reason: 'Konselor beberapa kali mengundang alasan klien untuk berubah (T9, T11) dan klien menyebut langkah yang pernah berhasil. Namun pada T7 konselor memberi solusi sendiri sehingga kesempatan menggali alasan klien terlewat.',
    evidence_turn_nos: [7, 9, 11],
  },
  {
    dimension: 'softening_sustain_talk',
    score: 3,
    reason: 'Saat klien menolak (T8), konselor tidak berdebat dan beralih menghargai kejujuran klien (T9). Sebelumnya arahan pada T7 justru memancing klien membela kebiasaannya.',
    evidence_turn_nos: [7, 8, 9],
  },
  {
    dimension: 'partnership',
    score: 3,
    reason: 'Ada ajakan bekerja sama (T11) dan penegasan bahwa klien yang memutuskan (T13). Arahan sepihak di T7 menurunkan kesan kemitraan.',
    evidence_turn_nos: [7, 11, 13],
  },
  {
    dimension: 'empathy',
    score: 4,
    reason: 'Refleksi pada T3 dan T11 menunjukkan konselor berusaha memahami sudut pandang klien, termasuk alasan klien bermain gim. Pemahaman ini belum muncul konsisten di seluruh sesi.',
    evidence_turn_nos: [3, 5, 11],
  },
]

const PROCESSES = [
  {
    process: 'engaging',
    start_turn_no: 1,
    end_turn_no: 4,
    excerpt: 'Konselor: "Kamu merasa main gim itu caramu melepas penat, tapi sekarang ada tekanan dari dosen soal skripsi." Klien: "Iya. Cuma \'sebentar\' itu kadang sampai jam tiga pagi sih."',
    reason: 'Konselor mengundang cerita klien dan merefleksikan sudut pandangnya; klien menanggapi dengan cerita yang lebih terbuka.',
    evidence_found: true,
  },
  {
    process: 'focusing',
    start_turn_no: null,
    end_turn_no: null,
    excerpt: null,
    reason: 'Arah pembahasan tidak dipilih atau dikonfirmasi bersama klien secara jelas.',
    evidence_found: false,
  },
  {
    process: 'evoking',
    start_turn_no: 9,
    end_turn_no: 11,
    excerpt: 'Konselor: "Bagian mana dari malammu yang menurutmu paling bisa kamu ubah?" Klien: "Mungkin berhenti jam dua belas? Aku pernah coba seminggu, lumayan juga."',
    reason: 'Konselor mengundang klien menyebut sendiri perubahan yang mungkin, lalu menindaklanjutinya dengan refleksi.',
    evidence_found: true,
  },
  {
    process: 'planning',
    start_turn_no: 12,
    end_turn_no: 14,
    excerpt: 'Konselor: "Bagaimana kalau minggu ini kamu coba lagi cara itu?" Klien: "Oke, aku coba mulai malam ini."',
    reason: 'Ada pembahasan langkah awal (menaruh HP di luar kamar) dan waktu mencobanya.',
    evidence_found: true,
  },
]

const FEEDBACK = [
  {
    kind: 'strength',
    turn_no: 3,
    excerpt: 'Kamu merasa main gim itu caramu melepas penat',
    content: 'Refleksi ini menunjukkan kamu memahami alasan klien bermain gim tanpa menghakiminya. Klien lalu bercerita lebih jujur tentang kebiasaannya di T4.',
    evidence_turn_nos: [4],
  },
  {
    kind: 'strength',
    turn_no: 11,
    excerpt: 'kita bisa pikirkan bersama apa yang membantumu waktu itu',
    content: 'Kamu memakai pengalaman berhasil klien sebagai bahan dan mengajaknya berpikir bersama. Klien langsung menyebut cara yang pernah ia pakai (T12).',
    evidence_turn_nos: [12],
  },
  {
    kind: 'improvement',
    turn_no: 7,
    excerpt: 'Kamu harus berhenti main gim di hari kerja.',
    content: 'Klien baru saja menyebut kekhawatiran soal kelulusan (T6), tetapi konselor langsung memberi solusi. Klien kemudian membela kebiasaannya (T8). Menggali atau merefleksikan kekhawatiran itu dulu bisa membuka alasan berubah dari klien sendiri.',
    evidence_turn_nos: [6, 8],
  },
  {
    kind: 'improvement',
    turn_no: 13,
    excerpt: 'Bagaimana kalau minggu ini kamu coba lagi cara itu?',
    content: 'Jumlah pertanyaan masih lebih banyak dari refleksi. Sebelum mengusulkan langkah, coba rangkum dulu apa yang sudah disampaikan klien.',
    evidence_turn_nos: [12],
  },
  {
    kind: 'alternative_response',
    turn_no: 7,
    excerpt: 'Kamu harus berhenti main gim di hari kerja. Itu satu-satunya cara.',
    content: 'Kamu khawatir tidak lulus tepat waktu dan pertanyaan orang tua membuatnya terasa makin berat.',
    evidence_turn_nos: [6],
  },
  {
    kind: 'alternative_response',
    turn_no: 13,
    excerpt: 'Bagaimana kalau minggu ini kamu coba lagi cara itu?',
    content: 'Jadi waktu HP ada di luar kamar, kamu bisa tidur lebih awal. Apa yang kamu pikirkan tentang mencobanya lagi?',
    evidence_turn_nos: [12],
  },
]

function sessionDetail(id, turns, duration) {
  return {
    id,
    student_id: 1,
    scenario_id: SCENARIO.id,
    class_id: null,
    parent_session_id: null,
    scenario: SCENARIO,
    status: 'completed',
    started_at: '2026-11-19T09:00:00+07:00',
    ended_at: '2026-11-19T09:14:00+07:00',
    duration_seconds: duration,
    turns,
    previous_topics: [],
  }
}

const fullFreq = frequenciesOf(FULL_CODES)
const shortFreq = frequenciesOf(SHORT_CODES)
const globalsMap = Object.fromEntries(GLOBAL_SCORES.map((g) => [g.dimension, g.score]))

export const COMPLETED_EVALUATION = (sessionId) =>
  statusPayload(41, sessionId, 'completed', {
    model_version:
      'behavior_coding=gemini-3.8-flash (thinking=default); global_scoring=gemini-3.8-flash (thinking=default); process_observation=gemini-3.8-flash (thinking=default); feedback=gemini-3.8-flash (thinking=default)',
    assessed_duration_seconds: 840,
    completed_at: '2026-11-19T09:16:30+07:00',
    codes_by_turn: FULL_CODES,
    frequencies: fullFreq,
    global_scores: GLOBAL_SCORES,
    summary_measures: summaryMeasures(fullFreq, globalsMap),
    processes: PROCESSES,
    feedback: FEEDBACK,
  })

// Kunci = session_id dummy. null = evaluasi belum dibuat (API mengembalikan 404).
export const DUMMY_EVALUATIONS = {
  9001: null,
  9002: statusPayload(42, 9002, 'running'),
  9003: statusPayload(43, 9003, 'failed', {
    error_message: 'Layanan penilaian tidak merespons tepat waktu.',
  }),
  9004: COMPLETED_EVALUATION(9004),
  9005: statusPayload(45, 9005, 'completed', {
    assessed_duration_seconds: 270,
    completed_at: '2026-11-19T10:06:10+07:00',
    limitation_notes: [
      'Durasi sesi 270 detik (≤ 5 menit): sesuai Rubrik SafeSesi 2.1, hanya kode perilaku dan ukuran berbasis jumlah kode (%CR, R:Q, MIA, MINA) yang ditampilkan. Skor global, Technical/Relational Global, pengamatan proses MI, dan umpan balik tidak dinilai.',
    ],
    codes_by_turn: SHORT_CODES,
    frequencies: shortFreq,
    global_scores: [],
    summary_measures: summaryMeasures(shortFreq, null),
    processes: [],
    feedback: [],
  }),
}

export const DUMMY_SESSIONS = {
  9001: sessionDetail(9001, FULL_TURNS, 840),
  9002: sessionDetail(9002, FULL_TURNS, 840),
  9003: sessionDetail(9003, FULL_TURNS, 840),
  9004: sessionDetail(9004, FULL_TURNS, 840),
  9005: sessionDetail(9005, SHORT_TURNS, 270),
}
