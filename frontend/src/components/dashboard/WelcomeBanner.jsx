/** Sapaan beranda. Baris tahun akademik hanya berisi bila mahasiswa punya kelas. */
export default function WelcomeBanner({ userName, academicYears = [] }) {
  return (
    <div className="flex flex-col md:flex-row md:items-end justify-between gap-3">
      {/* Sambutan Personal */}
      <div className="flex flex-col gap-1">
        {/* Tinggi baris dipertahankan agar halaman tidak bergeser saat daftar kelas selesai dimuat. */}
        <div className="flex items-center gap-1.5 min-h-4">
          {academicYears.length > 0 && (
            <>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#f5b51b]" />
              <span className="ss-fade-in text-[11px] text-[#d3daea] font-medium tracking-wide">
                Tahun Akademik {academicYears.join(', ')}
              </span>
            </>
          )}
        </div>
        <h1 className="text-xl md:text-2xl text-white tracking-tight font-bold">
          {userName ? `Halo, ${userName}` : 'Halo'} <span aria-hidden="true">👋</span>
        </h1>
        <p className="text-xs md:text-sm text-[#d3daea] max-w-xl leading-relaxed">
          Selamat datang di ruang belajar SafeSesi. Latih keterampilan konseling dan
          refleksi secara terarah dalam lingkungan simulasi yang aman.
        </p>
      </div>

      {/* Quick Action Card Mini: halaman panduan belum ada */}
      <div
        aria-disabled="true"
        className="flex items-center gap-2.5 bg-white px-3.5 py-2 rounded-xl shadow-sm border border-white/20 self-start md:self-auto cursor-default"
      >
        <div className="w-8 h-8 rounded-lg bg-[#ede9fe] text-[#352f55] flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-[18px]" aria-hidden="true">auto_stories</span>
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-bold text-[#1e1a34]">Panduan MI Terintegrasi</span>
          <span className="text-[11px] text-[#64748b]">Segera hadir</span>
        </div>
      </div>
    </div>
  )
}
