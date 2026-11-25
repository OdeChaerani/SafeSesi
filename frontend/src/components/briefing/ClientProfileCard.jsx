import PreviousTopicsTable from './PreviousTopicsTable'

export default function ClientProfileCard({
  client = {
    name: 'Nadia Putri',
    age: 19,
    gender: 'Perempuan',
    role: 'Semester 3 · Fakultas Psikologi',
    problem:
      'Nadia merasa sangat kewalahan membagi waktu antara beban perkuliahan reguler, penugasan praktikum laboratorium, dan komitmen tanggung jawab organisasi kemahasiswaan. Belakangan ini ia mengalami kelelahan mental, kesulitan menentukan skala prioritas kegiatan harian, serta mulai merasa bersalah terhadap tugas yang tertunda tanpa diagnosis patologis dini.',
  },
  mode = 'new',
  category = 'Latihan Mandiri',
  previousTopics = [],
  lastSavedTime = '08:12',
}) {
  const isClassMode = category.toLowerCase().includes('kelas')

  return (
    <section className="bg-white rounded-2xl p-6 md:p-8 shadow-xs border border-slate-200/80 relative overflow-hidden flex flex-col gap-6">
      {/* Decorative Blur Ambient */}
      <div className="absolute -right-16 -top-16 w-56 h-56 bg-[#ede9fe]/40 rounded-full blur-3xl pointer-events-none" />

      {/* 1. Header Profil Klien */}
      <div className="flex items-start gap-4 pb-5 border-b border-slate-100">
        <div className="shrink-0">
          <div className="w-14 h-14 md:w-16 md:h-16 rounded-full bg-[#352f55] text-white flex items-center justify-center shadow-xs">
            <span className="material-symbols-outlined text-[32px] md:text-[36px]">
              person
            </span>
          </div>
        </div>

        <div className="flex flex-col min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-[10px] uppercase font-bold tracking-wider text-[#64748b]">
              Profil Karakter Klien
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-[#352f55]">
              {isClassMode ? 'Simulasi Interaktif' : 'Latihan Mandiri Bebas'}
            </span>
          </div>

          <h2 className="text-lg md:text-xl font-bold text-[#1e1a34] truncate mt-0.5">
            {client.name}
          </h2>

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-50 text-slate-700 text-xs border border-slate-200/60 font-medium">
              <span className="material-symbols-outlined text-[14px] text-slate-500">
                cake
              </span>
              {client.age} tahun
            </span>

            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-50 text-slate-700 text-xs border border-slate-200/60 font-medium">
              <span className="material-symbols-outlined text-[14px] text-slate-500">
                female
              </span>
              {client.gender || 'Perempuan'}
            </span>

            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-50 text-slate-700 text-xs border border-slate-200/60 font-medium">
              <span className="material-symbols-outlined text-[14px] text-slate-500">
                school
              </span>
              {client.role || 'Mahasiswa'}
            </span>

            {client.marital_status && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-50 text-slate-700 text-xs border border-slate-200/60 font-medium">
                <span className="material-symbols-outlined text-[14px] text-slate-500">
                  family_restroom
                </span>
                {client.marital_status}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 2. Gambaran Masalah (Keluhan + Dampak Menyatu) & Target Perubahan */}
      <div className="bg-slate-50 p-5 rounded-xl border border-slate-200/70 flex flex-col gap-3">
        {/* Narasi Masalah & Dampak yang Mengalir */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2 text-[#352f55]">
            <span className="material-symbols-outlined text-[18px]">
              psychology_alt
            </span>
            <h3 className="text-xs md:text-sm font-bold text-[#1e1a34]">
              Gambaran Masalah
            </h3>
          </div>
          <p className="text-xs text-[#64748b] leading-relaxed text-justify">
            {client.problem}
            {client.history_impact && ` ${client.history_impact}`}
          </p>
        </div>

        {/* Target / Harapan Perubahan */}
        {(client.expectation_change_context || client.change_target) && (
          <div className="pt-2.5 border-t border-slate-200/60 flex items-start gap-2">
            <span className="material-symbols-outlined text-[16px] text-[#352f55] shrink-0 mt-0.5">
              flag
            </span>
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-[11px] font-bold text-[#1e1a34]">
                Target &amp; Harapan Perubahan:
              </span>
              <p className="text-xs text-[#64748b] leading-relaxed">
                {client.expectation_change_context || client.change_target}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 3. Catatan Sesi Sebelumnya (Khusus Mode Continue) */}
      {mode === 'continue' && (
        <PreviousTopicsTable
          topics={previousTopics}
          lastSavedTime={lastSavedTime}
        />
      )}
    </section>
  )
}

