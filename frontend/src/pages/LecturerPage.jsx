import DashboardLayout from '../components/layout/DashboardLayout'

export default function LecturerPage({ user, onLogout }) {
  return (
    <DashboardLayout user={user} onLogout={onLogout}>
      <div className="bg-white p-6 md:p-10 rounded-2xl shadow-xs border border-slate-100 flex flex-col items-center justify-center text-center gap-4 py-16">
        <div className="w-16 h-16 rounded-2xl bg-amber-50 text-[#f5b51b] flex items-center justify-center border border-amber-200">
          <span className="material-symbols-outlined text-[36px]">school</span>
        </div>
        <div className="max-w-lg">
          <span className="inline-block px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-semibold mb-2">
            Peran: Dosen Pengampu Praktikum
          </span>
          <h2 className="text-xl md:text-2xl text-[#1e1a34] font-bold mb-2">
            Portal Praktikum Dosen
          </h2>
          <p className="text-xs md:text-sm text-slate-500 leading-relaxed mb-6">
            Selamat datang, <strong className="text-slate-700">{user?.name || 'Bapak/Ibu Dosen'}</strong>.
            Fitur manajemen penugasan kelas, pemantauan progres praktikum konseling mahasiswa, dan rekapitulasi penilaian OARS sedang dalam tahap penyelesaian.
          </p>
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-left text-xs text-slate-600">
            <span className="font-semibold text-slate-800 block mb-1">Status Akses:</span>
            Sebagai dosen kelas, Anda nantinya dapat meninjau sesi praktikum mahasiswa kelas yang Anda ampu setelah sesi diselesaikan.
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
