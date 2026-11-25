import Badge from '../ui/Badge'
import Button from '../ui/Button'

export default function ScenarioCard({ scenario, onStartExercise }) {
  const isAttempted = scenario.attempt_status === 'attempted'

  return (
    <div className="bg-white rounded-2xl p-5 shadow-xs border border-slate-200/80 flex flex-col justify-between hover:shadow-md hover:-translate-y-0.5 transition-all group">
      {/* 1. Header Kartu: Status Badge, Judul, & Ringkasan Masalah */}
      <div className="flex flex-col gap-2.5">
        <div className="flex items-center">
          {isAttempted ? (
            <Badge variant="attempted" icon="check_circle">
              Sudah Dicoba
            </Badge>
          ) : (
            <Badge variant="unattempted">
              Belum Dicoba
            </Badge>
          )}
        </div>

        <h3 className="text-sm md:text-base font-bold text-[#1e1a34] group-hover:text-[#352f55] transition-colors leading-snug line-clamp-1">
          {scenario.title}
        </h3>

        <p className="text-xs text-[#64748b] leading-relaxed line-clamp-2">
          {scenario.initial_summary || scenario.main_problem || scenario.change_target}
        </p>
      </div>

      {/* 2. Profil Klien & Tombol Aksi Reusable UI */}
      <div className="flex flex-col gap-3.5 mt-4">
        {/* Profil Klien (Placeholder Avatar) */}
        <div className="flex items-center gap-3 pt-3 border-t border-slate-100">
          <div className="w-10 h-10 rounded-full bg-[#352f55] text-white flex items-center justify-center shrink-0 shadow-xs">
            <span className="material-symbols-outlined text-[20px]">person</span>
          </div>
          <div className="flex flex-col min-w-0">
            <span className="font-semibold text-xs text-[#1e1a34] leading-tight truncate">
              {scenario.client_name}
            </span>
            <span className="text-[11px] text-[#64748b] mt-0.5 truncate">
              {scenario.client_age} tahun · {scenario.client_role || 'Klien Virtual'}
            </span>
          </div>
        </div>

        {/* Tombol Aksi Reusable Button */}
        {isAttempted ? (
          <div className="flex items-center gap-2 w-full">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 py-2.5"
              onClick={() =>
                onStartExercise &&
                onStartExercise({
                  ...scenario,
                  scenarioId: scenario.id,
                  mode: 'repeat',
                })
              }
            >
              Mulai Ulang
            </Button>
            <Button
              variant="primary"
              size="sm"
              iconRight="play_arrow"
              className="flex-1 py-2.5"
              onClick={() =>
                onStartExercise &&
                onStartExercise({
                  ...scenario,
                  scenarioId: scenario.id,
                  mode: 'continue',
                  parentSessionId: scenario.last_completed_session_id,
                })
              }
            >
              Lanjutkan
            </Button>
          </div>
        ) : (
          <Button
            variant="primary"
            size="sm"
            iconRight="play_arrow"
            className="w-full py-2.5"
            onClick={() =>
              onStartExercise &&
              onStartExercise({
                ...scenario,
                scenarioId: scenario.id,
                mode: 'new',
              })
            }
          >
            Mulai latihan
          </Button>
        )}
      </div>
    </div>
  )
}
