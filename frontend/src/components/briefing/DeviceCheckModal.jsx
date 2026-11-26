import { useEffect, useRef, useState } from 'react'
import Button from '../ui/Button'

// Ambang "terdengar" sama dengan penolakan rekaman hening di usePushToTalk.
const HEARD_RMS = 0.015

const getStream = (constraints) =>
  navigator.mediaDevices?.getUserMedia(constraints) ?? Promise.reject(new Error('unsupported'))

/**
 * Cek perangkat sebelum masuk sesi: pratinjau wajah dan uji mikrofon. Tidak ada yang direkam atau disimpan.
 * Sesi tetap bisa dimulai tanpa izin (mahasiswa bisa mengetik). Perangkat dilepas saat modal ditutup.
 */
export default function DeviceCheckModal({ confirmLabel, isStarting, onConfirm, onClose }) {
  const [camera, setCamera] = useState('waiting') // waiting | ready | blocked
  const [mic, setMic] = useState('waiting') // waiting | ready | heard | blocked
  const dialogRef = useRef(null)
  const videoRef = useRef(null)
  const levelRef = useRef(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog.open) dialog.showModal()
    return () => dialog.close() // close() mengembalikan fokus ke tombol pemicu
  }, [])

  useEffect(() => {
    let isCancelled = false
    const streams = []
    let audioContext
    let frame = 0
    const keep = (stream) => {
      if (isCancelled) stream.getTracks().forEach((track) => track.stop())
      else streams.push(stream)
      return !isCancelled
    }

    // Diminta terpisah agar satu perangkat yang gagal tidak menggagalkan yang lain.
    getStream({ video: { width: 320, height: 240 } })
      .then((stream) => {
        if (!keep(stream)) return
        videoRef.current.srcObject = stream
        setCamera('ready')
      })
      .catch(() => !isCancelled && setCamera('blocked'))

    getStream({ audio: true })
      .then(async (stream) => {
        if (!keep(stream)) return
        audioContext = new AudioContext()
        await audioContext.resume().catch(() => {})
        if (isCancelled) return
        const analyser = audioContext.createAnalyser()
        analyser.fftSize = 1024
        audioContext.createMediaStreamSource(stream).connect(analyser)
        const samples = new Float32Array(analyser.fftSize)
        setMic('ready')
        const measure = () => {
          analyser.getFloatTimeDomainData(samples)
          const rms = Math.sqrt(samples.reduce((sum, v) => sum + v * v, 0) / samples.length)
          // Diubah langsung di DOM agar tidak render ulang setiap frame.
          if (levelRef.current) levelRef.current.style.transform = `scaleX(${Math.min(1, rms * 8)})`
          if (rms >= HEARD_RMS) setMic('heard')
          frame = requestAnimationFrame(measure)
        }
        measure()
      })
      .catch(() => !isCancelled && setMic('blocked'))

    return () => {
      isCancelled = true
      cancelAnimationFrame(frame)
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      audioContext?.close()
    }
  }, [])

  const requestClose = () => {
    if (!isStarting) onClose()
  }

  const micText = {
    waiting: 'Menunggu izin mikrofon...',
    ready: 'Coba ucapkan sesuatu',
    heard: 'Suaramu terdengar',
    blocked: 'Mikrofon tidak bisa dipakai. Kamu tetap bisa mengetik.',
  }[mic]

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="cek-perangkat"
      className="ss-modal ss-fade-up"
      onCancel={(e) => {
        e.preventDefault()
        requestClose()
      }}
      onClose={() => {
        if (!dialogRef.current?.open) requestClose() // ditutup paksa oleh browser
      }}
    >
      <div className="bg-white text-[#1e1a34] p-5 flex flex-col gap-4">
        <div>
          <h2 id="cek-perangkat" className="text-base font-bold">Cek kamera dan mikrofon</h2>
          <p className="text-xs text-slate-600">Tidak ada yang direkam atau disimpan di tahap ini.</p>
        </div>

        <div className="relative aspect-video rounded-xl bg-slate-900 overflow-hidden flex items-center justify-center">
          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            aria-label="Pratinjau kamera kamu"
            className={`w-full h-full object-cover -scale-x-100 ${camera === 'ready' ? '' : 'invisible'}`}
          />
          {camera !== 'ready' && (
            <p role="status" className="absolute px-4 text-center text-xs text-slate-200">
              {camera === 'waiting' ? 'Menunggu izin kamera...' : 'Kamera tidak bisa dipakai. Sesi tetap bisa dimulai.'}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <p aria-live="polite" className={`flex items-center gap-1.5 text-xs font-semibold ${mic === 'heard' ? 'text-emerald-700' : 'text-slate-700'}`}>
            <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
              {mic === 'heard' ? 'check_circle' : mic === 'blocked' ? 'mic_off' : 'mic'}
            </span>
            {micText}
          </p>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden" aria-hidden="true">
            <div ref={levelRef} className="h-full origin-left bg-emerald-500" style={{ transform: 'scaleX(0)' }} />
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" className="min-h-10" disabled={isStarting} onClick={requestClose}>
            Batal
          </Button>
          <Button iconRight="play_arrow" className="min-h-10" loading={isStarting} onClick={onConfirm}>
            {isStarting ? 'Menyiapkan...' : confirmLabel}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
