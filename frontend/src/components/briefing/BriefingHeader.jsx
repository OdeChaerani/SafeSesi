/** Breadcrumb halaman briefing. className = nama kelas (kosong untuk latihan mandiri). */
export default function BriefingHeader({ title, className, onBack }) {
  return (
    <header className="flex flex-col gap-0.5">
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[11px] text-[#d3daea] font-medium flex-wrap">
        <button
          type="button"
          onClick={onBack}
          className="min-h-8 flex items-center gap-1 rounded-lg hover:text-white transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-white outline-none"
        >
          <span className="material-symbols-outlined text-[16px]" aria-hidden="true">arrow_back</span>
          <span>{className ? 'Beranda' : 'Latihan Mandiri'}</span>
        </button>
        {className && (
          <>
            <span aria-hidden="true" className="text-white/40">/</span>
            <span className="break-words">{className}</span>
          </>
        )}
        <span aria-hidden="true" className="text-white/40">/</span>
        <span aria-current="page" className="text-white font-semibold">Briefing pra-sesi</span>
      </nav>
      {/* Judul disembunyikan: sama dengan nama klien di kartu; tetap dibacakan pembaca layar. */}
      <h1 className="sr-only">{title}</h1>
    </header>
  )
}
