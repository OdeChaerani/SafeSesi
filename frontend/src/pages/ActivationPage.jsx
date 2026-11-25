import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AuthBackground from '../components/auth/AuthBackground'
import { activate } from '../services/auth'

// Halaman yang sama dipakai untuk aktivasi akun baru dan atur ulang kata sandi (endpoint backend-nya sama).
const COPY = {
  activate: {
    title: 'Aktivasi Akun',
    subtitle: 'Buat kata sandi baru untuk mengaktifkan akun praktikum konseling Anda.',
    invalidLink: 'Tautan aktivasi tidak valid atau tidak memuat token aktivasi.',
    failed: 'Aktivasi akun gagal. Tautan mungkin telah kedaluwarsa atau sudah digunakan.',
    successTitle: 'Akun Berhasil Diaktifkan!',
    successBody: 'Kata sandi Anda telah disimpan. Silakan masuk ke aplikasi menggunakan email dan kata sandi baru Anda.',
    submit: 'Aktifkan Akun',
    loading: 'Mengaktifkan Akun...',
  },
  reset: {
    title: 'Atur Ulang Kata Sandi',
    subtitle: 'Buat kata sandi baru untuk akun Anda. Semua perangkat yang sedang masuk akan keluar.',
    invalidLink: 'Tautan atur ulang tidak valid atau tidak memuat token.',
    failed: 'Kata sandi gagal diatur ulang. Tautan mungkin telah kedaluwarsa atau sudah digunakan.',
    successTitle: 'Kata Sandi Berhasil Diatur Ulang!',
    successBody: 'Silakan masuk ke aplikasi menggunakan email dan kata sandi baru Anda.',
    submit: 'Simpan Kata Sandi',
    loading: 'Menyimpan...',
  },
}

export default function ActivationPage({ mode = 'activate' }) {
  const copy = COPY[mode]
  const navigate = useNavigate()
  // Token dibaca dari hash URL (#token=...) agar tidak ikut terkirim ke server atau tercatat di log.
  const [token] = useState(() => new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token') || '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(() => (token ? '' : copy.invalidLink))
  const [isSuccess, setIsSuccess] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!token) {
      setError('Token aktivasi tidak ditemukan pada tautan.')
      return
    }
    if (password.length < 8) {
      setError('Kata sandi harus terdiri dari minimal 8 karakter.')
      return
    }
    if (password !== confirmPassword) {
      setError('Konfirmasi kata sandi tidak cocok.')
      return
    }

    setIsLoading(true)
    setError('')
    try {
      await activate(token, password)
      setIsSuccess(true)
    } catch (err) {
      setError(err.message || copy.failed)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="w-full min-h-screen flex items-center justify-center relative bg-[#352f55] select-none p-4">
      <AuthBackground />

      <div
        className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-6 sm:p-8 md:p-9 transition-all relative z-10 border border-slate-100"
        style={{
          boxShadow:
            '0 20px 40px -15px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Header */}
        <div className="mb-6 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-[#ede9fe] text-[#352f55] mb-3">
            <span className="material-symbols-outlined text-[28px]">
              verified_user
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl text-[#1e1a34] font-bold tracking-tight mb-1">
            {copy.title} <span className="text-[#f5b51b]">Safe</span>
            <span className="text-[#352f55]">Sesi</span>
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
            {copy.subtitle}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-600 text-xs flex items-start gap-2">
            <span className="material-symbols-outlined text-[18px] shrink-0 mt-0.5">
              error
            </span>
            <span className="leading-relaxed">{error}</span>
          </div>
        )}

        {isSuccess ? (
          /* Success Card */
          <div className="text-center py-4 space-y-4">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-200">
              <span className="material-symbols-outlined text-[32px]">
                check_circle
              </span>
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800 mb-1">
                {copy.successTitle}
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                {copy.successBody}
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="w-full h-10 mt-2 bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] font-bold text-xs sm:text-sm rounded-xl shadow-xs transition flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <span>Menuju Halaman Masuk</span>
              <span className="material-symbols-outlined text-[18px]">
                arrow_forward
              </span>
            </button>
          </div>
        ) : (
          /* Activation Form */
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* New Password */}
            <div>
              <label
                htmlFor="new-password"
                className="block text-xs font-semibold text-[#1e1a34] mb-1.5"
              >
                Kata Sandi Baru
              </label>
              <div className="relative rounded-xl shadow-xs">
                <input
                  id="new-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimal 8 karakter"
                  required
                  minLength={8}
                  className="w-full h-10 pl-3.5 pr-10 bg-slate-50 text-[#1e1a34] text-xs sm:text-sm rounded-xl border border-slate-200 placeholder-slate-400 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-1 focus:ring-[#352f55]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 transition cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label
                htmlFor="confirm-password"
                className="block text-xs font-semibold text-[#1e1a34] mb-1.5"
              >
                Ulangi Kata Sandi Baru
              </label>
              <div className="relative rounded-xl shadow-xs">
                <input
                  id="confirm-password"
                  name="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Ketik ulang kata sandi baru"
                  required
                  minLength={8}
                  className="w-full h-10 px-3.5 bg-slate-50 text-[#1e1a34] text-xs sm:text-sm rounded-xl border border-slate-200 placeholder-slate-400 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-1 focus:ring-[#352f55]"
                />
              </div>
            </div>

            <p className="text-[11px] text-slate-500">
              * Kata sandi minimal 8 karakter, disarankan kombinasi huruf dan angka.
            </p>

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading || !token}
              className="w-full h-10 mt-2 bg-[#f5b51b] hover:bg-[#e2a613] disabled:opacity-60 disabled:cursor-not-allowed text-[#1e1a34] font-bold text-xs sm:text-sm rounded-xl shadow-xs active:scale-[0.99] transition flex items-center justify-center gap-1.5 cursor-pointer"
            >
              {isLoading ? (
                <span>{copy.loading}</span>
              ) : (
                <>
                  <span>{copy.submit}</span>
                  <span className="material-symbols-outlined text-[18px]">
                    check
                  </span>
                </>
              )}
            </button>
          </form>
        )}

        {/* Footer */}
        <div className="mt-5 pt-3.5 border-t border-slate-100 text-center">
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="text-xs text-[#352f55] hover:underline font-semibold"
          >
            Kembali ke Halaman Masuk
          </button>
        </div>
      </div>
    </main>
  )
}
