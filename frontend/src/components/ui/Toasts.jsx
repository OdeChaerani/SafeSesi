import { useCallback, useEffect, useState } from 'react'

const EXIT_MS = 180
const SUCCESS_MS = 5000

function Toast({ toast, onDismiss }) {
  const [isLeaving, setIsLeaving] = useState(false)
  const isError = toast.type === 'error'

  const leave = useCallback(() => {
    setIsLeaving(true)
    setTimeout(() => onDismiss(toast.id), EXIT_MS)
  }, [onDismiss, toast.id])

  // Pesan galat tidak hilang sendiri agar sempat dibaca.
  useEffect(() => {
    if (isError) return undefined
    const timer = setTimeout(leave, SUCCESS_MS)
    return () => clearTimeout(timer)
  }, [isError, leave])

  return (
    <div
      role={isError ? 'alert' : undefined}
      className={`pointer-events-auto flex items-center gap-2 pl-3.5 pr-1 py-1 rounded-xl border bg-white shadow-lg text-xs md:text-sm ${
        isLeaving ? 'ss-toast-out' : 'ss-toast-in'
      } ${isError ? 'border-rose-200 text-rose-800' : 'border-emerald-200 text-emerald-800'}`}
    >
      <span className="material-symbols-outlined text-[18px]" aria-hidden="true">
        {isError ? 'error' : 'check_circle'}
      </span>
      <span className="flex-1">{toast.message}</span>
      <button
        type="button"
        onClick={leave}
        aria-label="Tutup notifikasi"
        className="w-10 h-10 shrink-0 rounded-lg flex items-center justify-center text-slate-600 hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer transition"
      >
        <span className="material-symbols-outlined text-[18px]" aria-hidden="true">close</span>
      </button>
    </div>
  )
}

/** Wadah toast selalu ada di DOM agar perubahan isinya dibacakan pembaca layar. */
export default function Toasts({ toasts, onDismiss }) {
  return (
    <div
      aria-live="polite"
      className="fixed z-[60] bottom-4 right-4 left-4 sm:left-auto sm:w-96 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}
