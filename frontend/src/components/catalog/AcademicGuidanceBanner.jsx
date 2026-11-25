export default function AcademicGuidanceBanner() {
  return (
    <div className="bg-[#f0f3ff] p-4 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border border-[#d3daea]/60 shadow-xs">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-white text-[#352f55] flex items-center justify-center shrink-0 shadow-xs">
          <span className="material-symbols-outlined text-[20px]">school</span>
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-xs md:text-sm text-[#1e1a34]">
            Panduan Praktik Aman &amp; Reflektif
          </span>
          <span className="text-[11px] md:text-xs text-[#64748b]">
            Setiap sesi latihan mandiri merekam transkrip interaktif tanpa batas percobaan.
            Hasil evaluasi AI bersifat formatif untuk pembelajaran.
          </span>
        </div>
      </div>
      <a
        href="#rubrik"
        onClick={(e) => {
          e.preventDefault()
          alert('Panduan Rubrik Motivational Interviewing (MI) dapat diakses melalui modul pembelajaran.')
        }}
        className="text-xs font-bold text-[#352f55] hover:text-[#f5b51b] transition-colors shrink-0 flex items-center gap-1 self-end sm:self-auto cursor-pointer"
      >
        <span>Lihat Rubrik Evaluasi</span>
        <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
      </a>
    </div>
  )
}

