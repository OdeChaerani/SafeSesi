import { useState, useMemo, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import AudioCheckBar from '../components/briefing/AudioCheckBar'
import BriefingHeader from '../components/briefing/BriefingHeader'
import ClientProfileCard from '../components/briefing/ClientProfileCard'
import SessionModeSelector from '../components/briefing/SessionModeSelector'
import SessionTermsCard from '../components/briefing/SessionTermsCard'
import { FALLBACK_SCENARIOS } from '../data/fallbackScenarios'

export default function BriefingPage({
  scenario: propsScenario,
  initialMode = 'new',
  onStartSimulation,
  onBack: propsOnBack,
}) {
  const { scenarioId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()

  // Ambil data skenario dari props, state navigasi, atau fallback berdasarkan scenarioId
  const scenario = useMemo(() => {
    if (propsScenario) return propsScenario
    if (location.state?.scenario) return location.state.scenario
    if (scenarioId) {
      const found = FALLBACK_SCENARIOS.find(
        (s) => String(s.id) === String(scenarioId)
      )
      if (found) return found
    }
    return FALLBACK_SCENARIOS[0]
  }, [propsScenario, location.state, scenarioId])

  const hasContinueOption =
    scenario.attempt_status === 'attempted' ||
    Boolean(scenario.last_completed_session_id) ||
    Boolean(scenario.parentSessionId)

  const [selectedMode, setSelectedMode] = useState(
    initialMode === 'continue' && hasContinueOption ? 'continue' : 'new'
  )
  const [isStarting, setIsStarting] = useState(false)

  const handleBack = () => {
    if (propsOnBack) {
      propsOnBack()
    } else {
      navigate('/latihan-mandiri')
    }
  }

  // Contoh topik sesi sebelumnya, dipakai hanya bila backend tidak dapat dihubungi
  const sampleTopics = [
    {
      id: 1,
      title: 'Eksplorasi Keluhan Utama',
      timeRange: '00:00 – 02:45',
      response:
        'Klien mengutarakan rasa lelah luar biasa membagi waktu antara jadwal kuliah padat, modul praktikum lab, dan kepanitiaan BEM.',
      isLastActive: false,
    },
    {
      id: 2,
      title: 'Skala Prioritas & Hambatan',
      timeRange: '02:46 – 05:30',
      response:
        'Klien mengaku kesulitan menolak permintaan tolong rekan organisasi, memicu penumpukan tugas hingga larut malam.',
      isLastActive: false,
    },
    {
      id: 3,
      title: 'Eksplorasi Ambivalensi & Perasaan Bersalah',
      timeRange: '05:31 – 08:12',
      response:
        'Klien mulai membuka diri bahwa ada keinginan mengurangi beban organisasi tapi cemas dicap tidak bertanggung jawab. Di sinilah percakapan terakhir terhenti.',
      isLastActive: true,
    },
  ]

  // Topik sesi induk dari backend (hanya topik yang sudah memiliki catatan)
  const parentSessionId =
    scenario.parentSessionId || scenario.last_completed_session_id || null
  const [fetchedTopics, setFetchedTopics] = useState(null)

  useEffect(() => {
    if (selectedMode !== 'continue' || !parentSessionId) return undefined
    let isMounted = true
    fetch(
      `http://localhost:8000/api/v1/sessions/${parentSessionId}/briefing-topics`,
      { headers: { 'X-Dev-User-Id': '1' } }
    )
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((data) => {
        if (!isMounted) return
        const topics = Array.isArray(data.topics) ? data.topics : []
        setFetchedTopics(
          topics.map((t, idx) => ({
            id: idx + 1,
            title: t.name,
            response: t.description,
            isLastActive: idx === topics.length - 1,
          }))
        )
      })
      .catch((err) => {
        console.warn('Gagal memuat topik sesi sebelumnya, memakai contoh lokal:', err)
      })
    return () => {
      isMounted = false
    }
  }, [selectedMode, parentSessionId])

  const previousTopics = fetchedTopics ?? sampleTopics

  const handleStart = async () => {
    setIsStarting(true)
    try {
      const parentId =
        selectedMode === 'continue'
          ? scenario.parentSessionId || scenario.last_completed_session_id || 1
          : null

      // Hubungkan ke endpoint POST /api/v1/sessions
      const res = await fetch('http://localhost:8000/api/v1/sessions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Dev-User-Id': '1',
        },
        body: JSON.stringify({
          scenario_id: scenario.id || scenario.scenarioId || 1,
          mode: selectedMode,
          parent_session_id: parentId,
          class_id: scenario.classId || null,
        }),
      })

      if (!res.ok) {
        throw new Error('Gagal membuat sesi di backend')
      }

      const sessionData = await res.json()
      const payload = {
        ...scenario,
        sessionId: sessionData.id,
        scenarioId: sessionData.scenario_id,
        mode: selectedMode,
        publicScenario: sessionData.scenario,
        scenarioTitle: scenario.title,
        clientName: scenario.client_name || scenario.clientName || 'Nadia Putri',
        clientAge: scenario.client_age || scenario.clientAge || 19,
        clientGender: scenario.client_gender || scenario.clientGender || 'Perempuan',
        clientRole: scenario.client_role || scenario.clientRole || 'Mahasiswa',
        maritalStatus: scenario.marital_status || scenario.maritalStatus || null,
        mainProblem: scenario.main_problem || scenario.problem || '',
        category: scenario.category || 'Latihan Mandiri',
      }

      if (onStartSimulation) {
        onStartSimulation(payload)
      } else {
        navigate(`/simulasi/${sessionData.id}`, { state: { scenario: payload } })
      }
    } catch (err) {
      console.warn('Backend offline / gagal koneksi, menggunakan fallback sesi lokal:', err)
      const fallbackId = Date.now()
      const fallbackPayload = {
        ...scenario,
        sessionId: fallbackId,
        scenarioId: scenario.id || 1,
        mode: selectedMode,
        scenarioTitle: scenario.title,
        clientName: scenario.client_name || scenario.clientName || 'Nadia Putri',
        clientAge: scenario.client_age || scenario.clientAge || 19,
        clientGender: scenario.client_gender || scenario.clientGender || 'Perempuan',
        clientRole: scenario.client_role || scenario.clientRole || 'Mahasiswa',
        maritalStatus: scenario.marital_status || scenario.maritalStatus || null,
        mainProblem: scenario.main_problem || scenario.problem || '',
        category: scenario.category || 'Latihan Mandiri',
      }

      if (onStartSimulation) {
        onStartSimulation(fallbackPayload)
      } else {
        navigate(`/simulasi/${fallbackId}`, {
          state: { scenario: fallbackPayload },
        })
      }
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 w-full pb-8">
      {/* 1. Header & Breadcrumb */}
      <BriefingHeader
        scenarioTitle={scenario.title}
        category={scenario.category || 'Latihan Mandiri'}
        onBack={handleBack}
      />

      {/* 2. Mode Selector (Hanya muncul jika skenario sudah pernah dicoba sebelumnya) */}
      {hasContinueOption && (
        <SessionModeSelector
          selectedMode={selectedMode}
          onSelectMode={setSelectedMode}
          lastSessionInfo={{
            attemptNo: 2,
            timestamp: '08:12',
            relativeTime: '2 hari lalu',
          }}
        />
      )}

      {/* 3. Grid Konten Utama: 7 Kolom Kiri (Profil Klien & Masalah) vs 5 Kolom Kanan (Ketentuan & Aksi) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Kolom Kiri */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <ClientProfileCard
            client={{
              name: scenario.client_name || scenario.clientName || 'Nadia Putri',
              age: scenario.client_age || 19,
              gender: scenario.client_gender || 'Perempuan',
              role: scenario.client_role || 'Semester 3 · Fakultas Psikologi',
              marital_status: scenario.marital_status || scenario.maritalStatus || null,
              problem:
                scenario.initial_summary ||
                scenario.main_problem ||
                scenario.problem ||
                'Nadia merasa sangat kewalahan membagi waktu antara beban perkuliahan reguler, penugasan praktikum laboratorium, dan komitmen tanggung jawab organisasi kemahasiswaan.',
              history_impact: scenario.history_impact || scenario.historyImpact || null,
              expectation_change_context:
                scenario.expectation_change_context ||
                scenario.expectationChangeContext ||
                scenario.change_target ||
                null,
              change_target: scenario.change_target || scenario.changeTarget || null,
            }}
            mode={selectedMode}
            category={scenario.category || 'Latihan Mandiri'}
            previousTopics={previousTopics}
            lastSavedTime="08:12"
          />
        </div>

        {/* Kolom Kanan */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <SessionTermsCard
            category={scenario.category || 'Latihan Mandiri'}
            mode={selectedMode}
            lastSavedTime="08:12"
            onStartSession={handleStart}
            onBack={handleBack}
            isLoading={isStarting}
          />

          <AudioCheckBar />
        </div>
      </div>
    </div>
  )
}

