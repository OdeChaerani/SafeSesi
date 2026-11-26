// Sumber: BRD (akses sesi mandiri; hasil otomatis tidak menentukan nilai akhir) dan aturan akses di api/deps.py.
export default function AcademicGuidanceBanner() {
  return (
    <p className="flex items-start gap-2.5 bg-[#f0f3ff] p-3 rounded-xl text-xs text-[#1e1a34]">
      <span className="material-symbols-outlined text-[18px] text-[#352f55] shrink-0" aria-hidden="true">lock</span>
      <span>
        Hasil latihan mandiri hanya bisa kamu lihat. Evaluasi otomatis adalah umpan balik latihan, bukan penentu nilai akhir.
      </span>
    </p>
  )
}
