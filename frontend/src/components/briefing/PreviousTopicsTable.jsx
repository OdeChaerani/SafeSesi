const DEFAULT_PREVIOUS_TOPICS = [
  {
    id: 1,
    title: 'Eksplorasi Keluhan Utama',
    timeRange: '00:00 – 02:45',
    response:
      'Klien mengutarakan rasa lelah luar biasa membagi waktu antara jadwal kuliah padat, modul praktikum lab, dan kepanitiaan BEM.',
    isLastActive: false,
  },
  {
    id: 2,
    title: 'Skala Prioritas & Hambatan',
    timeRange: '02:46 – 05:30',
    response:
      'Klien mengaku kesulitan menolak permintaan tolong rekan organisasi, memicu penumpukan tugas hingga larut malam.',
    isLastActive: false,
  },
  {
    id: 3,
    title: 'Eksplorasi Ambivalensi & Perasaan Bersalah',
    timeRange: '05:31 – 08:12',
    response:
      'Klien mulai membuka diri bahwa ada keinginan mengurangi beban organisasi tapi cemas dicap tidak bertanggung jawab. Di sinilah percakapan terakhir terhenti.',
    isLastActive: true,
  },
]

export default function PreviousTopicsTable({
  topics = DEFAULT_PREVIOUS_TOPICS,
  lastSavedTime = '08:12',
  attemptNo = 2,
  relativeTime = '2 hari lalu',
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* 1. Alert Banner Melanjutkan Simulasi */}
      <div className="p-4 rounded-xl bg-[#ede9fe] border border-[#d7cefe] flex items-start gap-3.5 shadow-xs">
        <div className="w-8 h-8 rounded-lg bg-[#352f55] text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
          <span className="material-symbols-outlined text-[18px]">restore</span>
        </div>
        <div className="flex flex-col gap-1 min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs font-bold text-[#1e1a34]">
              Melanjutkan Simulasi Sebelumnya
            </span>
            <span className="text-[11px] font-semibold text-[#352f55] bg-white px-2 py-0.5 rounded-md border border-[#d7cefe]/80">
              Tersimpan Otomatis
            </span>
          </div>
          <p className="text-xs text-[#64748b] leading-relaxed">
            Terakhir disimpan pada{' '}
            <span className="font-bold text-[#1e1a34]">Menit {lastSavedTime}</span>{' '}
            (Percobaan ke-{attemptNo} · {relativeTime}). Klien merespons hingga tahap
            eksplorasi ambivalensi.
          </p>
        </div>
      </div>

      {/* 2. Tabel Catatan Pembahasan Sesi Sebelumnya */}
      <div className="bg-white p-5 rounded-2xl shadow-xs border border-slate-200/80">
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-[#352f55]">
              table_chart
            </span>
            <h3 className="text-sm font-bold text-[#1e1a34]">
              Catatan Pembahasan Sesi Sebelumnya
            </h3>
          </div>
          <span className="text-[11px] text-slate-500 font-medium">
            {topics.length} Segmen Tercatat
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-200/80">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 font-bold border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3.5 w-[220px]">Topik Pembahasan</th>
                <th className="py-2.5 px-3.5">Deskripsi Respons Klien</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {topics.map((t) => (
                <tr
                  key={t.id || t.title}
                  className={`transition-colors ${
                    t.isLastActive
                      ? 'bg-[#ede9fe]/30 hover:bg-[#ede9fe]/50'
                      : 'hover:bg-slate-50'
                  }`}
                >
                  <td className="py-3 px-3.5 align-top">
                    <div className="font-bold text-[#1e1a34] text-xs">
                      {t.title}
                    </div>
                    <span
                      className={`inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                        t.isLastActive
                          ? 'bg-[#352f55] text-white'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      <span className="material-symbols-outlined text-[11px]">
                        {t.isLastActive ? 'pause_circle' : 'timer'}
                      </span>
                      {t.timeRange || '00:00'}
                    </span>
                  </td>
                  <td className="py-3 px-3.5 text-[#64748b] text-xs leading-relaxed">
                    {t.response || t.description || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

