import Avatar from '../ui/Avatar'
import Badge from '../ui/Badge'
import Button from '../ui/Button'

/** Lencana status: sesi yang belum diakhiri didahulukan; selain itu jumlah sesi selesai. */
function StatusBadge({ scenario }) {
  if (scenario.active_session_id) {
    return <Badge variant="warning" icon="play_circle">Sedang berjalan</Badge>
  }
  if (scenario.completed_attempts > 0) {
    return <Badge variant="success" icon="check_circle">Sudah dicoba · {scenario.completed_attempts} sesi selesai</Badge>
  }
  return <Badge icon="radio_button_unchecked">Belum dicoba</Badge>
}

export default function ScenarioCard({ scenario, index, onStart }) {
  const titleId = `skenario-${scenario.id}`
  const details = [scenario.client_age && `${scenario.client_age} tahun`, scenario.client_role].filter(Boolean).join(' · ')

  return (
    <li
      className="ss-fade-up ss-lift bg-white rounded-xl p-4 shadow-xs border border-slate-100 flex flex-col gap-3"
      style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
    >
      <div>
        <StatusBadge scenario={scenario} />
      </div>

      <div>
        <h2 id={titleId} className="text-sm font-bold text-[#1e1a34] leading-snug break-words">
          {scenario.title}
        </h2>
        {scenario.initial_summary && (
          <p className="text-xs text-slate-600 leading-relaxed line-clamp-2 mt-1">{scenario.initial_summary}</p>
        )}
      </div>

      <div className="mt-auto flex items-center gap-2.5 pt-3 border-t border-slate-100">
        <Avatar name={scenario.client_name} />
        <div className="min-w-0">
          <p className="text-xs font-semibold text-[#1e1a34] truncate">{scenario.client_name}</p>
          <p className="text-[11px] text-slate-600 truncate" title={details}>{details}</p>
        </div>
      </div>

      <Button size="sm" iconRight="play_arrow" className="w-full min-h-9" aria-describedby={titleId} onClick={() => onStart(scenario.id)}>
        Mulai latihan
      </Button>
    </li>
  )
}
