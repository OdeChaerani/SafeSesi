import { useCallback, useEffect, useRef, useState } from 'react'

// Memutar suara klien lewat Web Audio; avatar membaca viseme yang aktif (atau volume, bila cue tidak ada) untuk lip-sync.
// Browser hanya mengizinkan audio setelah interaksi pengguna: panggil unlock() di dalam handler klik/tekan.
export default function useClientVoice() {
  const ctxRef = useRef(null)
  const analyserRef = useRef(null)
  const sourceRef = useRef(null)
  const dataRef = useRef(null)
  const pendingRef = useRef(null)
  const playingRef = useRef(null) // { visemes, charEndMs, text, durationMs, startedAt (detik AudioContext) }
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [needsUnlock, setNeedsUnlock] = useState(false)

  const context = useCallback(() => {
    if (!ctxRef.current) {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      analyser.connect(ctx.destination)
      ctxRef.current = ctx
      analyserRef.current = analyser
      dataRef.current = new Float32Array(analyser.fftSize)
    }
    return ctxRef.current
  }, [])

  const playBuffer = useCallback(async ({ audio, visemes = [], charEndMs = [], text = '' }) => {
    const ctx = context()
    const buffer = await ctx.decodeAudioData(audio)
    sourceRef.current?.stop()
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(analyserRef.current)
    source.onended = () => {
      if (sourceRef.current === source) {
        sourceRef.current = null
        playingRef.current = null
        setIsSpeaking(false)
      }
    }
    sourceRef.current = source
    playingRef.current = { visemes, charEndMs, text, durationMs: buffer.duration * 1000, startedAt: ctx.currentTime }
    setIsSpeaking(true)
    source.start()
  }, [context])

  const unlock = useCallback(async () => {
    const ctx = context()
    if (ctx.state !== 'running') await ctx.resume()
    if (pendingRef.current) {
      const pending = pendingRef.current
      pendingRef.current = null
      setNeedsUnlock(false)
      await playBuffer(pending)
    }
  }, [context, playBuffer])

  // speech = { audio: ArrayBuffer, visemes: [{viseme, start_ms, end_ms}], charEndMs?: [ms per huruf], text?: string }
  // Hasil: true bila suara langsung diputar, false bila menunggu ketukan (autoplay diblokir browser).
  const speak = useCallback(async (speech) => {
    if (context().state !== 'running') {
      pendingRef.current = speech
      setNeedsUnlock(true)
      return false
    }
    await playBuffer(speech)
    return true
  }, [context, playBuffer])

  const stop = useCallback(() => {
    sourceRef.current?.stop()
    sourceRef.current = null
    playingRef.current = null
    setIsSpeaking(false)
  }, [])

  // Dibaca tiap frame oleh avatar. null = diam; viseme null di antara cue (jeda) atau bila cue tidak ada (hasCues false).
  const getSpeech = useCallback(() => {
    const analyser = analyserRef.current
    const playing = playingRef.current
    if (!analyser || !playing) return null
    const data = dataRef.current
    analyser.getFloatTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i += 1) sum += data[i] * data[i]
    const level = Math.min(1, Math.sqrt(sum / data.length) * 4)
    const ms = (ctxRef.current.currentTime - playing.startedAt) * 1000
    const cue = playing.visemes.find((c) => ms >= c.start_ms && ms < c.end_ms)
    return { level, viseme: cue?.viseme ?? null, hasCues: playing.visemes.length > 0 }
  }, [])

  // Bagian teks yang sudah terucap (subtitle); null bila tidak sedang bicara.
  // Tanpa waktu per huruf, teks dimunculkan sebanding dengan durasi audio.
  const getCaption = useCallback(() => {
    const playing = playingRef.current
    if (!playing?.text) return null
    const ms = (ctxRef.current.currentTime - playing.startedAt) * 1000
    const { charEndMs, text } = playing
    let count = 0
    if (charEndMs.length) while (count < charEndMs.length && charEndMs[count] <= ms) count += 1
    else count = Math.round((text.length * ms) / playing.durationMs)
    return text.slice(0, count)
  }, [])

  useEffect(() => () => {
    sourceRef.current?.stop()
    ctxRef.current?.close()
  }, [])

  return { speak, stop, unlock, getSpeech, getCaption, isSpeaking, needsUnlock }
}
