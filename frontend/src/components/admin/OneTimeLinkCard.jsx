import { useEffect, useRef, useState } from 'react'
import Button from '../ui/Button'

const COPIED_MS = 2000

/** Tautan aktivasi atau reset yang hanya tampil sekali (tidak bisa diambil lagi dari server). */
export default function OneTimeLinkCard({ link, onDismiss }) {
  const [copyState, setCopyState] = useState('idle')
  const cardRef = useRef(null)
  const inputRef = useRef(null)
  const timerRef = useRef(null)

  useEffect(() => {
    cardRef.current?.scrollIntoView({ block: 'nearest' })
    return () => clearTimeout(timerRef.current)
  }, [])

  const copy = async () => {
    clearTimeout(timerRef.current)
    try {
      await navigator.clipboard.writeText(link.url)
      setCopyState('copied')
      timerRef.current = setTimeout(() => setCopyState('idle'), COPIED_MS)
    } catch {
      // Clipboard tidak tersedia (mis. halaman tanpa HTTPS): pilih teksnya agar bisa disalin manual.
      inputRef.current?.select()
      setCopyState('failed')
    }
  }

  const isCopied = copyState === 'copied'

  return (
    <section
      ref={cardRef}
      aria-label={`${link.title} untuk ${link.name}`}
      className="ss-fade-up bg-amber-50 border-2 border-[#f5b51b] rounded-2xl shadow-lg p-4 md:p-5 flex flex-col gap-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm md:text-base font-bold text-[#1e1a34] break-words">
            {link.title} untuk {link.name}
          </h2>
          <p className="text-xs text-amber-900 mt-0.5">
            Tautan hanya ditampilkan sekali dan tidak akan ditampilkan lagi setelah kartu ini ditutup atau halaman
            dimuat ulang. Berlaku sampai {new Date(link.expiresAt).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' })}.
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label={`Tutup tautan untuk ${link.name}`}
          className="w-10 h-10 shrink-0 rounded-lg flex items-center justify-center text-slate-700 hover:bg-amber-100 focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer transition"
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">close</span>
        </button>
      </div>
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          ref={inputRef}
          type="text"
          readOnly
          value={link.url}
          aria-label={link.title}
          onFocus={(e) => e.target.select()}
          className="flex-1 min-w-0 h-10 px-3 bg-white text-xs text-slate-800 font-mono rounded-xl border border-amber-300 outline-none focus:ring-2 focus:ring-[#352f55]"
        />
        <Button icon={isCopied ? 'check' : 'content_copy'} onClick={copy} className="h-10 sm:w-36">
          {isCopied ? 'Tersalin' : 'Salin tautan'}
        </Button>
      </div>
      <p aria-live="polite" className="text-xs text-rose-700 empty:hidden">
        {copyState === 'failed' ? 'Gagal menyalin otomatis. Teks sudah dipilih, tekan Ctrl+C.' : ''}
      </p>
    </section>
  )
}
