export default function CatalogHeader() {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5 text-[11px] text-[#d3daea] font-medium">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#f5b51b]" />
        <span>Ruang Belajar</span>
        <span className="material-symbols-outlined text-[13px]">
          chevron_right
        </span>
        <span className="text-white font-semibold">
          Katalog Latihan Mandiri
        </span>
      </div>
      <h1 className="text-xl md:text-2xl font-bold text-white tracking-tight">
        Latihan Mandiri
      </h1>
      <p className="text-xs md:text-sm text-[#d3daea] max-w-3xl leading-relaxed">
        Pilih skenario percakapan dengan klien virtual untuk mengasah
        keterampilan konseling sesuai ritme belajarmu.
      </p>
    </div>
  )
}

