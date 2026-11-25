import { useEffect, useRef, useState } from 'react'
import { createUser } from '../../services/admin'
import Button from '../ui/Button'
import Collapse from '../ui/Collapse'

const EXIT_MS = 180
const FIELDS_WITH_INPUT = ['name', 'email', 'npm', 'asal_institusi', 'nip']
const ROLES = [
  { value: 'student', label: 'Mahasiswa', icon: 'school' },
  { value: 'lecturer', label: 'Dosen Praktikum', icon: 'psychology' },
]
const EMPTY = { name: '', email: '', role: 'student', npm: '', isExternal: false, institution: '', nip: '' }

const inputClass =
  'w-full h-10 px-3.5 bg-slate-50 text-[#1e1a34] text-sm rounded-xl border border-slate-300 placeholder-slate-500 outline-none transition-all duration-200 focus:bg-white focus:border-[#352f55] focus:ring-2 focus:ring-[#352f55]/40 disabled:opacity-50 disabled:cursor-not-allowed aria-[invalid=true]:border-rose-500'

/** Peringatan lunak (tidak memblokir): panjang nomor di luar kebiasaan setelah spasi dibuang. */
function lengthWarning(value, expected, label) {
  const length = value.replace(/\s/g, '').length
  return length && length !== expected ? `${label} ini ${length} karakter, bukan ${expected}. Periksa kembali.` : ''
}

function Field({ id, label, value, onChange, help, warning, error, inputRef, ...inputProps }) {
  return (
    <div className="group">
      <label htmlFor={id} className="block text-xs font-semibold text-[#1e1a34] mb-1.5 transition-colors group-focus-within:text-[#7b5800]">
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={`${id}-info`}
        className={`${inputClass} ${error ? 'ss-shake' : ''}`}
        {...inputProps}
      />
      <div id={`${id}-info`} className="mt-1 space-y-0.5 text-[11px]">
        {help && <p className="text-slate-600">{help}</p>}
        {warning && <p className="ss-fade-in text-amber-800">{warning}</p>}
        {error && (
          <p role="alert" className="ss-fade-in text-rose-700 font-semibold">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}

/** Panel samping (dialog modal) berisi formulir pembuatan akun. Dipasang hanya selama terbuka. */
export default function UserFormPanel({ onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [isLoading, setIsLoading] = useState(false)
  const [isClosing, setIsClosing] = useState(false)
  const [error, setError] = useState('')
  const [errorField, setErrorField] = useState(null)
  const dialogRef = useRef(null)
  const nameRef = useRef(null)
  const closingRef = useRef(false)

  const { name, email, role, npm, isExternal, institution, nip } = form
  const isStudent = role === 'student'
  const isDirty = Object.keys(EMPTY).some((key) => key !== 'role' && form[key] !== EMPTY[key])

  // showModal() memberi jebakan fokus bawaan browser: halaman di belakang menjadi inert.
  useEffect(() => {
    if (!dialogRef.current.open) dialogRef.current.showModal()
    nameRef.current.focus()
  }, [])

  const dismiss = (after) => {
    closingRef.current = true
    setIsClosing(true)
    setTimeout(() => {
      dialogRef.current?.close()
      after()
    }, EXIT_MS)
  }

  const requestClose = () => {
    if (isLoading || closingRef.current) return
    if (isDirty && !window.confirm('Isian belum disimpan. Tutup formulir?')) return
    dismiss(onClose)
  }

  const edit = (key) => (value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setError('')
    setErrorField(null)
  }

  const errorFor = (field) => (errorField === field ? error : '')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (isLoading) return
    const missing = !name.trim() ? 'name' : !email.trim() ? 'email' : null
    if (missing) {
      setError(missing === 'name' ? 'Harap masukkan nama lengkap.' : 'Harap masukkan email pengguna.')
      setErrorField(missing)
      return
    }

    // Hanya isian milik role yang dipilih yang dikirim; backend menolak isian role lain.
    const profile = {}
    if (isStudent) {
      if (!isExternal) profile.npm = npm
      if (institution.trim() || isExternal) profile.asal_institusi = institution
    }
    if (role === 'lecturer') profile.nip = nip

    setIsLoading(true)
    setError('')
    setErrorField(null)
    try {
      const result = await createUser({ name: name.trim(), email: email.trim(), role, ...profile })
      dismiss(() => onCreated(result))
    } catch (err) {
      setError(err.message || 'Gagal membuat akun baru.')
      setErrorField(err.field)
      setIsLoading(false)
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="user-panel-title"
      className={`ss-drawer ${isClosing ? 'ss-drawer-closing' : ''}`}
      onKeyDown={(e) => {
        if (e.key !== 'Escape') return
        e.preventDefault()
        requestClose()
      }}
      onCancel={(e) => {
        e.preventDefault()
        requestClose()
      }}
      onClose={() => {
        if (!closingRef.current) onClose() // ditutup paksa oleh browser
      }}
      // Klik pada latar gelap dilaporkan dengan target dialog itu sendiri.
      onMouseDown={(e) => {
        if (e.target === dialogRef.current) requestClose()
      }}
    >
      <div className="h-full flex flex-col bg-white text-[#1e1a34]">
        <header className="flex items-start justify-between gap-3 px-5 py-4 border-b border-slate-200">
          <div>
            <h2 id="user-panel-title" className="text-lg font-bold">
              Tambah pengguna
            </h2>
            <p className="text-xs text-slate-600 mt-0.5">
              Akun menunggu aktivasi. Tautan aktivasi sekali pakai ditampilkan setelah akun dibuat.
            </p>
          </div>
          <button
            type="button"
            onClick={requestClose}
            aria-label="Tutup panel"
            className="w-10 h-10 shrink-0 rounded-lg flex items-center justify-center text-slate-700 hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer transition"
          >
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">close</span>
          </button>
        </header>

        <form id="user-form" onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {error && !FIELDS_WITH_INPUT.includes(errorField) && (
            <div role="alert" className="ss-fade-in p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">error</span>
              <span>{error}</span>
            </div>
          )}

          <Field
            id="user-name"
            label="Nama Lengkap"
            inputRef={nameRef}
            value={name}
            onChange={edit('name')}
            placeholder="Contoh: Nadia Maharani"
            required
            error={errorFor('name')}
          />
          <Field
            id="user-email"
            label="Email Kampus"
            type="email"
            value={email}
            onChange={edit('email')}
            placeholder="Contoh: nadia@kampus.ac.id"
            required
            error={errorFor('email')}
          />

          <fieldset>
            <legend className="text-xs font-semibold mb-1.5">Peran Pengguna</legend>
            <div className="grid grid-cols-2 gap-3">
              {ROLES.map((option) => (
                <label
                  key={option.value}
                  className={`flex items-center gap-2 min-h-11 px-3 rounded-xl border cursor-pointer text-xs transition focus-within:ring-2 focus-within:ring-[#352f55] ${
                    role === option.value
                      ? 'border-[#352f55] bg-[#f0f3ff] text-[#352f55] font-bold'
                      : 'border-slate-300 text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value={option.value}
                    checked={role === option.value}
                    onChange={() => edit('role')(option.value)}
                    className="accent-[#352f55]"
                  />
                  <span className="material-symbols-outlined text-[18px]" aria-hidden="true">{option.icon}</span>
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <Collapse open={isStudent}>
              <div className="flex flex-col gap-3">
                <label className="flex items-center gap-2 min-h-10 text-sm cursor-pointer w-fit">
                  <input
                    type="checkbox"
                    checked={isExternal}
                    onChange={(e) => edit('isExternal')(e.target.checked)}
                    className="ss-check w-4 h-4 accent-[#352f55]"
                  />
                  Mahasiswa kampus lain (tanpa NPM)
                </label>
                <Field
                  id="user-npm"
                  label="NPM"
                  value={isExternal ? '' : npm}
                  onChange={edit('npm')}
                  disabled={isExternal}
                  required={isStudent && !isExternal}
                  inputMode="numeric"
                  help="12 digit"
                  warning={isExternal ? '' : lengthWarning(npm, 12, 'NPM')}
                  error={errorFor('npm')}
                />
                <Field
                  id="user-institution"
                  label={isExternal ? 'Asal institusi' : 'Asal institusi (opsional)'}
                  value={institution}
                  onChange={edit('institution')}
                  required={isStudent && isExternal}
                  error={errorFor('asal_institusi')}
                />
              </div>
            </Collapse>
            <Collapse open={role === 'lecturer'}>
              <Field
                id="user-nip"
                label="NIP"
                value={nip}
                onChange={edit('nip')}
                required={role === 'lecturer'}
                inputMode="numeric"
                help="18 digit"
                warning={lengthWarning(nip, 18, 'NIP')}
                error={errorFor('nip')}
              />
            </Collapse>
          </div>
        </form>

        <footer className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200">
          <Button variant="outline" onClick={requestClose} disabled={isLoading} className="min-h-10">
            Batal
          </Button>
          <Button type="submit" form="user-form" variant="secondary" icon="person_add" loading={isLoading} className="min-h-10">
            {isLoading ? 'Membuat akun...' : 'Buat akun'}
          </Button>
        </footer>
      </div>
    </dialog>
  )
}
