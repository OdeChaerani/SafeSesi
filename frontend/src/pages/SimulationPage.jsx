import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import SimulationHeader from '../components/simulation/SimulationHeader'
import VirtualClientStage from '../components/simulation/VirtualClientStage'
import Button from '../components/ui/Button'
import { FALLBACK_SCENARIOS } from '../data/fallbackScenarios'
import { endSession, getSession, sendTurn } from '../services/sessions'
import useClientVoice from '../hooks/useClientVoice'
import { getClientAudio } from '../services/speech'

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
        avatarFile: pub.client_avatar_file || scenario.client_avatar_file || null,
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
      avatarFile: scenario.client_avatar_file || null,
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [sessionEnded, setSessionEnded] = useState(false)
  const [voiceError, setVoiceError] = useState(null)
  // Ekspresi wajah avatar dari respons giliran terakhir (label kasar dari backend, bukan Client State)
  const [clientExpression, setClientExpression] = useState('neutral')
  const voice = useClientVoice()
  // Jam sesi (ms sejak halaman simulasi dibuka); sama dengan asal elapsedSeconds.
  const [sessionStart] = useState(() => Date.now())
  const getElapsedMs = () => Date.now() - sessionStart

  // State untuk Panel Transkrip (Buka/Tutup & Ukuran Lebar)

  // Fungsi pembatal animasi teks klien yang sedang berjalan (efek ketik atau mengikuti suara)
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
        typingTimerRef.current()
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
      getSession(currentSessionId)
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

  // Menampilkan jawaban klien di transkrip. Bila suara klien diputar, teks muncul mengikuti suaranya
  // (waktu per huruf dari ElevenLabs); bila suara gagal atau menunggu izin autoplay, memakai efek ketik.
  const showClientResponse = (fullText, turnNo) => {
    typingTimerRef.current?.()
    typingTimerRef.current = null

    setMessages((prev) => [
      ...prev,
      { sender: 'client', name: activeClientName, time: formatTimestamp(elapsedSeconds), text: '', isTyping: true },
    ])
    const setClientText = (text, isTyping) =>
      setMessages((prev) => {
        const last = prev.length - 1
        if (last < 0 || prev[last].sender !== 'client') return prev
        const copy = [...prev]
        copy[last] = { ...copy[last], text, isTyping }
        return copy
      })
    const finish = () => {
      typingTimerRef.current = null
      setClientText(fullText, false)
      setIsProcessing(false)
    }

    const typewriter = () => {
      let charIndex = 0
      // Kecepatan adaptif: teks panjang diketik lebih cepat agar pengguna tidak menunggu lama
      const charDelay = fullText.length > 200 ? 14 : fullText.length > 100 ? 18 : 22
      const id = setInterval(() => {
        charIndex += 1
        if (charIndex < fullText.length) setClientText(fullText.slice(0, charIndex), true)
        else {
          clearInterval(id)
          finish()
        }
      }, charDelay)
      typingTimerRef.current = () => clearInterval(id)
    }

    const followVoice = () => {
      let raf
      let shown = -1
      const tick = () => {
        const spoken = voice.getCaption()
        if (spoken === null) return finish() // suara selesai atau dihentikan
        if (spoken.length !== shown) {
          shown = spoken.length
          setClientText(spoken, true)
        }
        raf = requestAnimationFrame(tick)
      }
      tick()
      typingTimerRef.current = () => cancelAnimationFrame(raf)
    }

    setVoiceError(null)
    getClientAudio(currentSessionId, turnNo)
      .then((speech) => voice.speak({ ...speech, text: fullText }))
      .then((playing) => (playing ? followVoice() : typewriter()))
      .catch((err) => {
        setVoiceError(err.message)
        typewriter()
      })
  }

  // timing (input suara): { start_ms, end_ms, words } dari STT; input teks memakai jam sesi.
  const handleSendMessage = async (text, timing = null) => {
    const counselorMsg = {
      sender: 'counselor',
      name: activeCounselorName,
      time: formatTimestamp(elapsedSeconds),
      text,
    }

    setMessages((prev) => [...prev, counselorMsg])
    setIsProcessing(true)

    if (!currentSessionId) {
      setIsProcessing(false)
      alert('Sesi simulasi tidak valid. Silakan mulai sesi dari halaman Briefing.')
      return
    }

    // 100% LLM: Hubungkan langsung ke endpoint /turns di backend
    try {
      const data = await sendTurn(
        currentSessionId,
        timing
          ? { content: text, ...timing }
          : { content: text, start_ms: elapsedSeconds * 1000, end_ms: (elapsedSeconds + 1) * 1000 }
      )
      setClientExpression(data.expression || 'neutral')
      showClientResponse(data.content, data.turn_no)
    } catch (err) {
      console.error('Gagal mengirim giliran:', err)
      setIsProcessing(false)
      alert(err.status === 0 ? err.message : `Kendala Layanan AI: ${err.message}`)
    }
  }

  const handleConfirmExit = async () => {
    if (
      window.confirm(
        'Apakah Anda yakin ingin mengakhiri sesi latihan ini sekarang?'
      )
    ) {
      if (currentSessionId) {
        try {
          await endSession(currentSessionId)
        } catch (e) {
          console.warn('Gagal mengakhiri sesi di backend:', e)
        }
      }
      voice.stop()
      if (onExitSession) {
        onExitSession()
      } else {
        setSessionEnded(true)
      }
    }
  }

  if (sessionEnded) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-[#f4efe7] p-4">
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
    <div className="w-full h-screen flex flex-col bg-[#f4efe7] text-[#1e1a34] overflow-hidden select-none">
      {/* 1. Header Bar: Navbar Putih dengan Timer di samping tombol Akhiri Sesi */}
      <SimulationHeader
        scenarioTitle={activeTitle}
        category={activeCategory}
        elapsedSeconds={elapsedSeconds}
        onExitSession={handleConfirmExit}
      />

      {/* 2. Workspace Area (tema terang) */}
      <div className="flex-1 flex flex-col md:flex-row relative w-full h-[calc(100vh-56px)] overflow-hidden bg-[#f4efe7]">
        {/* Central Stage */}
        <VirtualClientStage
          client={clientInfo}
          clientName={activeClientName}
          onSendMessage={handleSendMessage}
          isProcessing={isProcessing}
          messages={messages}
          sessionId={currentSessionId}
          getElapsedMs={getElapsedMs}
          voice={voice}
          expression={clientExpression}
        />

        {voiceError && (
          <div className="absolute top-16 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-white text-[#1e1a34] text-xs px-3 py-2 rounded-xl shadow-xl border border-amber-200" role="alert">
            <span className="material-symbols-outlined text-[16px] text-amber-600">volume_off</span>
            <span>{voiceError}</span>
            <button type="button" onClick={() => setVoiceError(null)} className="text-slate-400 hover:text-slate-600" aria-label="Tutup">
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        )}

      </div>
    </div>
  )
}
