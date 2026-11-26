import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AcademicGuidanceBanner from '../components/catalog/AcademicGuidanceBanner'
import CatalogFilters from '../components/catalog/CatalogFilters'
import ScenarioGrid, { ScenarioGridSkeleton } from '../components/catalog/ScenarioGrid'
import { EmptyState, ErrorState } from '../components/dashboard/SectionState'
import Button from '../components/ui/Button'
import { useRequest } from '../hooks/useRequest'
import { getCatalog } from '../services/scenarios'

const SEARCH_DELAY_MS = 300

// Katalog latihan mandiri. Hanya menampilkan data dari API; tidak ada data cadangan.
export default function CatalogPage() {
  const navigate = useNavigate()
  const [searchText, setSearchText] = useState('')
  const [search, setSearch] = useState('') // teks yang sudah dikirim ke API
  const [status, setStatus] = useState('all')
  const timer = useRef(null)

  useEffect(() => () => clearTimeout(timer.current), [])

  const load = useCallback(() => getCatalog({ search, status }), [search, status])
  const { data, error, isLoading, reload } = useRequest(load)
  const isPending = isLoading || searchText.trim() !== search

  const onSearch = (value) => {
    setSearchText(value)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setSearch(value.trim()), SEARCH_DELAY_MS)
  }

  const clearFilters = () => {
    clearTimeout(timer.current)
    setSearchText('')
    setSearch('')
    setStatus('all')
  }

  let content
  if (data === undefined) {
    content = error ? null : <ScenarioGridSkeleton />
  } else if (data.total === 0) {
    content = (
      <EmptyState icon="library_books" title="Belum ada skenario">
        Skenario latihan mandiri akan muncul di sini setelah tersedia di katalog.
      </EmptyState>
    )
  } else if (data.items.length === 0) {
    content = isPending ? (
      <ScenarioGridSkeleton />
    ) : (
      !error && (
        <EmptyState
          icon="search_off"
          title="Tidak ada skenario yang cocok"
          action={<Button size="sm" className="min-h-9 mt-1" onClick={clearFilters}>Hapus saringan</Button>}
        >
          Coba kata kunci lain atau ganti status.
        </EmptyState>
      )
    )
  } else {
    content = (
      <ScenarioGrid scenarios={data.items} isStale={isPending} onStart={(id) => navigate(`/latihan-mandiri/${id}/briefing`)} />
    )
  }

  return (
    <div className="flex flex-col gap-3 w-full">
      <header className="text-white">
        <h1 className="text-lg md:text-xl font-bold tracking-tight">Latihan Mandiri</h1>
        <p className="text-xs text-[#d3daea]">Pilih skenario percakapan dengan klien virtual.</p>
      </header>

      <CatalogFilters
        search={searchText}
        onSearch={onSearch}
        status={status}
        onStatus={setStatus}
        counts={data}
        shown={data?.items.length}
        isPending={isPending && (data !== undefined || !error)}
      />

      {error && (
        <ErrorState
          message={`Katalog belum bisa dimuat. ${error.message}${data ? ' Yang tampil adalah hasil sebelumnya.' : ''}`}
          onRetry={reload}
        />
      )}

      {content}

      <AcademicGuidanceBanner />
    </div>
  )
}
