import Button from '../ui/Button'

export default function SessionTermsCard({
  category = 'Latihan Mandiri',
  mode = 'new',
  lastSavedTime = '08:12',
  onStartSession,
  onBack,
  isLoading = false,
}) {
  const isClassMode = category.toLowerCase().includes('kelas')

  return (
    <section className="bg-white rounded-2xl p-6 md:p-8 shadow-xs border border-slate-200/80 flex flex-col gap-5">
      {/* 1. Header Card */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[20px] text-[#352f55]">
            checklist
          </span>
          <h3 className="text-sm font-bold text-[#1e1a34]">Ketentuan Sesi</h3>
        </div>
        <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
          {isClassMode ? 'Mode Kelas' : 'Mode Mandiri'}
        </span>
      </div>

      {/* 2. Checklist Poin Ringkas */}
      <div className="space-y-2.5">
        <div className="flex items-start gap-3 p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/70 transition-colors">
          <div className="w-5 h-5 rounded-full bg-[#ede9fe] text-[#352f55] flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
            1
          </div>
          <p className="text-xs text-[#1e1a34] leading-snug">
            {isClassMode
              ? 'Percakapan interaktif terpandu dengan klien virtual AI.'
              : 'Percakapan interaktif bebas tanpa batas frekuensi percobaan.'}
          </p>
        </div>

        <div className="flex items-start gap-3 p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/70 transition-colors">
          <div className="w-5 h-5 rounded-full bg-[#ede9fe] text-[#352f55] flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
            2
          </div>
          <p className="text-xs text-[#1e1a34] leading-snug">
            Transkrip dan metrik evaluasi otomatis tersimpan di menu Riwayat.
          </p>
        </div>

        <div className="flex items-start gap-3 p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/70 transition-colors">
          <div className="w-5 h-5 rounded-full bg-[#ede9fe] text-[#352f55] flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
            3
          </div>
          <p className="text-xs text-[#1e1a34] leading-snug">
            Audio diproses real-time dan tidak disimpan di server (aman &amp; privat).
          </p>
        </div>
      </div>

      {/* 3. Banner Privasi atau Transparansi Kelas */}
      {isClassMode ? (
        <div className="p-3.5 rounded-xl bg-[#ede9fe] border border-[#d7cefe] text-[#352f55] shadow-xs">
          <div className="flex items-start gap-2.5">
            <span className="material-symbols-outlined text-[18px] text-[#352f55] shrink-0 mt-0.5">
              visibility
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-bold text-[#1e1a34]">
                Peninjauan Dosen (Mode Kelas)
              </span>
              <p className="text-[11px] text-[#64748b] leading-relaxed">
                Aktivitas latihan dan evaluasi formatif ditinjau oleh dosen pengampu kelas.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl bg-[#ede9fe] border border-[#d7cefe] text-[#352f55] shadow-xs">
          <div className="flex items-start gap-2.5">
            <span className="material-symbols-outlined text-[18px] text-[#352f55] shrink-0 mt-0.5">
              lock
            </span>
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-bold text-[#1e1a34]">
                100% Privat (Mode Mandiri)
              </span>
              <p className="text-[11px] text-[#64748b] leading-relaxed">
                Transkrip dan hasil latihan hanya dapat diakses oleh Anda, tanpa akses dosen.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 4. Tombol Aksi Mulai & Kembali */}
      <div className="flex flex-col gap-2.5 pt-3 border-t border-slate-100">
        <Button
          variant="primary"
          size="md"
          iconRight="play_arrow"
          disabled={isLoading}
          onClick={onStartSession}
          className="w-full py-3"
        >
          {isLoading ? (
            <span>Menyiapkan Sesi...</span>
          ) : mode === 'continue' ? (
            <span>Lanjutkan Sesi (Menit {lastSavedTime})</span>
          ) : (
            <span>Mulai Sesi Baru (Dari Awal)</span>
          )}
        </Button>

        <button
          type="button"
          onClick={onBack}
          className="w-full py-2.5 text-xs font-bold text-[#64748b] hover:text-[#1e1a34] hover:bg-slate-100 rounded-xl transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span className="material-symbols-outlined text-[16px]">
            arrow_back
          </span>
          <span>
            {isClassMode ? 'Kembali ke Detail Kelas' : 'Kembali ke Katalog Latihan Mandiri'}
          </span>
        </button>
      </div>
    </section>
  )
}

