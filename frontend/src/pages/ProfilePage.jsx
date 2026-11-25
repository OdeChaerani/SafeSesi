import { useCallback, useEffect, useRef, useState } from 'react'
import ChangePasswordForm from '../components/auth/ChangePasswordForm'
import Avatar from '../components/ui/Avatar'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Collapse from '../components/ui/Collapse'
import CopyButton from '../components/ui/CopyButton'
import Toasts from '../components/ui/Toasts'
import { useToasts } from '../hooks/useToasts'
import { getMe, getRoleLabel } from '../services/auth'

const cardClass = 'bg-white p-4 rounded-2xl shadow-xs border border-slate-100'
const titleClass = 'text-sm font-bold text-[#1e1a34] mb-2'
const ROLE_ICONS = { student: 'school', lecturer: 'psychology', admin: 'admin_panel_settings' }

const formatDate = (value) => new Date(value).toLocaleDateString('id-ID', { dateStyle: 'long' })

/** Baris identitas menurut role: [label, nilai, bisaDisalin]. Admin tidak punya. */
function identityRows(me) {
  if (me.role === 'student') {
    const rows = [['NPM', me.npm, true]]
    if (!me.npm || me.asal_institusi) rows.push(['Asal institusi', me.asal_institusi, false])
    return rows
  }
  return me.role === 'lecturer' ? [['NIP', me.nip, true]] : []
}

function Skeleton() {
  return (
    <div role="status" className="flex flex-col gap-3">
      <span className="sr-only">Memuat profil</span>
      <div className={`${cardClass} flex items-center gap-3`}>
        <span className="ss-skeleton w-14 h-14 rounded-full" />
        <span className="flex-1 space-y-2">
          <span className="ss-skeleton block h-4 w-48 max-w-full rounded" />
          <span className="ss-skeleton block h-3 w-64 max-w-full rounded" />
        </span>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {[0, 1].map((card) => (
          <div key={card} className={`${cardClass} space-y-3`}>
            <span className="ss-skeleton block h-4 w-24 rounded" />
            <span className="ss-skeleton block h-3 w-3/4 rounded" />
            <span className="ss-skeleton block h-3 w-1/2 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

function AccountCard({ me, onCopyError }) {
  const rows = identityRows(me)
  // Hanya tanggal yang benar-benar ada di data.
  const timeline = [
    ['Akun dibuat', me.created_at],
    ['Akun diaktifkan', me.activated_at],
  ].filter(([, value]) => value)

  return (
    <section className={cardClass}>
      <h2 className={titleClass}>Data akun</h2>
      {rows.length > 0 && (
        <dl className="divide-y divide-slate-100 mb-3">
          {rows.map(([label, value, canCopy]) => (
            <div key={label} className="flex items-center gap-3 py-2">
              <dt className="w-28 shrink-0 text-xs text-slate-600">{label}</dt>
              <dd className="flex-1 min-w-0 flex items-center gap-1">
                <span className="text-xs font-semibold text-[#1e1a34] break-all">{value || '-'}</span>
                {canCopy && value && <CopyButton value={value} label={label} onError={onCopyError} />}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {timeline.length > 0 && (
        <ol className="ml-1.5 border-l-2 border-[#e6deff]">
          {timeline.map(([label, value]) => (
            <li key={label} className="relative pl-4 pb-2.5 last:pb-0">
              <span className="absolute -left-[6px] top-1 w-2.5 h-2.5 rounded-full bg-[#352f55]" aria-hidden="true" />
              <p className="text-[11px] text-slate-600">{label}</p>
              <p className="text-xs font-semibold text-[#1e1a34]">{formatDate(value)}</p>
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3 text-[11px] text-slate-600">Perubahan data akun dilakukan oleh admin.</p>
    </section>
  )
}

function SecurityCard({ onChanged }) {
  const [isOpen, setIsOpen] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  // Ganti key = formulir baru, jadi isian lama tidak tertinggal saat panel dibuka lagi.
  const [formKey, setFormKey] = useState(0)
  const toggleRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (isOpen) inputRef.current?.focus({ preventScroll: true })
  }, [isOpen])

  const toggle = () => {
    if (!isOpen) setFormKey((key) => key + 1)
    setIsOpen((open) => !open)
  }

  const handleSuccess = () => {
    setIsOpen(false)
    // Tombol masih disabled sampai render berikutnya, jadi fokus dipindahkan sesudahnya.
    requestAnimationFrame(() => toggleRef.current?.focus())
    onChanged()
  }

  return (
    <section className={cardClass}>
      <h2 className={titleClass}>Keamanan</h2>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-600">Kata sandi akun</p>
        <Button
          ref={toggleRef}
          variant="outline"
          size="sm"
          iconRight={isOpen ? 'expand_less' : 'expand_more'}
          onClick={toggle}
          disabled={isBusy}
          aria-expanded={isOpen}
          aria-controls="password-panel"
          className="min-h-10"
        >
          {isOpen ? 'Tutup' : 'Ubah kata sandi'}
        </Button>
      </div>
      <Collapse open={isOpen} id="password-panel">
        <div className="pt-2">
          <ChangePasswordForm key={formKey} inputRef={inputRef} onBusyChange={setIsBusy} onSuccess={handleSuccess} />
        </div>
      </Collapse>
    </section>
  )
}

function ClassCards({ me }) {
  const title = me.role === 'lecturer' ? 'Kelas yang dikelola' : 'Kelas yang diikuti'
  return (
    <section className={cardClass}>
      <h2 className={titleClass}>
        {title} ({me.classes.length})
      </h2>
      {me.classes.length === 0 ? (
        <p className="text-xs text-slate-600">Belum ada kelas.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {me.classes.map((kelas) => (
            <li key={kelas.id} className="ss-lift p-3 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs font-bold text-[#1e1a34] break-words">{kelas.name}</p>
              <p className="text-[11px] text-slate-600">Tahun akademik {kelas.academic_year}</p>
              {me.role === 'student' &&
                (kelas.lecturers.length === 0 ? (
                  <p className="mt-2 text-[11px] text-slate-600">Dosen: -</p>
                ) : (
                  <ul aria-label="Dosen" className="mt-2 flex flex-col gap-1.5">
                    {kelas.lecturers.map((name, index) => (
                      <li key={`${name}-${index}`} className="flex items-center gap-2">
                        <Avatar name={name} className="w-6 h-6 text-[10px]" />
                        <span className="text-[11px] text-slate-800 break-words min-w-0">{name}</span>
                      </li>
                    ))}
                  </ul>
                ))}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function ProfilePage() {
  const [me, setMe] = useState(null)
  const [error, setError] = useState('')
  const { toasts, addToast, dismissToast } = useToasts()

  const load = useCallback(
    () =>
      getMe()
        .then((data) => {
          setMe(data)
          setError('')
        })
        .catch((err) => setError(err.message)),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  const copyError = (message) => addToast('error', message)

  return (
    <div className="flex flex-col gap-3 w-full max-w-5xl mx-auto">
      {error && (
        <div role="alert" className={`${cardClass} flex flex-wrap items-center justify-between gap-3`}>
          <span className="text-xs text-rose-700">{error}</span>
          <Button size="sm" variant="outline" icon="refresh" onClick={load} className="min-h-10">
            Coba lagi
          </Button>
        </div>
      )}
      {!me && !error && <Skeleton />}

      {me && (
        <div className="ss-fade-up flex flex-col gap-3">
          <header className={`${cardClass} flex items-center gap-3`}>
            <Avatar name={me.name} className="w-14 h-14 text-lg" />
            <div className="min-w-0">
              <h1 className="text-lg font-bold text-[#1e1a34] break-words">{me.name}</h1>
              <div className="flex items-center gap-1">
                <span className="text-xs text-slate-600 break-all">{me.email}</span>
                <CopyButton value={me.email} label="Email" onError={copyError} />
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                <Badge variant="neutral" icon={ROLE_ICONS[me.role]} className="!text-slate-700">
                  {getRoleLabel(me.role)}
                </Badge>
                <Badge variant="success" icon="check_circle">
                  {me.status === 'active' ? 'Aktif' : me.status}
                </Badge>
              </div>
            </div>
          </header>

          <div className="grid gap-3 lg:grid-cols-2 items-start">
            <AccountCard me={me} onCopyError={copyError} />
            <SecurityCard onChanged={() => addToast('success', 'Kata sandi berhasil diganti. Perangkat lain perlu masuk kembali.')} />
          </div>

          {me.classes && <ClassCards me={me} />}
        </div>
      )}

      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
