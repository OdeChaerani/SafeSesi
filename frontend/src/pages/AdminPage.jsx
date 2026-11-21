import { useState } from 'react'
import DashboardLayout from '../components/layout/DashboardLayout'
import { postJson } from '../services/api'

export default function AdminPage({ user, onLogout }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('student')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [createdList, setCreatedList] = useState([])
  const [copiedIndex, setCopiedIndex] = useState(null)

  const handleCreateUser = async (e) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Harap masukkan nama lengkap.')
      return
    }
    if (!email.trim()) {
      setError('Harap masukkan email pengguna.')
      return
    }

    setIsLoading(true)
    setError('')
    try {
      const res = await postJson('/admin/users', {
        name: name.trim(),
        email: email.trim(),
        role,
      })

      // Tambahkan ke daftar akun yang baru dibuat
      setCreatedList((prev) => [
        {
          id: res.user.id,
          name: res.user.name,
          email: res.user.email,
          role: res.user.role,
          activationUrl: res.activation_url,
          createdAt: new Date().toLocaleTimeString('id-ID', {
            hour: '2-digit',
            minute: '2-digit',
          }),
        },
        ...prev,
      ])

      // Reset form
      setName('')
      setEmail('')
    } catch (err) {
      setError(err.message || 'Gagal membuat akun baru.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopyLink = (url, index) => {
    navigator.clipboard.writeText(url)
    setCopiedIndex(index)
    setTimeout(() => {
      setCopiedIndex(null)
    }, 2500)
  }

  return (
    <DashboardLayout user={user} onLogout={onLogout}>
      <div className="flex flex-col gap-6 max-w-4xl mx-auto w-full">
        {/* Header Admin */}
        <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-100 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 text-[#352f55] flex items-center justify-center border border-indigo-200 shrink-0">
              <span className="material-symbols-outlined text-[28px]">
                admin_panel_settings
              </span>
            </div>
            <div>
              <h1 className="text-xl text-[#1e1a34] font-bold">
                Portal Administrator SafeSesi
              </h1>
              <p className="text-xs text-slate-500">
                Kelola pendaftaran akun mahasiswa dan dosen pengampu praktikum konseling.
              </p>
            </div>
          </div>
          <span className="px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-semibold">
            Admin: {user?.name || 'Administrator'}
          </span>
        </div>

        {/* Card: Form Buat Akun Baru */}
        <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-xs border border-slate-100">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-[20px] text-[#352f55]">
              person_add
            </span>
            <h2 className="text-base sm:text-lg font-bold text-[#1e1a34]">
              Buat Akun Pengguna Baru
            </h2>
          </div>
          <p className="text-xs text-slate-500 mb-6 leading-relaxed">
            Akun akan dibuat dalam status menunggu aktivasi. Sistem akan menghasilkan tautan aktivasi sekali pakai yang dapat dikirimkan kepada calon pengguna untuk membuat kata sandi mereka.
          </p>

          {/* Alert Error */}
          {error && (
            <div className="mb-5 p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">error</span>
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleCreateUser} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Nama Lengkap */}
              <div>
                <label
                  htmlFor="user-name"
                  className="block text-xs font-semibold text-[#1e1a34] mb-1.5"
                >
                  Nama Lengkap
                </label>
                <input
                  id="user-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Contoh: Nadia Maharani"
                  required
                  className="w-full h-10 px-3.5 bg-slate-50 text-[#1e1a34] text-xs sm:text-sm rounded-xl border border-slate-200 placeholder-slate-400 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-1 focus:ring-[#352f55]"
                />
              </div>

              {/* Email */}
              <div>
                <label
                  htmlFor="user-email"
                  className="block text-xs font-semibold text-[#1e1a34] mb-1.5"
                >
                  Email Kampus
                </label>
                <input
                  id="user-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Contoh: nadia@unpad.ac.id"
                  required
                  className="w-full h-10 px-3.5 bg-slate-50 text-[#1e1a34] text-xs sm:text-sm rounded-xl border border-slate-200 placeholder-slate-400 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-1 focus:ring-[#352f55]"
                />
              </div>
            </div>

            {/* Peran / Role */}
            <div>
              <label className="block text-xs font-semibold text-[#1e1a34] mb-2">
                Peran Pengguna
              </label>
              <div className="grid grid-cols-2 gap-3 max-w-md">
                <label
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition ${
                    role === 'student'
                      ? 'border-[#352f55] bg-slate-50 text-[#352f55] font-semibold'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value="student"
                    checked={role === 'student'}
                    onChange={() => setRole('student')}
                    className="accent-[#352f55]"
                  />
                  <div className="flex items-center gap-2 text-xs">
                    <span className="material-symbols-outlined text-[18px]">
                      school
                    </span>
                    <span>Mahasiswa</span>
                  </div>
                </label>

                <label
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition ${
                    role === 'lecturer'
                      ? 'border-[#352f55] bg-slate-50 text-[#352f55] font-semibold'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value="lecturer"
                    checked={role === 'lecturer'}
                    onChange={() => setRole('lecturer')}
                    className="accent-[#352f55]"
                  />
                  <div className="flex items-center gap-2 text-xs">
                    <span className="material-symbols-outlined text-[18px]">
                      psychology
                    </span>
                    <span>Dosen Praktikum</span>
                  </div>
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="mt-4 px-6 h-10 bg-[#352f55] hover:bg-[#25203d] disabled:opacity-60 text-white font-semibold text-xs sm:text-sm rounded-xl shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
            >
              {isLoading ? (
                <span>Membuat Akun...</span>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">
                    add_circle
                  </span>
                  <span>Buat Akun & Dapatkan Tautan Aktivasi</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Card: Riwayat Tautan Aktivasi yang Baru Dibuat */}
        {createdList.length > 0 && (
          <div className="bg-white p-6 sm:p-8 rounded-2xl shadow-xs border border-slate-100 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold text-[#1e1a34] flex items-center gap-2">
                <span className="material-symbols-outlined text-[20px] text-emerald-600">
                  check_circle
                </span>
                Akun yang Baru Dibuat ({createdList.length})
              </h2>
              <span className="text-[11px] text-slate-400">
                Sesi saat ini
              </span>
            </div>

            <div className="flex flex-col gap-3">
              {createdList.map((item, idx) => (
                <div
                  key={item.id}
                  className="p-4 rounded-xl border border-slate-200 bg-slate-50 flex flex-col gap-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-[#1e1a34]">
                        {item.name}
                      </span>
                      <span className="text-slate-400">·</span>
                      <span className="text-xs text-slate-600 font-mono">
                        {item.email}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        item.role === 'student'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-amber-100 text-amber-700'
                      }`}
                    >
                      {item.role === 'student' ? 'Mahasiswa' : 'Dosen'}
                    </span>
                  </div>

                  {/* Activation Link Box */}
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={item.activationUrl}
                      className="flex-1 h-9 px-3 bg-white text-xs text-slate-700 rounded-lg border border-slate-200 font-mono select-all outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => handleCopyLink(item.activationUrl, idx)}
                      className="h-9 px-3 rounded-lg bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] text-xs font-semibold flex items-center gap-1 transition shrink-0 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-[16px]">
                        {copiedIndex === idx ? 'done' : 'content_copy'}
                      </span>
                      <span>
                        {copiedIndex === idx ? 'Tersalin!' : 'Salin Tautan'}
                      </span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
