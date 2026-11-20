import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import SimulationHeader from '../components/simulation/SimulationHeader'
import VirtualClientStage from '../components/simulation/VirtualClientStage'
import TranscriptPanel from '../components/simulation/TranscriptPanel'
import Button from '../components/ui/Button'
import { FALLBACK_SCENARIOS } from '../data/fallbackScenarios'
import { apiUrl } from '../config'

export default function SimulationPage({
  scenario: propsScenario,
  onExitSession,
}) {
  const { sessionId: paramSessionId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()

  const scenario =
    propsScenario ||
    location.state?.scenario || {
      title: 'Menavigasi Kelelahan Akademik dan Beban Organisasi',
      category: 'Latihan Mandiri',
      clientName: 'Nadia Putri',
    }

  const currentSessionId = paramSessionId || scenario.sessionId

  // State untuk menyimpan detail sesi asli dari backend jika tersedia
  const [sessionDetail, setSessionDetail] = useState(null)

  // Skenario fallback jika skenario tidak memiliki metadata lengkap
  const fallbackScenario = useMemo(() => {
    const idToFind = scenario?.scenarioId || scenario?.id || 1
    return (
      FALLBACK_SCENARIOS.find((s) => String(s.id) === String(idToFind)) ||
      FALLBACK_SCENARIOS[0]
    )
  }, [scenario])

  // Menentukan data info klien dari database snapshot, navigation state, atau fallback
  const clientInfo = useMemo(() => {
    // Backend hanya mengirim ringkasan publik skenario (tanpa persona/kasus/hidden facts)
    const pub = sessionDetail?.scenario || scenario?.publicScenario
    if (pub?.client_name) {
      return {
        name: pub.client_name,
        age: pub.client_age || scenario.clientAge || fallbackScenario.client_age,
        gender: pub.client_gender || scenario.clientGender || fallbackScenario.client_gender,
        role: pub.client_role || scenario.clientRole || fallbackScenario.client_role,
        maritalStatus:
          scenario.maritalStatus ||
          scenario.marital_status ||
          fallbackScenario.marital_status,
        problem:
          pub.initial_summary ||
          scenario.mainProblem ||
          scenario.main_problem ||
          scenario.problem ||
          fallbackScenario.main_problem,
      }
    }

    return {
      name:
        scenario.client_name ||
        scenario.clientName ||
        fallbackScenario.client_name,
      age:
        scenario.client_age ||
        scenario.clientAge ||
        fallbackScenario.client_age,
      gender:
        scenario.client_gender ||
        scenario.clientGender ||
        fallbackScenario.client_gender,
      role:
        scenario.client_role ||
        scenario.clientRole ||
        fallbackScenario.client_role,
      maritalStatus:
        scenario.marital_status ||
        scenario.maritalStatus ||
        fallbackScenario.marital_status,
      problem:
        scenario.main_problem ||
        scenario.mainProblem ||
        scenario.problem ||
        fallbackScenario.main_problem,
    }
  }, [sessionDetail, scenario, fallbackScenario])

  const activeClientName = clientInfo.name
  const activeTitle =
    sessionDetail?.scenario?.title ||
    scenario.scenarioTitle ||
    scenario.title ||
    fallbackScenario.title ||
    'Latihan Konseling'
  const activeCategory =
    scenario.category ||
    (sessionDetail?.class_id ? 'Latihan Kelas' : 'Latihan Mandiri')

  // Mengambil nama konselor yang sedang login atau fallback
  const activeCounselorName = (() => {
    try {
      const raw = localStorage.getItem('safesesi_auth_user')
      if (raw) {
        const parsed = JSON.parse(raw)
        return parsed.username || 'Rani Aulia'
      }
    } catch {
      // ignore
    }
    return 'Rani Aulia'
  })()

  const [messages, setMessages] = useState([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [clientStatus, setClientStatus] = useState('Mendengarkan aktif')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [sessionEnded, setSessionEnded] = useState(false)

  // State untuk Panel Transkrip (Buka/Tutup & Ukuran Lebar)
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(true)
  const [transcriptWidth, setTranscriptWidth] = useState(340)

  // Ref untuk timer efek mengetik (typewriter)
  const typingTimerRef = useRef(null)

  // Timer sesi aktif berjalan otomatis dari 00:00
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Bersihkan timer efek mengetik saat unmount
  useEffect(() => {
    return () => {
      if (typingTimerRef.current) {
        clearInterval(typingTimerRef.current)
      }
    }
  }, [])

  const formatTimestamp = (totalSecs) => {
    const mins = String(Math.floor(totalSecs / 60)).padStart(2, '0')
    const secs = String(totalSecs % 60).padStart(2, '0')
    return `${mins}:${secs}`
  }

  // Muat riwayat dialog & detail snapshot dari backend jika memiliki currentSessionId
  useEffect(() => {
    let isMounted = true
    if (currentSessionId) {
      fetch(apiUrl(`/api/v1/sessions/${currentSessionId}`), {
        headers: {
          'X-Dev-User-Id': '1',
        },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!isMounted || !data) return
          setSessionDetail(data)
          if (Array.isArray(data.turns) && data.turns.length > 0) {
            const clientSpeakerName =
              data.scenario?.client_name || activeClientName
            const loaded = data.turns.map((t) => ({
              sender: t.speaker,
              name:
                t.speaker === 'counselor'
                  ? activeCounselorName
                  : clientSpeakerName,
              time: formatTimestamp(Math.floor((t.start_ms || 0) / 1000)),
              text: t.content,
              isTyping: false,
            }))
            setMessages(loaded)
          }
        })
        .catch((err) => {
          console.warn('Gagal memuat detail sesi:', err)
        })
    }
    return () => {
      isMounted = false
    }
  }, [currentSessionId, activeCounselorName, activeClientName])

  // Menjalankan animasi efek diketik (typewriter effect) karakter per karakter
  const typeOutResponse = (fullText) => {
    if (typingTimerRef.current) {
      clearInterval(typingTimerRef.current)
    }

    setClientStatus('Sedang berbicara...')
    const responseTime = formatTimestamp(elapsedSeconds)

    // Tambahkan entri klien kosong awal dengan isTyping: true
    setMessages((prev) => [
      ...prev,
      {
        sender: 'client',
        name: activeClientName,
        time: responseTime,
        text: '',
        isTyping: true,
      },
    ])

    let charIndex = 0
    // Kecepatan adaptif: teks panjang diketik lebih cepat agar pengguna tidak menunggu lama
    const charDelay = fullText.length > 200 ? 14 : fullText.length > 100 ? 18 : 22

    typingTimerRef.current = setInterval(() => {
      charIndex += 1
      if (charIndex <= fullText.length) {
        const partialText = fullText.slice(0, charIndex)
        setMessages((prev) => {
          if (prev.length === 0) return prev
          const copy = [...prev]
          const lastIdx = copy.length - 1
          if (copy[lastIdx].sender === 'client') {
            copy[lastIdx] = {
              ...copy[lastIdx],
              text: partialText,
              isTyping: charIndex < fullText.length,
            }
          }
          return copy
        })
      } else {
        clearInterval(typingTimerRef.current)
        typingTimerRef.current = null
        setIsProcessing(false)
        setClientStatus('Mendengarkan aktif')
      }
    }, charDelay)
  }

  const handleSendMessage = async (text) => {
    const counselorMsg = {
      sender: 'counselor',
      name: activeCounselorName,
      time: formatTimestamp(elapsedSeconds),
      text,
    }

    setMessages((prev) => [...prev, counselorMsg])
    setIsProcessing(true)
    setClientStatus('Sedang berpikir...')

    if (!currentSessionId) {
      setIsProcessing(false)
      setClientStatus('Mendengarkan aktif')
      alert('Sesi simulasi tidak valid. Silakan mulai sesi dari halaman Briefing.')
      return
    }

    // 100% LLM: Hubungkan langsung ke endpoint /turns di backend
    try {
      const res = await fetch(
        apiUrl(`/api/v1/sessions/${currentSessionId}/turns`),
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Dev-User-Id': '1',
          },
          body: JSON.stringify({
            content: text,
            start_ms: elapsedSeconds * 1000,
            end_ms: (elapsedSeconds + 1) * 1000,
          }),
        }
      )

      if (res.ok) {
        const data = await res.json()
        typeOutResponse(data.content)
      } else {
        let errorMsg = 'Layanan AI sedang mengalami kendala teknis.'
        try {
          const errData = await res.json()
          if (errData.detail) errorMsg = errData.detail
        } catch {
          // ignore
        }
        setIsProcessing(false)
        setClientStatus('Mendengarkan aktif')
        alert(`Kendala Layanan AI: ${errorMsg}`)
      }
    } catch (err) {
      console.error('Gagal terhubung ke backend LLM:', err)
      setIsProcessing(false)
      setClientStatus('Mendengarkan aktif')
      alert('Tidak dapat terhubung ke server backend. Pastikan server backend sedang aktif.')
    }
  }

  const handleStartResize = (e) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = transcriptWidth

    const handleMouseMove = (moveEvent) => {
      const delta = startX - moveEvent.clientX
      const newWidth = Math.min(Math.max(startWidth + delta, 260), 560)
      setTranscriptWidth(newWidth)
    }

    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }

  const handleConfirmExit = async () => {
    if (
      window.confirm(
        'Apakah Anda yakin ingin mengakhiri sesi latihan ini sekarang?'
      )
    ) {
      if (currentSessionId) {
        try {
          await fetch(
            apiUrl(`/api/v1/sessions/${currentSessionId}/end`),
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-Dev-User-Id': '1',
              },
            }
          )
        } catch (e) {
          console.warn('Gagal mengakhiri sesi di backend:', e)
        }
      }
      if (onExitSession) {
        onExitSession()
      } else {
        setSessionEnded(true)
      }
    }
  }

  if (sessionEnded) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-[#352f55] p-4">
        <div className="bg-white p-6 md:p-8 rounded-2xl shadow-xs border border-slate-100 flex flex-col items-center text-center gap-3 max-w-md">
          <div className="w-12 h-12 rounded-xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
            <span className="material-symbols-outlined text-[28px]">task_alt</span>
          </div>
          <h2 className="text-lg md:text-xl text-[#1e1a34] font-bold">Sesi telah diakhiri</h2>
          <p className="text-xs md:text-sm text-[#64748b]">
            Kamu bisa melihat hasil evaluasi sesi ini atau kembali ke katalog latihan.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-2">
            <Button variant="outline" onClick={() => navigate('/latihan-mandiri')}>
              Kembali ke katalog
            </Button>
            {currentSessionId && (
              <Button icon="analytics" onClick={() => navigate(`/evaluasi/${currentSessionId}`)}>
                Lihat Hasil Evaluasi
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full h-screen flex flex-col bg-[#352f55] text-white overflow-hidden select-none">
      {/* 1. Header Bar: Navbar Putih dengan Timer di samping tombol Akhiri Sesi */}
      <SimulationHeader
        scenarioTitle={activeTitle}
        category={activeCategory}
        elapsedSeconds={elapsedSeconds}
        onExitSession={handleConfirmExit}
        isTranscriptOpen={isTranscriptOpen}
        onToggleTranscript={() => setIsTranscriptOpen((prev) => !prev)}
      />

      {/* 2. Workspace Area: Background Ungu Beranda (#352f55) */}
      <div className="flex-1 flex flex-col md:flex-row relative w-full h-[calc(100vh-56px)] overflow-hidden bg-[#352f55]">
        {/* Central Stage */}
        <VirtualClientStage
          client={clientInfo}
          clientName={activeClientName}
          clientStatus={clientStatus}
          onSendMessage={handleSendMessage}
          isProcessing={isProcessing}
          isTranscriptOpen={isTranscriptOpen}
          onOpenTranscript={() => setIsTranscriptOpen(true)}
        />

        {/* Right Transcript Panel: Collapsible & Resizable */}
        {isTranscriptOpen && (
          <TranscriptPanel
            messages={messages}
            width={transcriptWidth}
            onClose={() => setIsTranscriptOpen(false)}
            onStartResize={handleStartResize}
          />
        )}
      </div>
    </div>
  )
}
