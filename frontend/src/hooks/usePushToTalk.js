import { useCallback, useEffect, useRef, useState } from 'react'

// Satu rekaman = satu giliran konselor (Rubrik 2.6): tekan untuk mulai, tekan lagi untuk selesai,
// atau berhenti sendiri setelah jeda hening. Rekaman yang terlalu pendek atau hampir hening ditolak
// di sini, sebelum dikirim ke server, karena STT cenderung "mengarang" kalimat dari audio hening.
const MIN_DURATION_MS = 700
const MIN_PEAK_RMS = 0.015
// shortcut: ambang hening tetap, tidak menyesuaikan derau ruangan; naikkan bila di ruangan berisik rekaman tidak pernah berhenti sendiri.
const SILENCE_RMS = 0.01
const SILENCE_STOP_MS = 1800 // jeda setelah bicara sebelum rekaman berhenti sendiri
const NO_SPEECH_STOP_MS = 8000 // berhenti bila sama sekali tidak ada ucapan sejak mulai

function pickMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm']
  return types.find((t) => window.MediaRecorder?.isTypeSupported?.(t)) || ''
}

/** onAutoStop dipanggil sekali saat rekaman sebaiknya diakhiri karena hening. */
export default function usePushToTalk({ onAutoStop } = {}) {
  const onAutoStopRef = useRef(onAutoStop)
  useEffect(() => {
    onAutoStopRef.current = onAutoStop
  }, [onAutoStop])
  const [isRecording, setIsRecording] = useState(false)
  const stateRef = useRef(null)

  const cleanup = useCallback(() => {
    const s = stateRef.current
    if (!s) return
    cancelAnimationFrame(s.raf)
    s.stream.getTracks().forEach((t) => t.stop())
    s.audioCtx.close()
    stateRef.current = null
  }, [])

  /** Mulai merekam. Melempar Error berbahasa sederhana jika mikrofon tidak bisa dipakai. */
  const start = useCallback(async () => {
    if (stateRef.current) return
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      throw new Error('Browser ini tidak mendukung perekaman suara. Gunakan input teks.')
    }
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      throw new Error('Izin mikrofon ditolak. Izinkan mikrofon lewat ikon gembok di bilah alamat browser, atau gunakan input teks.')
    }
    const mimeType = pickMimeType()
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks = []
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data)

    // Ukur puncak volume selama merekam untuk mendeteksi rekaman hening.
    // Dibuat setelah await, jadi browser bisa membuatnya "suspended" (volume terbaca 0); paksa jalan.
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    if (audioCtx.state !== 'running') await audioCtx.resume().catch(() => {})
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 1024
    audioCtx.createMediaStreamSource(stream).connect(analyser)
    const data = new Float32Array(analyser.fftSize)
    const startedAt = performance.now()
    const s = { stream, recorder, chunks, audioCtx, peak: 0, startedAt, lastVoiceAt: startedAt, autoStopped: false, raf: 0 }
    const measure = () => {
      analyser.getFloatTimeDomainData(data)
      let sum = 0
      for (let i = 0; i < data.length; i += 1) sum += data[i] * data[i]
      const rms = Math.sqrt(sum / data.length)
      const now = performance.now()
      s.peak = Math.max(s.peak, rms)
      if (rms > SILENCE_RMS) s.lastVoiceAt = now
      const spoke = s.peak >= MIN_PEAK_RMS
      const silentTooLong = spoke ? now - s.lastVoiceAt > SILENCE_STOP_MS : now - startedAt > NO_SPEECH_STOP_MS
      if (!s.autoStopped && audioCtx.state === 'running' && silentTooLong) {
        s.autoStopped = true
        onAutoStopRef.current?.()
      }
      s.raf = requestAnimationFrame(measure)
    }
    measure()
    stateRef.current = s
    recorder.start(1000) // potongan per detik: snapshot() bisa mengambil rekaman sementara
    setIsRecording(true)
  }, [])

  /** Berhenti merekam. Hasil: { blob, durationMs }. Melempar Error jika rekaman tidak layak. */
  const stop = useCallback(async () => {
    const s = stateRef.current
    if (!s || s.stopping) return null // tombol "selesai" dan berhenti-otomatis bisa terjadi bersamaan
    s.stopping = true
    const stopped = new Promise((resolve) => {
      s.recorder.onstop = resolve
    })
    s.recorder.stop()
    await stopped
    const durationMs = performance.now() - s.startedAt
    const { peak, chunks, recorder } = s
    const measured = s.audioCtx.state === 'running' // bila tidak, cek hening diserahkan ke backend
    cleanup()
    setIsRecording(false)
    if (durationMs < MIN_DURATION_MS) throw new Error('Rekaman terlalu pendek. Tahan tombol selama kamu berbicara.')
    if (!chunks.length) throw new Error('Rekaman kosong. Periksa mikrofon yang dipilih browser, lalu coba lagi.')
    if (measured && peak < MIN_PEAK_RMS) throw new Error('Suaramu hampir tidak terdengar. Coba bicara lebih dekat ke mikrofon.')
    return { blob: new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }), durationMs }
  }, [cleanup])

  useEffect(() => cleanup, [cleanup])

  /** Rekaman sejauh ini (untuk teks sementara), atau null bila tidak sedang merekam. */
  const snapshot = useCallback(() => {
    const s = stateRef.current
    if (!s || s.stopping || !s.chunks.length) return null
    return new Blob(s.chunks, { type: s.recorder.mimeType || 'audio/webm' })
  }, [])

  return { start, stop, snapshot, isRecording }
}
