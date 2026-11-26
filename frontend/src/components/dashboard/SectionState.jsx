import Button from '../ui/Button'

/** Keadaan galat di dalam kartu, dengan tombol coba lagi. */
export function ErrorState({ message, onRetry }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white rounded-2xl border border-rose-200">
      <p className="text-xs text-rose-700">{message}</p>
      <Button variant="outline" size="sm" icon="refresh" onClick={onRetry} className="min-h-10">
        Coba lagi
      </Button>
    </div>
  )
}

/** Keadaan kosong yang jujur, dengan satu aksi lanjutan opsional. */
export function EmptyState({ icon, title, children, action }) {
  return (
    <div className="ss-fade-in flex flex-col items-center text-center gap-2 p-8 bg-white rounded-2xl border border-slate-100">
      <span className="w-12 h-12 rounded-2xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
        <span className="material-symbols-outlined text-[26px]" aria-hidden="true">{icon}</span>
      </span>
      <p className="text-sm font-bold text-[#1e1a34]">{title}</p>
      {children && <p className="text-xs text-slate-600 max-w-md">{children}</p>}
      {action}
    </div>
  )
}
