import { formatDateTime, formatDuration } from '../../utils/format'
import { EmptyState, ErrorState } from './SectionState'

const BADGES = {
  amber: ['bg-amber-50 text-amber-800 border-amber-200/80', 'bg-[#f5b51b]'],
  purple: ['bg-purple-50 text-purple-900 border-purple-200/80', 'bg-[#352f55]'],
  red: ['bg-red-50 text-red-700 border-red-200/80', 'bg-red-600'],
}

// Lencana sesi selesai menurut status evaluasinya.
const EVALUATION = {
  none: { tone: 'purple', label: 'Selesai' },
  running: { tone: 'purple', label: 'Sedang dievaluasi' },
  completed: { tone: 'amber', label: 'Sudah Dievaluasi' },
  failed: { tone: 'red', label: 'Evaluasi gagal' },
}
const UNFINISHED = { tone: 'red', label: 'Belum selesai' }

function StatusBadge({ tone, label }) {
  const [badge, dot] = BADGES[tone]
  return (
    <span className={`border text-[11px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${badge}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  )
}

function HistoryRow({ item }) {
  const isCompleted = item.status === 'completed'
  const status = isCompleted ? EVALUATION[item.evaluation_status] : UNFINISHED

  return (
    <div className="px-4 py-3 hover:bg-slate-50 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3">
      {/* Item Info */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-full bg-[#ede9fe] flex items-center justify-center shrink-0 text-[#352f55]">
          <span className="material-symbols-outlined text-[18px]" aria-hidden="true">person</span>
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-xs md:text-sm font-bold text-[#1e1a34] truncate">{item.scenario_title}</span>
          <div className="flex items-center gap-1.5 text-slate-500 text-[11px] flex-wrap mt-0.5">
            <span className="flex items-center gap-1 font-medium">
              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">account_circle</span>
              {item.client_name}
            </span>
            <span>·</span>
            <span>{formatDateTime(item.started_at)}</span>
            {isCompleted && item.duration_seconds != null && (
              <>
                <span>·</span>
                <span>Durasi {formatDuration(item.duration_seconds)}</span>
              </>
            )}
            {item.kind === 'class' && (
              <>
                <span>·</span>
                <span>{item.class_name || 'Latihan kelas'}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Status & tombol detail */}
      <div className="flex items-center gap-2.5 shrink-0 justify-between md:justify-end">
        <StatusBadge tone={status.tone} label={status.label} />
        {/* Diaktifkan setelah halaman riwayat dibuat. */}
        <button
          type="button"
          disabled
          title="Halaman riwayat segera hadir"
          className="bg-slate-100 text-[#1e1a34] px-2.5 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 opacity-50 cursor-not-allowed"
        >
          <span className="material-symbols-outlined text-[16px] text-[#352f55]" aria-hidden="true">arrow_forward</span>
          <span>Detail</span>
        </button>
      </div>
    </div>
  )
}

/** sessions = hasil useRequest daftar sesi. */
export default function RecentHistory({ sessions, onStartFirst }) {
  const { data, error, reload } = sessions

  let content
  if (data === undefined) {
    content = error ? (
      <ErrorState message={`Riwayat belum bisa dimuat. ${error.message}`} onRetry={reload} />
    ) : (
      <div role="status" className="bg-white rounded-xl border border-slate-100 divide-y divide-slate-100">
        <span className="sr-only">Memuat riwayat</span>
        {[0, 1, 2].map((key) => (
          <div key={key} className="h-16 px-4 flex items-center gap-3">
            <span className="ss-skeleton w-8 h-8 rounded-full" />
            <span className="flex-1 space-y-2">
              <span className="ss-skeleton block h-3 w-1/2 rounded" />
              <span className="ss-skeleton block h-2.5 w-1/3 rounded" />
            </span>
          </div>
        ))}
      </div>
    )
  } else if (data.items.length === 0) {
    content = (
      <EmptyState
        icon="history"
        title="Belum ada sesi"
        action={
          <button
            type="button"
            onClick={onStartFirst}
            className="mt-1 bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] px-3 py-2 rounded-lg text-xs font-bold cursor-pointer transition active:scale-95"
          >
            Mulai latihan pertamamu
          </button>
        }
      >
        Sesi latihanmu akan tercatat di sini.
      </EmptyState>
    )
  } else {
    content = (
      <div className="ss-fade-in bg-white rounded-xl shadow-xs border border-slate-100 overflow-hidden">
        <div className="divide-y divide-slate-100 flex flex-col">
          {data.items.map((item) => (
            <HistoryRow key={item.id} item={item} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#ede9fe] inline-block" />
          <h2 className="text-base md:text-lg text-white font-bold tracking-tight">Riwayat terbaru</h2>
        </div>
        <button
          type="button"
          disabled
          title="Halaman riwayat segera hadir"
          className="text-xs text-[#d3daea]/70 flex items-center gap-1 font-medium cursor-not-allowed"
        >
          <span>Lihat semua (segera hadir)</span>
        </button>
      </div>
      {content}
    </div>
  )
}
