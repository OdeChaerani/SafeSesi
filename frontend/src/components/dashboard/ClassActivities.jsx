import { useCallback } from 'react'
import { useRequest } from '../../hooks/useRequest'
import { getClassScenarios } from '../../services/classes'
import { EmptyState, ErrorState } from './SectionState'

const gridClass = 'grid grid-cols-1 md:grid-cols-2 gap-4'

function CardSkeleton() {
  return (
    <div role="status" className="h-48 bg-white p-4 md:p-5 rounded-xl border border-slate-100 space-y-3">
      <span className="sr-only">Memuat kegiatan kelas</span>
      <span className="ss-skeleton block h-4 w-24 rounded-full" />
      <span className="ss-skeleton block h-4 w-3/4 rounded" />
      <span className="ss-skeleton block h-12 rounded-lg" />
    </div>
  )
}

/**
 * Kartu skenario satu kelas, diletakkan di grid bersama. Tiap kelas dimuat sendiri (paralel),
 * sehingga kegagalan satu kelas tidak menghilangkan kegiatan kelas lain.
 */
function ClassCards({ klass, onOpenBriefing }) {
  const load = useCallback(() => getClassScenarios(klass.id), [klass.id])
  const { data, error, reload } = useRequest(load)
  const course = `${klass.name} · ${klass.lecturers.join(', ') || 'Dosen belum ditetapkan'}`

  if (data === undefined) {
    return error ? (
      <ErrorState message={`Kegiatan ${klass.name} belum bisa dimuat. ${error.message}`} onRetry={reload} />
    ) : (
      <CardSkeleton />
    )
  }

  return data.items.map((item, index) => (
    <div
      key={item.id}
      className="ss-fade-up bg-white p-4 md:p-5 rounded-xl shadow-xs border border-slate-100 flex flex-col justify-between hover:shadow-md hover:-translate-y-0.5 transition-all duration-200"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex flex-col">
        {/* Badge & status */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span className="bg-[#ede9fe] text-[#352f55] text-[11px] px-2 py-0.5 rounded-full font-semibold">Latihan Kelas</span>
          <div className="flex items-center gap-1 text-slate-500 text-[11px]">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
              {item.attempt_status === 'attempted' ? 'check_circle' : 'radio_button_unchecked'}
            </span>
            <span className="font-medium">{item.attempt_status === 'attempted' ? 'Sudah dicoba' : 'Belum dicoba'}</span>
          </div>
        </div>

        {/* Title & Course */}
        <h3 className="text-sm md:text-base text-[#1e1a34] mt-2 leading-snug font-bold">{item.title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{course}</p>

        {/* Virtual Client Info Box */}
        <div className="mt-3 bg-slate-50 border border-slate-200/70 p-2.5 rounded-lg flex items-center gap-3">
          <div className="w-9 h-9 rounded-full shrink-0 bg-[#ede9fe] flex items-center justify-center text-[#352f55]">
            <span className="material-symbols-outlined text-[20px]" aria-hidden="true">person</span>
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-xs text-[#1e1a34] font-semibold truncate">Klien Virtual: {item.client_name}</span>
            <span className="text-slate-500 text-[11px] mt-0.5 truncate">
              {[item.client_age && `${item.client_age} tahun`, item.client_role].filter(Boolean).join(' · ')}
            </span>
          </div>
        </div>
      </div>

      {/* Card Footer */}
      <div className="mt-4 pt-2.5 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] text-slate-500">
          {item.total_attempts > 0 ? `${item.total_attempts} percobaan` : 'Belum ada percobaan'}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onOpenBriefing(item, klass.id)}
            className="bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition shadow-xs cursor-pointer active:scale-95"
          >
            {/* Selalu lewat briefing; di sana ada pilihan melanjutkan sesi yang belum diakhiri. */}
            <span>{item.active_session_id ? 'Lanjutkan sesi' : 'Mulai latihan'}</span>
            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">play_arrow</span>
          </button>
        </div>
      </div>
    </div>
  ))
}

/** classes = hasil useRequest(getClasses). */
export default function ClassActivities({ classes, onOpenBriefing }) {
  const { data, error, reload } = classes
  return (
    <div className="flex flex-col gap-3">
      {/* Section Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#f5b51b] inline-block" />
          <h2 className="text-base md:text-lg text-white font-bold tracking-tight">Kegiatan kelas</h2>
        </div>
        {data?.length > 0 && (
          <span className="text-[11px] text-[#d3daea] font-medium bg-white/10 px-2.5 py-0.5 rounded-full">
            {data.length} Kelas aktif
          </span>
        )}
      </div>

      {data === undefined ? (
        error ? (
          <ErrorState message={`Daftar kelas belum bisa dimuat. ${error.message}`} onRetry={reload} />
        ) : (
          <div className={gridClass}>
            <CardSkeleton />
            <CardSkeleton />
          </div>
        )
      ) : data.length === 0 ? (
        <EmptyState icon="school" title="Kamu belum terdaftar di kelas">
          Kegiatan kelas muncul di sini setelah akunmu dihubungkan ke sebuah kelas.
        </EmptyState>
      ) : (
        <div className={`${gridClass} peer`}>
          {data.map((klass) => (
            <ClassCards key={klass.id} klass={klass} onOpenBriefing={onOpenBriefing} />
          ))}
        </div>
      )}
      {data?.length > 0 && (
        // Semua kelas selesai dimuat tetapi tidak satu pun punya skenario: grid kosong.
        <p className="hidden peer-empty:block text-xs text-[#d3daea]">Belum ada skenario yang ditetapkan untuk kelasmu.</p>
      )}
    </div>
  )
}
