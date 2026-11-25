import { useEffect, useRef, useState } from 'react'
import OneTimeLinkCard from '../components/admin/OneTimeLinkCard'
import UserFormPanel from '../components/admin/UserFormPanel'
import UserTable from '../components/admin/UserTable'
import DashboardLayout from '../components/layout/DashboardLayout'
import Button from '../components/ui/Button'
import Toasts from '../components/ui/Toasts'
import { useToasts } from '../hooks/useToasts'
import { listUsers, resendActivation, resetPassword } from '../services/admin'

const PAGE_SIZE = 20
const SEARCH_DELAY_MS = 300
const HIGHLIGHT_MS = 3000

const controlClass =
  'h-9 px-3 bg-slate-50 text-[#1e1a34] text-xs rounded-xl border border-slate-300 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-2 focus:ring-[#352f55]/40'

function Notice({ icon, title, children, action }) {
  return (
    <div className="ss-fade-in flex flex-col items-center text-center gap-2 px-6 py-14">
      <span className="w-14 h-14 rounded-2xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
        <span className="material-symbols-outlined text-[30px]" aria-hidden="true">{icon}</span>
      </span>
      <h2 className="text-base font-bold text-[#1e1a34]">{title}</h2>
      <p className="text-sm text-slate-600 max-w-md">{children}</p>
      {action}
    </div>
  )
}

export default function AdminUsersPage({ user, onLogout }) {
  const [searchText, setSearchText] = useState('')
  const [filters, setFilters] = useState({ q: '', role: '', status: '', page: 1 })
  const [reloadCount, setReloadCount] = useState(0)
  const [result, setResult] = useState(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [links, setLinks] = useState([])
  const { toasts, addToast, dismissToast } = useToasts()
  const [busyIds, setBusyIds] = useState([])
  const [highlightId, setHighlightId] = useState(null)
  const searchTimer = useRef(null)
  const addButtonRef = useRef(null)
  const openerRef = useRef(null)
  const nextId = useRef(0)

  const params = new URLSearchParams({ page: filters.page, page_size: PAGE_SIZE })
  for (const key of ['q', 'role', 'status']) if (filters[key]) params.set(key, filters[key])
  const query = params.toString()
  const requestKey = `${query}#${reloadCount}`

  // Hasil lama tetap tampil selama permintaan baru berjalan; jawaban yang sudah basi diabaikan.
  useEffect(() => {
    let isStale = false
    listUsers(query)
      .then((data) => {
        if (!isStale) setResult({ key: requestKey, query, data, error: '' })
      })
      .catch((err) => {
        if (!isStale) setResult((prev) => ({ ...prev, key: requestKey, error: err.message }))
      })
    return () => {
      isStale = true
    }
  }, [query, requestKey])

  useEffect(() => () => clearTimeout(searchTimer.current), [])

  useEffect(() => {
    if (highlightId === null) return undefined
    const timer = setTimeout(() => setHighlightId(null), HIGHLIGHT_MS)
    return () => clearTimeout(timer)
  }, [highlightId])

  const isLoading = result?.key !== requestKey
  const isPending = isLoading || searchText.trim() !== filters.q
  const data = result?.data
  const error = isLoading ? '' : result?.error
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))
  const hasFilters = Boolean(filters.q || filters.role || filters.status)

  const reload = () => setReloadCount((count) => count + 1)
  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value, page: 1 }))

  const onSearch = (value) => {
    setSearchText(value)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setFilter('q', value.trim()), SEARCH_DELAY_MS)
  }

  const clearFilters = () => {
    clearTimeout(searchTimer.current)
    setSearchText('')
    setFilters({ q: '', role: '', status: '', page: 1 })
  }

  const addLink = (title, name, url, expiresAt) => {
    const id = ++nextId.current
    setLinks((prev) => [{ id, title, name, url, expiresAt }, ...prev])
  }

  const openPanel = (e) => {
    openerRef.current = e.currentTarget
    setIsPanelOpen(true)
  }

  const closePanel = () => {
    setIsPanelOpen(false)
    // Pemicu di keadaan kosong bisa sudah hilang; jatuh ke tombol utama.
    requestAnimationFrame(() => {
      const opener = openerRef.current
      ;(opener?.isConnected ? opener : addButtonRef.current)?.focus()
    })
  }

  const handleCreated = (res) => {
    closePanel()
    addLink('Tautan aktivasi', res.user.name, res.activation_url, res.expires_at)
    addToast('success', `Akun ${res.user.name} dibuat.`)
    setHighlightId(res.user.id)
    setFilters((prev) => ({ ...prev, page: 1 })) // daftar terurut terbaru dulu
    reload()
  }

  const runRowAction = async (row, call, urlKey, title) => {
    setBusyIds((prev) => [...prev, row.id])
    try {
      const res = await call(row.id)
      addLink(title, row.name, res[urlKey], res.expires_at)
      addToast('success', `${title} untuk ${row.name} dibuat.`)
    } catch (err) {
      addToast('error', err.message)
    } finally {
      setBusyIds((prev) => prev.filter((id) => id !== row.id))
      reload() // status bisa berubah, termasuk bila ditolak karena data sudah basi
    }
  }

  // Cermin aturan backend; backend tetap yang menolak.
  const actionsFor = (row) => {
    if (row.role === 'admin' || row.id === user?.id) return []
    if (row.status === 'aktif') {
      return [
        {
          label: 'Reset kata sandi',
          icon: 'lock_reset',
          onSelect: () => runRowAction(row, resetPassword, 'reset_url', 'Tautan reset kata sandi'),
        },
      ]
    }
    return [
      {
        label: 'Kirim ulang tautan aktivasi',
        icon: 'forward_to_inbox',
        onSelect: () => runRowAction(row, resendActivation, 'activation_url', 'Tautan aktivasi'),
      },
    ]
  }

  const retryButton = (
    <Button variant="secondary" icon="refresh" onClick={reload} className="min-h-10 mt-1">
      Coba lagi
    </Button>
  )

  let content
  if (!data && error) {
    content = (
      <Notice icon="cloud_off" title="Daftar belum bisa dimuat" action={retryButton}>
        {error}
      </Notice>
    )
  } else if (data && data.items.length === 0 && !isLoading) {
    if (filters.page > 1) {
      content = (
        <Notice
          icon="last_page"
          title="Halaman ini kosong"
          action={<Button className="min-h-10 mt-1" onClick={() => setFilters((prev) => ({ ...prev, page: 1 }))}>Ke halaman pertama</Button>}
        >
          Jumlah pengguna sudah berubah.
        </Notice>
      )
    } else if (hasFilters) {
      content = (
        <Notice
          icon="search_off"
          title="Tidak ada pengguna yang cocok"
          action={<Button className="min-h-10 mt-1" onClick={clearFilters}>Hapus pencarian dan saringan</Button>}
        >
          Coba kata kunci lain atau longgarkan saringannya.
        </Notice>
      )
    } else {
      content = (
        <Notice
          icon="group_add"
          title="Belum ada pengguna"
          action={<Button icon="add" className="min-h-10 mt-1" onClick={openPanel}>Tambah pengguna pertama</Button>}
        >
          Buat akun mahasiswa atau dosen, lalu bagikan tautan aktivasinya.
        </Notice>
      )
    }
  } else {
    // Kerangka hanya saat belum ada data sama sekali (atau data lama kosong dan sedang memuat ulang).
    const rows = data && data.items.length > 0 ? data.items : undefined
    content = <UserTable rows={rows} resultKey={result?.query} highlightId={highlightId} busyIds={busyIds} actionsFor={actionsFor} />
  }

  return (
    <DashboardLayout user={user} onLogout={onLogout}>
      <div className="flex flex-col gap-3 w-full -my-2">
        <div className="flex flex-wrap items-end justify-between gap-3 text-white">
          <div>
            <h1 className="text-xl font-bold font-display">Pengguna</h1>
            <p className="text-xs text-[#e6deff]">Kelola akun mahasiswa dan dosen pengampu praktikum konseling.</p>
          </div>
          <Button ref={addButtonRef} icon="add" onClick={openPanel} className="min-h-10 focus-visible:!ring-white focus-visible:!ring-offset-[#352f55]">
            Tambah
          </Button>
        </div>

        {links.map((link) => (
          <OneTimeLinkCard key={link.id} link={link} onDismiss={() => setLinks((prev) => prev.filter((item) => item.id !== link.id))} />
        ))}

        <div className="bg-white rounded-2xl shadow-xs border border-slate-100">
          <div role="search" className="flex flex-col md:flex-row gap-2 p-3">
            <div className="relative flex-1">
              <span className="material-symbols-outlined absolute left-3 top-2 text-[20px] text-slate-500" aria-hidden="true">search</span>
              <input
                type="search"
                value={searchText}
                onChange={(e) => onSearch(e.target.value)}
                maxLength={100}
                placeholder="Cari nama, email, NPM, atau NIP"
                aria-label="Cari pengguna"
                className={`${controlClass} w-full !pl-10 !pr-10`}
              />
              {isPending && <span className="ss-spinner absolute right-3 top-2.5 text-[#352f55]" aria-hidden="true" />}
            </div>
            <select value={filters.role} onChange={(e) => setFilter('role', e.target.value)} aria-label="Saring menurut role" className={controlClass}>
              <option value="">Semua role</option>
              <option value="student">Mahasiswa</option>
              <option value="lecturer">Dosen Praktikum</option>
              <option value="admin">Administrator</option>
            </select>
            <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)} aria-label="Saring menurut status" className={controlClass}>
              <option value="">Semua status</option>
              <option value="aktif">Aktif</option>
              <option value="menunggu">Menunggu</option>
              <option value="kedaluwarsa">Kedaluwarsa</option>
            </select>
          </div>

          <p aria-live="polite" className="sr-only">
            {isPending ? 'Memuat daftar pengguna' : data ? `${data.total} pengguna ditemukan` : ''}
          </p>

          {data && error && (
            <div role="alert" className="mx-4 mb-3 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex flex-wrap items-center justify-between gap-2">
              <span>{error} Yang tampil adalah hasil sebelumnya.</span>
              {retryButton}
            </div>
          )}

          {content}

          {data && data.total > 0 && (
            <nav aria-label="Paginasi" className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-t border-slate-100">
              <span className="text-xs text-slate-600">
                Halaman {filters.page} dari {totalPages} · {data.total} pengguna
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  icon="chevron_left"
                  aria-label="Halaman sebelumnya"
                  title="Sebelumnya"
                  className="w-8 h-8 !px-0"
                  disabled={filters.page <= 1 || isLoading}
                  onClick={() => setFilters((prev) => ({ ...prev, page: prev.page - 1 }))}
                />
                <Button
                  variant="outline"
                  size="sm"
                  icon="chevron_right"
                  aria-label="Halaman berikutnya"
                  title="Berikutnya"
                  className="w-8 h-8 !px-0"
                  disabled={filters.page >= totalPages || isLoading}
                  onClick={() => setFilters((prev) => ({ ...prev, page: prev.page + 1 }))}
                />
              </div>
            </nav>
          )}
        </div>
      </div>

      {isPanelOpen && <UserFormPanel onClose={closePanel} onCreated={handleCreated} />}
      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </DashboardLayout>
  )
}
