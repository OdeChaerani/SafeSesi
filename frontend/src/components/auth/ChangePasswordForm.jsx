import { useEffect, useRef, useState } from 'react'
import { changePassword } from '../../services/auth'
import Button from '../ui/Button'

const MIN_LENGTH = 8
const MAX_LENGTH = 128

const FIELDS = [
  { key: 'current_password', id: 'current-password', label: 'Kata sandi saat ini', autoComplete: 'current-password' },
  { key: 'new_password', id: 'new-password', label: 'Kata sandi baru', autoComplete: 'new-password' },
  { key: 'confirm', id: 'confirm-new-password', label: 'Ulangi kata sandi baru', autoComplete: 'new-password' },
]
const EMPTY = { current_password: '', new_password: '', confirm: '' }

/** Isian pertama yang belum layak dikirim: [isian, pesan], atau null. */
function validate({ current_password: current, new_password: next, confirm }) {
  if (!current) return ['current_password', 'Harap masukkan kata sandi saat ini.']
  if (next.length < MIN_LENGTH) return ['new_password', `Kata sandi baru minimal ${MIN_LENGTH} karakter.`]
  if (next.length > MAX_LENGTH) return ['new_password', `Kata sandi baru maksimal ${MAX_LENGTH} karakter.`]
  if (next === current) return ['new_password', 'Kata sandi baru tidak boleh sama dengan kata sandi saat ini.']
  if (next !== confirm) return ['confirm', 'Konfirmasi kata sandi baru tidak cocok.']
  return null
}

/** Isian yang dimaksud galat API. null = galat umum (mis. 429 atau server tidak terjangkau). */
function fieldOfApiError(err) {
  if (FIELDS.some((f) => f.key === err.field)) return err.field
  if (err.status === 400) return 'current_password' // satu-satunya 400: kata sandi saat ini salah
  if (err.status === 422) return 'new_password'
  return null
}

/**
 * Formulir ganti kata sandi. onSuccess dipanggil hanya setelah server menerima;
 * onBusyChange(true/false) agar pemasang tidak menutupnya di tengah pengiriman.
 */
export default function ChangePasswordForm({ onSuccess, onBusyChange, inputRef }) {
  const [values, setValues] = useState(EMPTY)
  const [visible, setVisible] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null) // { field, message }
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  // Petunjuk saja; server tetap penentu.
  const { current_password: current, new_password: next, confirm } = values
  const rules = [
    { label: `Panjang ${MIN_LENGTH} sampai ${MAX_LENGTH} karakter`, met: next.length >= MIN_LENGTH && next.length <= MAX_LENGTH },
    { label: 'Berbeda dari kata sandi saat ini', met: Boolean(current && next) && next !== current },
    { label: 'Ulangan sama dengan kata sandi baru', met: Boolean(confirm) && confirm === next },
  ]

  const setBusy = (busy) => {
    setIsLoading(busy)
    onBusyChange?.(busy)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (isLoading) return
    const problem = validate(values)
    if (problem) {
      setError({ field: problem[0], message: problem[1] })
      return
    }
    setError(null)
    setBusy(true)
    try {
      await changePassword(current, next)
    } catch (err) {
      if (mounted.current) {
        setError({ field: fieldOfApiError(err), message: err.message || 'Kata sandi gagal diganti. Silakan coba lagi.' })
        setBusy(false)
      }
      return
    }
    if (!mounted.current) return
    setValues(EMPTY)
    setBusy(false)
    onSuccess?.()
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 py-1" noValidate>
      {error && !error.field && (
        <p role="alert" className="ss-fade-in p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs">
          {error.message}
        </p>
      )}

      {FIELDS.map((field, index) => {
        const fieldError = error?.field === field.key ? error.message : ''
        const isVisible = Boolean(visible[field.key])
        return (
          <div key={field.key}>
            <label htmlFor={field.id} className="block text-xs font-semibold text-[#1e1a34] mb-1">
              {field.label}
            </label>
            <div className={`relative ${fieldError ? 'ss-shake' : ''}`}>
              <input
                ref={index === 0 ? inputRef : undefined}
                id={field.id}
                type={isVisible ? 'text' : 'password'}
                autoComplete={field.autoComplete}
                value={values[field.key]}
                onChange={(e) => {
                  setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                  setError(null)
                }}
                maxLength={MAX_LENGTH}
                required
                aria-invalid={Boolean(fieldError)}
                aria-describedby={fieldError ? `${field.id}-error` : undefined}
                className="w-full h-10 pl-3 pr-11 bg-slate-50 text-[#1e1a34] text-sm rounded-xl border border-slate-300 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-2 focus:ring-[#352f55]/40 aria-[invalid=true]:border-rose-500"
              />
              <button
                type="button"
                onClick={() => setVisible((prev) => ({ ...prev, [field.key]: !prev[field.key] }))}
                aria-label={`${isVisible ? 'Sembunyikan' : 'Tampilkan'} ${field.label.toLowerCase()}`}
                className="absolute inset-y-0 right-0 w-10 rounded-xl flex items-center justify-center text-slate-600 hover:text-[#1e1a34] focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer transition"
              >
                <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
                  {isVisible ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
            {fieldError && (
              <p id={`${field.id}-error`} role="alert" className="ss-fade-in mt-1 text-[11px] font-semibold text-rose-700">
                {fieldError}
              </p>
            )}
          </div>
        )
      })}

      <ul aria-label="Syarat kata sandi" aria-live="polite" className="flex flex-col gap-1 text-[11px]">
        {rules.map((rule) => (
          <li
            key={rule.label}
            aria-atomic="true"
            className={`flex items-center gap-1.5 transition-colors ${rule.met ? 'text-emerald-700' : 'text-slate-600'}`}
          >
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
              {rule.met ? 'check_circle' : 'radio_button_unchecked'}
            </span>
            <span>
              {rule.label}
              <span className="sr-only">: {rule.met ? 'terpenuhi' : 'belum terpenuhi'}</span>
            </span>
          </li>
        ))}
      </ul>

      <Button type="submit" loading={isLoading} className="min-h-10">
        {isLoading ? 'Menyimpan...' : 'Simpan kata sandi'}
      </Button>
    </form>
  )
}
