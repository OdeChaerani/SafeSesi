import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AcademicGuidanceBanner from '../components/catalog/AcademicGuidanceBanner'
import CatalogFilters from '../components/catalog/CatalogFilters'
import CatalogHeader from '../components/catalog/CatalogHeader'
import ScenarioGrid from '../components/catalog/ScenarioGrid'
import { FALLBACK_SCENARIOS } from '../data/fallbackScenarios'

export default function CatalogPage({ onStartExercise }) {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [scenarios, setScenarios] = useState([])

  const handleStartExercise = (activity) => {
    if (onStartExercise) {
      onStartExercise(activity)
    } else {
      const scenarioId = activity.scenarioId || activity.id || 1
      navigate(`/latihan-mandiri/${scenarioId}/briefing`, {
        state: { scenario: activity },
      })
    }
  }
  const [meta, setMeta] = useState({
    total: 3,
    unattempted_count: 2,
    attempted_count: 1,
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let isMounted = true
    const fetchCatalog = async () => {
      setIsLoading(true)
      try {
        const queryParams = new URLSearchParams()
        if (searchQuery.trim()) queryParams.set('search', searchQuery.trim())
        if (statusFilter !== 'all') queryParams.set('status', statusFilter)

        const res = await fetch(
          `http://localhost:8000/api/v1/scenarios/catalog?${queryParams.toString()}`,
          {
            headers: {
              'X-Dev-User-Id': '1', // Peneliti default dev user
            },
          }
        )

        if (!res.ok) throw new Error('Gagal memuat katalog dari backend')
        const data = await res.json()

        if (isMounted) {
          setScenarios(data.items || [])
          setMeta({
            total: data.total || 0,
            unattempted_count: data.unattempted_count || 0,
            attempted_count: data.attempted_count || 0,
          })
        }
      } catch (err) {
        // Fallback anggun ke skenario seed lokal jika backend offline
        if (isMounted) {
          let filtered = FALLBACK_SCENARIOS
          if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase()
            filtered = filtered.filter(
              (s) =>
                s.title.toLowerCase().includes(q) ||
                s.client_name.toLowerCase().includes(q) ||
                s.main_problem.toLowerCase().includes(q)
            )
          }
          if (statusFilter !== 'all') {
            filtered = filtered.filter((s) => s.attempt_status === statusFilter)
          }
          setScenarios(filtered)
          setMeta({
            total: FALLBACK_SCENARIOS.length,
            unattempted_count: FALLBACK_SCENARIOS.filter(
              (s) => s.attempt_status === 'unattempted'
            ).length,
            attempted_count: FALLBACK_SCENARIOS.filter(
              (s) => s.attempt_status === 'attempted'
            ).length,
          })
        }
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    // Debounce pencarian 300ms agar efisien
    const timer = setTimeout(fetchCatalog, 300)
    return () => {
      isMounted = false
      clearTimeout(timer)
    }
  }, [searchQuery, statusFilter])

  return (
    <div className="flex flex-col gap-6 w-full">
      {/* 1. Header & Breadcrumb */}
      <CatalogHeader />

      {/* 2. Kotak Filter, Pencarian, & Counter */}
      <CatalogFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        totalCount={meta.total}
        unattemptedCount={meta.unattempted_count}
        attemptedCount={meta.attempted_count}
        displayedCount={scenarios.length}
      />

      {/* 3. Grid Kartu Skenario */}
      <ScenarioGrid
        scenarios={scenarios}
        onStartExercise={handleStartExercise}
        isLoading={isLoading}
      />

      {/* 4. Banner Panduan Akademik */}
      <AcademicGuidanceBanner />
    </div>
  )
}

