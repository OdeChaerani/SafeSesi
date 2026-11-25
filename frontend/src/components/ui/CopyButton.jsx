import { useEffect, useRef, useState } from 'react'

const COPIED_MS = 2000

/** Tombol ikon salin; berubah jadi centang sebentar setelah berhasil. */
export default function CopyButton({ value, label, onError }) {
  const [isCopied, setIsCopied] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => () => clearTimeout(timerRef.current), [])

  const copy = async () => {
    clearTimeout(timerRef.current)
    try {
      await navigator.clipboard.writeText(value)
      setIsCopied(true)
      timerRef.current = setTimeout(() => setIsCopied(false), COPIED_MS)
    } catch {
      onError?.(`${label} gagal disalin. Salin teksnya secara manual.`)
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={copy}
        aria-label={`Salin ${label}`}
        title={isCopied ? 'Tersalin' : `Salin ${label}`}
        className={`w-10 h-10 -my-2 shrink-0 rounded-lg inline-flex items-center justify-center hover:bg-slate-100 active:scale-95 focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer transition ${
          isCopied ? 'text-emerald-700' : 'text-slate-600'
        }`}
      >
        <span key={String(isCopied)} className="material-symbols-outlined ss-fade-in text-[16px]" aria-hidden="true">
          {isCopied ? 'check' : 'content_copy'}
        </span>
      </button>
      <span aria-live="polite" className="sr-only">
        {isCopied ? `${label} tersalin` : ''}
      </span>
    </>
  )
}
