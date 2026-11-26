import { useEffect, useRef, useState } from 'react'
import usePushToTalk from '../../hooks/usePushToTalk'
import { transcribeAudio } from '../../services/speech'

const PREVIEW_MS = 3000 // ~20 permintaan/menit selama merekam: di bawah batas laju Groq

// Tombol bicara: tekan untuk mulai, tekan lagi untuk selesai, atau berhenti sendiri saat hening.
// Lalu panel tinjau transkrip (kirim atau rekam ulang). Satu rekaman = satu giliran konselor.
// onSend(text, { start_ms, end_ms, words }) mengirim giliran; hasilnya false bila tidak tersimpan.
export default function VoiceInput({ sessionId, getElapsedMs, onSend, onPress, disabled }) {
  const finishRef = useRef(null)
  const { start, stop, snapshot, isRecording } = usePushToTalk({ onAutoStop: () => finishRef.current?.() })
  const [liveText, setLiveText] = useState('')
  const [phase, setPhase] = useState('idle') // idle | starting | recording | transcribing | review
  const [review, setReview] = useState(null)
  const [error, setError] = useState(null)
  const startedAtRef = useRef(0)

  const begin = async () => {
    onPress?.() // interaksi pengguna: kesempatan membuka kunci audio klien
    setError(null)
    setReview(null)
    setPhase('starting')
    startedAtRef.current = getElapsedMs()
    try {
      await start()
      setPhase('recording')
    } catch (err) {
      setPhase('idle')
      setError(err.message)
    }
  }

  const toggle = () => {
    if (disabled) return
    if (phase === 'recording') finish()
    else if (phase === 'idle' || phase === 'review') begin()
  }

  const finish = async () => {
    setPhase('transcribing')
    let recording
    try {
      recording = await stop()
    } catch (err) {
      setPhase('idle')
      setError(err.message)
      return
    }
    if (!recording) return
    try {
      const result = await transcribeAudio(sessionId, recording.blob)
      const offset = startedAtRef.current
      const words = result.words.map((w) => ({ word: w.word, start_ms: offset + w.start_ms, end_ms: offset + w.end_ms }))
      setReview({
        text: result.text,
        words,
        start_ms: words[0]?.start_ms ?? offset,
        end_ms: words.at(-1)?.end_ms ?? offset + Math.round(recording.durationMs),
      })
      setPhase('review')
    } catch (err) {
      setPhase('idle')
      setError(err.message)
    }
  }

  const send = async () => {
    const sent = review
    const { text, ...timing } = sent
    setReview(null)
    setPhase('idle')
    if (!(await onSend(text, timing))) {
      // Gagal terkirim: rekaman ditampilkan lagi agar bisa dikirim ulang tanpa merekam ulang.
      setReview(sent)
      setPhase('review')
    }
  }

  useEffect(() => {
    finishRef.current = finish
  })

  // Teks sementara: rekaman sejauh ini dikirim ke Groq tiap PREVIEW_MS, satu permintaan dalam satu waktu.
  // shortcut: setiap kirim ditagih Groq minimal 10 detik audio; perbesar PREVIEW_MS bila kuota cepat habis.
  useEffect(() => {
    if (phase !== 'recording') return undefined
    let alive = true
    let inFlight = false
    const id = setInterval(async () => {
      const blob = !inFlight && snapshot()
      if (!blob) return
      inFlight = true
      try {
        const { text } = await transcribeAudio(sessionId, blob, { preview: true })
        if (alive) setLiveText(text)
      } catch {
        // Pratinjau boleh gagal (mis. belum ada ucapan); transkrip akhir tetap diambil saat selesai.
      } finally {
        inFlight = false
      }
    }, PREVIEW_MS)
    return () => {
      alive = false
      clearInterval(id)
      setLiveText('')
    }
  }, [phase, sessionId, snapshot])

  const busy = phase === 'transcribing' || phase === 'starting'
  return (
    <div className="relative shrink-0">
      {(review || error || busy || isRecording) && (
        <div className="absolute bottom-full right-0 mb-3 w-[min(22rem,calc(100vw-3rem))] bg-white rounded-2xl shadow-2xl border border-slate-100 p-3.5 text-[#1e1a34] ss-fade-up">
          {isRecording && (
            <p className="text-xs font-semibold flex items-center gap-2" role="status">
              <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" /> Mendengarkan… tekan lagi jika sudah selesai, atau diam sejenak.
            </p>
          )}
          {isRecording && liveText && (
            <p className="mt-2 text-sm leading-relaxed text-slate-500 italic" aria-live="polite">{liveText}…</p>
          )}
          {busy && (
            <p className="text-xs font-semibold flex items-center gap-2" role="status">
              <span className="material-symbols-outlined animate-spin text-[16px]">progress_activity</span> Mengubah suara menjadi teks…
            </p>
          )}
          {error && (
            <p className="text-xs text-rose-700 flex gap-1.5" role="alert">
              <span className="material-symbols-outlined text-[16px]">error</span>
              {error}
            </p>
          )}
          {review && (
            <div className="flex flex-col gap-2.5">
              <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Yang terdengar</span>
              <p className="text-sm leading-relaxed">“{review.text}”</p>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={begin}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-[#352f55] text-xs font-bold flex items-center gap-1 active:scale-95 transition"
                >
                  <span className="material-symbols-outlined text-[16px]">replay</span> Rekam ulang
                </button>
                <button
                  type="button"
                  onClick={send}
                  disabled={disabled}
                  className="px-3 py-1.5 rounded-lg bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] text-xs font-bold flex items-center gap-1 active:scale-95 transition disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-[16px]">send</span> Kirim
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      <button
        type="button"
        onClick={toggle}
        disabled={disabled || busy}
        aria-pressed={isRecording}
        aria-label={isRecording ? 'Selesai bicara' : 'Bicara'}
        title={isRecording ? 'Selesai bicara' : 'Bicara'}
        className={`h-11 w-11 shrink-0 rounded-xl flex items-center justify-center transition border select-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
          isRecording
            ? 'bg-slate-400 text-white border-slate-400 scale-105 shadow-[0_0_0_4px_rgba(148,163,184,0.3)]'
            : 'bg-[#352f55] text-white border-[#352f55] hover:bg-[#453b6a]'
        }`}
      >
        <span className={`material-symbols-outlined text-xl ${busy ? 'animate-spin' : ''}`} aria-hidden="true">
          {isRecording ? 'stop' : busy ? 'progress_activity' : 'mic'}
        </span>
      </button>
    </div>
  )
}
