import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import SimulationHeader from '../components/simulation/SimulationHeader'
import VirtualClientStage from '../components/simulation/VirtualClientStage'
import { ErrorState } from '../components/dashboard/SectionState'
import Button from '../components/ui/Button'
import Toasts from '../components/ui/Toasts'
import { useRequest } from '../hooks/useRequest'
import { useToasts } from '../hooks/useToasts'
import useClientVoice from '../hooks/useClientVoice'
import { endSession, getSession, sendTurn } from '../services/sessions'
import { getClientAudio } from '../services/speech'

const formatTimestamp = (totalSecs) => {
  const mins = String(Math.floor(totalSecs / 60)).padStart(2, '0')
  const secs = String(totalSecs % 60).padStart(2, '0')
  return `${mins}:${secs}`
}

const toMessages = (session, counselorName) =>
  (session.turns || []).map((t) => ({
    sender: t.speaker,
    name: t.speaker === 'counselor' ? counselorName : session.scenario.client_name,
    time: formatTimestamp(Math.floor((t.start_ms || 0) / 1000)),
    text: t.content,
    isTyping: false,
    isTyped: t.input_mode === 'text',
  }))

const Screen = ({ children }) => (
  <div className="w-full min-h-screen flex flex-col items-center justify-center gap-3 bg-[#f4efe7] p-4">{children}</div>
)

export default function SimulationPage({ user }) {
  const { sessionId } = useParams()
  // key: pindah sesi memulai halaman dari nol, tanpa sisa data sesi sebelumnya.
  return <SimulationSession key={sessionId} sessionId={sessionId} user={user} />
}

// Memuat sesi, lalu memilih layar: memuat, gagal, sudah selesai, atau ruang simulasi.
function SimulationSession({ sessionId, user }) {
  const navigate = useNavigate()
  const load = useCallback(() => getSession(sessionId), [sessionId])
  const session = useRequest(load)
  const [endedHere, setEndedHere] = useState(false)

  if (session.data === undefined) {
    return (
      <Screen>
        {session.error ? (
          <>
            <ErrorState message={`Sesi tidak bisa dibuka. ${session.error.message}`} onRetry={session.reload} />
            <Button variant="outline" icon="arrow_back" onClick={() => navigate('/beranda')} className="min-h-10">
              Kembali ke beranda
            </Button>
          </>
        ) : (
          <p role="status" className="flex items-center gap-2 text-sm font-semibold text-[#352f55]">
            <span className="ss-spinner" aria-hidden="true" /> Memuat sesi…
          </p>
        )}
      </Screen>
    )
  }

  if (endedHere || session.data.status === 'completed') {
    const isClass = Boolean(session.data.class_id)
    return (
      <Screen>
        <div className="bg-white p-6 md:p-8 rounded-2xl shadow-xs border border-slate-100 flex flex-col items-center text-center gap-3 max-w-md">
          <div className="w-12 h-12 rounded-xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
            <span className="material-symbols-outlined text-[28px]" aria-hidden="true">task_alt</span>
          </div>
          <h1 className="text-lg md:text-xl text-[#1e1a34] font-bold">
            {endedHere ? 'Sesi telah diakhiri' : 'Sesi ini sudah selesai'}
          </h1>
          <p className="text-xs md:text-sm text-[#64748b]">
            Kamu bisa melihat hasil evaluasi sesi ini atau kembali ke {isClass ? 'beranda' : 'katalog latihan'}.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-2">
            <Button variant="outline" onClick={() => navigate(isClass ? '/beranda' : '/latihan-mandiri')}>
              {isClass ? 'Kembali ke beranda' : 'Kembali ke katalog'}
            </Button>
            <Button icon="analytics" onClick={() => navigate(`/evaluasi/${sessionId}`)}>
              Lihat Hasil Evaluasi
            </Button>
          </div>
        </div>
      </Screen>
    )
  }

  return <SimulationRoom session={session.data} user={user} onEnded={() => setEndedHere(true)} />
}

function SimulationRoom({ session, user, onEnded }) {
  const sessionId = session.id
  const { scenario } = session
  // Backend hanya mengirim ringkasan publik skenario (tanpa persona/kasus/hidden facts).
  const clientInfo = {
    name: scenario.client_name,
    age: scenario.client_age,
    gender: scenario.client_gender,
    avatarFile: scenario.client_avatar_file,
    role: scenario.client_role,
    problem: scenario.initial_summary,
  }
  const counselorName = user?.name || 'Konselor'

  // Garis waktu sesi (ms sejak simulasi dimulai) melanjutkan dari akhir giliran terakhir di server,
  // sehingga waktu saat mahasiswa pergi tidak terhitung.
  const [timelineStart] = useState(() => Math.max(0, ...(session.turns || []).map((t) => t.end_ms || 0)))
  const [origin] = useState(() => Date.now() - timelineStart)
  const getElapsedMs = () => Date.now() - origin
  const lastSentRef = useRef(0)

  const [messages, setMessages] = useState(() => toMessages(session, counselorName))
  const [isProcessing, setIsProcessing] = useState(false)
  const [isEnding, setIsEnding] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(() => Math.floor(timelineStart / 1000))
  const [voiceError, setVoiceError] = useState(null)
  // Ekspresi wajah avatar dari respons giliran terakhir (label kasar dari backend, bukan Client State)
  const [clientExpression, setClientExpression] = useState('neutral')
  const voice = useClientVoice()
  const { toasts, addToast, dismissToast } = useToasts()

  // Fungsi pembatal animasi teks klien yang sedang berjalan (efek ketik atau mengikuti suara)
  const typingTimerRef = useRef(null)
  const isOpenRef = useRef(true)

  useEffect(() => {
    const timer = setInterval(() => setElapsedSeconds(Math.floor((Date.now() - origin) / 1000)), 500)
    return () => clearInterval(timer)
  }, [origin])

  // Saat ruang ditutup: hentikan efek ketik dan jangan memutar suara yang baru tiba.
  useEffect(() => {
    isOpenRef.current = true
    return () => {
      isOpenRef.current = false
      typingTimerRef.current?.()
    }
  }, [])

  // Menampilkan jawaban klien di transkrip. Bila suara klien diputar, teks muncul mengikuti suaranya
  // (waktu per huruf dari ElevenLabs); bila suara gagal atau menunggu izin autoplay, memakai efek ketik.
  const showClientResponse = (fullText, turnNo) => {
    typingTimerRef.current?.()
    typingTimerRef.current = null

    setMessages((prev) => [
      ...prev,
      {
        sender: 'client',
        name: clientInfo.name,
        time: formatTimestamp(Math.floor(getElapsedMs() / 1000)),
        text: '',
        isTyping: true,
      },
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
    getClientAudio(sessionId, turnNo)
      .then((speech) => isOpenRef.current && voice.speak({ ...speech, text: fullText }))
      .then((playing) => (playing ? followVoice() : typewriter()))
      .catch((err) => {
        setVoiceError(err.message)
        typewriter()
      })
  }

  // timing (input suara): { start_ms, end_ms, words } dari STT. Ketikan tidak punya durasi bicara:
  // awal dan akhirnya sama dengan saat dikirim, tanpa words.
  // Mengembalikan false bila pesan tidak tersimpan, agar masukan dikembalikan ke mahasiswa.
  const handleSendMessage = async (text, timing = null) => {
    if (timing && timing.start_ms < lastSentRef.current) {
      setVoiceError('Rekaman ini dibuat sebelum giliran terakhir. Rekam ulang.')
      return false
    }
    const sentMs = getElapsedMs()
    const turn = timing || { start_ms: sentMs, end_ms: sentMs }
    const counselorMsg = {
      sender: 'counselor',
      name: counselorName,
      time: formatTimestamp(Math.floor(turn.start_ms / 1000)),
      text,
      isTyped: !timing,
    }

    setMessages((prev) => [...prev, counselorMsg])
    setIsProcessing(true)

    try {
      const data = await sendTurn(sessionId, { content: text, ...turn, sent_ms: sentMs })
      lastSentRef.current = sentMs
      setClientExpression(data.expression || 'neutral')
      showClientResponse(data.content, data.turn_no)
      return true
    } catch (err) {
      // Balasan bisa hilang di jalan padahal giliran sudah tersimpan: cek server agar tidak terkirim dua kali.
      const fresh = await getSession(sessionId).catch(() => null)
      setIsProcessing(false)
      if (fresh?.turns?.some((t) => t.speaker === 'counselor' && t.start_ms === turn.start_ms && t.content === text)) {
        setMessages(toMessages(fresh, counselorName))
        return true
      }
      setMessages((prev) => prev.filter((m) => m !== counselorMsg))
      if (fresh?.status === 'completed') onEnded()
      else addToast('error', `Pesan belum terkirim. ${err.message}`)
      return false
    }
  }

  const handleConfirmExit = async () => {
    if (!window.confirm('Apakah Anda yakin ingin mengakhiri sesi latihan ini sekarang?')) return
    setIsEnding(true)
    try {
      await endSession(sessionId, getElapsedMs())
    } catch (err) {
      setIsEnding(false)
      addToast('error', `Sesi belum diakhiri. ${err.message}`)
      return
    }
    voice.stop()
    onEnded()
  }

  return (
    <div className="w-full h-screen flex flex-col bg-[#f4efe7] text-[#1e1a34] overflow-hidden select-none">
      {/* 1. Header Bar: Navbar Putih dengan Timer di samping tombol Akhiri Sesi */}
      <SimulationHeader
        scenarioTitle={scenario.title}
        category={session.class_id ? 'Latihan Kelas' : 'Latihan Mandiri'}
        elapsedSeconds={elapsedSeconds}
        onExitSession={handleConfirmExit}
        isEnding={isEnding}
      />

      {/* 2. Workspace Area (tema terang) */}
      <div className="flex-1 flex flex-col md:flex-row relative w-full h-[calc(100vh-56px)] overflow-hidden bg-[#f4efe7]">
        {/* Central Stage */}
        <VirtualClientStage
          client={clientInfo}
          onSendMessage={handleSendMessage}
          isProcessing={isProcessing || isEnding}
          messages={messages}
          sessionId={sessionId}
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

      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}
