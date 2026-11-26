import { formatDateTime, formatDuration } from '../../utils/format'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Collapse from '../ui/Collapse'

const MODES = [
  { value: 'new', label: 'Dari awal' },
  { value: 'continue', label: 'Lanjutkan' },
]

/** Pilihan dua tombol (radio asli, jadi bisa dipakai dengan panah keyboard). */
function ModeSwitch({ mode, onChange, canContinue }) {
  return (
    <fieldset className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-slate-100">
      <legend className="sr-only">Mode latihan</legend>
      {MODES.map(({ value, label }) => {
        const disabled = value === 'continue' && !canContinue
        return (
          <label
            key={value}
            className={`min-h-8 flex items-center justify-center rounded-md text-xs font-bold transition focus-within:ring-2 focus-within:ring-[#352f55] ${
              disabled ? 'text-slate-400 cursor-not-allowed' : 'cursor-pointer'
            } ${mode === value ? 'bg-white text-[#1e1a34] shadow-xs' : disabled ? '' : 'text-slate-600 hover:text-[#1e1a34]'}`}
          >
            <input
              type="radio"
              name="mode-sesi"
              value={value}
              checked={mode === value}
              disabled={disabled}
              onChange={() => onChange(value)}
              className="sr-only"
            />
            {label}
          </label>
        )
      })}
    </fieldset>
  )
}

function SessionList({ sessions, selectedId, onSelect }) {
  return (
    <fieldset>
      <legend className="text-xs font-semibold text-[#1e1a34] mb-1.5">Sesi yang dilanjutkan</legend>
      <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto p-0.5">
        {sessions.map((item, index) => (
          <label
            key={item.id}
            className={`flex items-start gap-2.5 px-2.5 py-2 rounded-lg border cursor-pointer transition focus-within:ring-2 focus-within:ring-[#352f55] ${
              selectedId === item.id ? 'border-[#352f55] bg-[#f0f3ff]' : 'border-slate-200 hover:bg-slate-50'
            }`}
          >
            <input
              type="radio"
              name="sesi-induk"
              checked={selectedId === item.id}
              onChange={() => onSelect(item.id)}
              className="mt-0.5 w-3.5 h-3.5 accent-[#352f55]"
            />
            <span className="flex-1 min-w-0">
              <span className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-[#1e1a34]">Sesi {item.number}</span>
                {index === 0 && <Badge>Terbaru</Badge>}
              </span>
              <span className="block text-[11px] text-slate-600">
                {formatDateTime(item.started_at)}
                {item.duration_seconds != null && ` · ${formatDuration(item.duration_seconds)}`}
              </span>
              {item.parentNumber && (
                <span className="block text-[11px] text-slate-600">Lanjutan dari Sesi {item.parentNumber}</span>
              )}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/**
 * Pilihan mode, sesi yang dilanjutkan, privasi, dan tombol mulai.
 * history = hasil useRequest riwayat pada konteks ini; completed = sesi selesai (terbaru dulu).
 */
export default function SessionActionCard({
  className,
  history,
  completed,
  mode,
  onModeChange,
  parentId,
  onParentChange,
  activeSessionId,
  onResume,
  onStart,
  isStarting,
}) {
  const hasCompleted = completed.length > 0

  let hint = mode === 'continue' ? 'Meneruskan dari akhir sesi yang dipilih.' : 'Dari kondisi awal skenario.'
  if (history.data === undefined) hint = history.error ? 'Riwayat sesi belum bisa dimuat.' : 'Memeriksa riwayat sesi...'
  else if (!hasCompleted) hint = 'Belum ada sesi selesai untuk dilanjutkan.'

  return (
    <section aria-labelledby="mulai-latihan" className="ss-fade-up bg-white rounded-xl p-4 shadow-xs border border-slate-100 flex flex-col gap-2.5">
      <h2 id="mulai-latihan" className="text-sm font-bold text-[#1e1a34]">Mulai latihan</h2>

      {activeSessionId && (
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 flex flex-col gap-2">
          <p className="text-xs text-amber-900">Ada sesi skenario ini yang belum diakhiri.</p>
          <Button variant="outline" size="sm" icon="play_circle" className="min-h-10" onClick={() => onResume(activeSessionId)}>
            Lanjutkan yang tadi
          </Button>
        </div>
      )}

      <ModeSwitch mode={mode} onChange={onModeChange} canContinue={hasCompleted} />
      <p className="text-[11px] text-slate-600">{hint}</p>

      {history.error && history.data === undefined && (
        <Button variant="ghost" size="sm" icon="refresh" className="min-h-10" onClick={history.reload}>
          Muat ulang riwayat
        </Button>
      )}

      <Collapse open={mode === 'continue' && hasCompleted}>
        <SessionList sessions={completed} selectedId={parentId} onSelect={onParentChange} />
      </Collapse>

      {/* Harus sama dengan aturan akses backend (api/deps.py). */}
      <p className="flex items-center gap-1.5 text-[11px] text-slate-700">
        <span className="material-symbols-outlined text-[16px] text-[#352f55] shrink-0" aria-hidden="true">
          {className ? 'visibility' : 'lock'}
        </span>
        {className ? 'Terlihat olehmu dan dosen kelas ini.' : 'Hanya kamu yang bisa melihat sesi ini.'}
      </p>

      <Button size="sm" iconRight="play_arrow" loading={isStarting} onClick={onStart} className="hidden lg:inline-flex w-full min-h-9">
        {isStarting ? 'Menyiapkan sesi...' : mode === 'continue' ? 'Lanjutkan sesi' : 'Mulai sesi'}
      </Button>
    </section>
  )
}
