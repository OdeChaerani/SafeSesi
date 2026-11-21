import { useEffect, useRef, useState } from 'react'

// Pratinjau kamera mahasiswa. Tidak direkam, tidak disimpan, tidak dianalisis.
export default function CameraPreview() {
  const videoRef = useRef(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let stream
    let cancelled = false
    if (!navigator.mediaDevices?.getUserMedia) {
      Promise.resolve().then(() => setError('Browser ini tidak mendukung kamera.'))
      return undefined
    }
    navigator.mediaDevices
      .getUserMedia({ video: { width: 320, height: 240 }, audio: false })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop())
        stream = s
        if (videoRef.current) videoRef.current.srcObject = s
      })
      .catch(() => setError('Izin kamera ditolak. Kamu tetap bisa berlatih tanpa kamera.'))
    return () => {
      cancelled = true
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  if (error) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-1 text-center px-2" role="alert">
        <span className="material-symbols-outlined text-lg text-slate-400">videocam_off</span>
        <span className="text-[10px] text-slate-300 leading-snug">{error}</span>
      </div>
    )
  }
  return <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover -scale-x-100" aria-label="Pratinjau kamera kamu" />
}
