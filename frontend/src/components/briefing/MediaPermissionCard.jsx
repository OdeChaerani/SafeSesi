import { useEffect, useState } from 'react'

// Izin kamera & mikrofon diminta sebelum sesi dimulai, dengan penjelasan untuk apa.
// Kamera hanya untuk pratinjau dirimu; tidak ada perekaman, penyimpanan, atau analisis ekspresi.
const STATUS = {
  unknown: { dot: 'bg-slate-400', label: 'Belum diizinkan' },
  granted: { dot: 'bg-emerald-400 animate-pulse', label: 'Kamera & mikrofon siap' },
  denied: { dot: 'bg-rose-400', label: 'Izin ditolak' },
  unsupported: { dot: 'bg-rose-400', label: 'Tidak didukung browser' },
}

async function queryPermission(name) {
  try {
    return (await navigator.permissions.query({ name })).state
  } catch {
    return 'prompt' // Firefox/Safari belum mendukung query kamera/mikrofon
  }
}

export default function MediaPermissionCard() {
  const supported = Boolean(navigator.mediaDevices?.getUserMedia)
  const [status, setStatus] = useState(supported ? 'unknown' : 'unsupported')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!supported) return
    Promise.all([queryPermission('camera'), queryPermission('microphone')]).then((states) => {
      if (states.every((s) => s === 'granted')) setStatus('granted')
      else if (states.includes('denied')) setStatus('denied')
    })
  }, [supported])

  const request = async () => {
    setBusy(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true })
      stream.getTracks().forEach((t) => t.stop()) // hanya meminta izin; perangkat langsung dilepas
      setStatus('granted')
    } catch {
      setStatus('denied')
    } finally {
      setBusy(false)
    }
  }

  const s = STATUS[status]
  return (
    <div className="p-3.5 rounded-xl bg-white/10 border border-white/10 flex flex-col gap-2.5 text-[#d3daea] text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[17px] text-[#f5b51b]">headset_mic</span>
          <span className="font-bold text-white">Kamera &amp; mikrofon</span>
        </div>
        <div className="flex items-center gap-1.5 font-bold text-white text-[11px] shrink-0">
          <span className={`w-2 h-2 rounded-full ${s.dot}`} />
          <span>{s.label}</span>
        </div>
      </div>
      <ul className="flex flex-col gap-1 text-[11px] leading-relaxed">
        <li className="flex gap-1.5"><span className="material-symbols-outlined text-[14px] mt-px">mic</span>Mikrofon hanya merekam setelah kamu menekan tombol mikrofon, dan berhenti saat kamu menekannya lagi atau diam sejenak. Rekaman diubah menjadi teks lalu dihapus. Kamu juga bisa mengetik.</li>
        <li className="flex gap-1.5"><span className="material-symbols-outlined text-[14px] mt-px">videocam</span>Kamera hanya menampilkan pratinjau dirimu di pojok layar. Tidak direkam atau disimpan.</li>
        <li className="flex gap-1.5"><span className="material-symbols-outlined text-[14px] mt-px">headphones</span>Disarankan memakai earphone agar suara klien tidak ikut terekam.</li>
      </ul>
      {status === 'denied' && (
        <p className="text-[11px] text-rose-200" role="alert">
          Izin ditolak. Kamu tetap bisa berlatih dengan mengetik. Untuk memakai suara, izinkan kamera dan mikrofon lewat ikon gembok di bilah alamat browser, lalu muat ulang halaman.
        </p>
      )}
      {status === 'unsupported' && (
        <p className="text-[11px] text-rose-200" role="alert">Browser ini tidak mendukung kamera/mikrofon. Kamu tetap bisa berlatih dengan mengetik.</p>
      )}
      {status === 'unknown' && (
        <button
          type="button"
          onClick={request}
          disabled={busy}
          className="self-start inline-flex items-center gap-1.5 bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] font-bold text-xs px-3 py-1.5 rounded-lg active:scale-95 transition disabled:opacity-50 cursor-pointer"
        >
          <span className="material-symbols-outlined text-[16px]">verified_user</span>
          {busy ? 'Menunggu izin…' : 'Izinkan kamera & mikrofon'}
        </button>
      )}
    </div>
  )
}
