export default function BriefingHeader({
  scenarioTitle,
  category = 'Latihan Mandiri',
  estimatedTime = '10–15 menit',
  method = 'Motivational Interviewing',
  onBack,
}) {
  const isClassMode = category.toLowerCase().includes('kelas')

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Breadcrumb Navigasi */}
      <nav className="flex items-center gap-1.5 text-[11px] text-[#d3daea] font-medium flex-wrap">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#f5b51b]" />
        {isClassMode ? (
          <>
            <button
              type="button"
              onClick={onBack}
              className="hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[14px]">school</span>
              <span>Kelas</span>
            </button>
            <span className="text-white/40">/</span>
            <span className="hover:text-white transition-colors">
              Praktikum Konseling Dasar
            </span>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={onBack}
              className="hover:text-white transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[14px]">psychology</span>
              <span>Latihan Mandiri</span>
            </button>
            <span className="text-white/40">/</span>
            <span className="truncate max-w-[200px] sm:max-w-[320px]">
              {scenarioTitle}
            </span>
          </>
        )}
        <span className="text-white/40">/</span>
        <span className="text-white font-semibold">Briefing Pra-Sesi</span>
      </nav>

      {/* 2. Header Box: Judul Skenario & Deskripsi */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5 max-w-3xl">
          {/* Judul Skenario */}
          <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight leading-tight">
            {scenarioTitle}
          </h1>

          <p className="text-xs md:text-sm text-[#d3daea] leading-relaxed">
            {isClassMode
              ? 'Pahami konteks interaksi sebelum memulai simulasi percakapan terpandu bersama klien virtual.'
              : 'Pahami konteks interaksi sebelum memulai simulasi percakapan mandiri bersama klien virtual. Latihan ini bebas dicoba berulang kali untuk mengasah keterampilan MI.'}
          </p>
        </div>

        {/* Versi Engine Badge */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/10 text-[#d3daea] text-[11px] font-medium border border-white/10 self-start shrink-0">
          <span className="w-2 h-2 rounded-full bg-[#f5b51b] animate-pulse" />
          <span>{isClassMode ? 'Simulasi Interaktif v2.4' : 'Mode Mandiri · v2.4'}</span>
        </div>
      </div>
    </div>
  )
}

