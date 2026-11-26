import CountUp from '../ui/CountUp'

/**
 * stats: [{ id, title, icon, iconFill?, subtitle, source, value, format?, unit?, barColor, progressPercent }]
 * source = hasil useRequest tempat angka itu berasal; tiap kartu memuat dan gagal sendiri-sendiri.
 */
export default function StatCards({ stats }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
      {stats.map((stat, index) => {
        const { data, error, reload } = stat.source
        const isReady = data !== undefined
        return (
          <div
            key={stat.id}
            className="ss-fade-up bg-white p-3.5 rounded-xl shadow-xs border border-slate-100 flex flex-col justify-between transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-500">{stat.title}</span>
              <div className="w-7 h-7 rounded-lg bg-[#ede9fe] flex items-center justify-center text-[#352f55]">
                <span
                  className="material-symbols-outlined text-[17px]"
                  aria-hidden="true"
                  style={stat.iconFill ? { fontVariationSettings: "'FILL' 1" } : undefined}
                >
                  {stat.icon}
                </span>
              </div>
            </div>

            {/* Value */}
            <div className="mt-2.5 flex flex-col">
              <div className="h-8 flex items-baseline gap-1.5">
                {isReady ? (
                  <>
                    <span className="text-2xl font-bold text-[#1e1a34] leading-tight">
                      <span aria-hidden="true">
                        <CountUp value={stat.value} format={stat.format} />
                      </span>
                      <span className="sr-only">{stat.format ? stat.format(stat.value) : stat.value}</span>
                    </span>
                    {stat.unit && <span className="text-xs text-slate-500 font-medium">{stat.unit}</span>}
                  </>
                ) : error ? (
                  <button
                    type="button"
                    onClick={reload}
                    title={error.message}
                    className="self-center min-h-8 text-xs font-semibold text-rose-700 underline cursor-pointer"
                  >
                    Gagal dimuat. Coba lagi
                  </button>
                ) : (
                  <span className="ss-skeleton self-center block h-6 w-14 rounded">
                    <span className="sr-only">Memuat {stat.title}</span>
                  </span>
                )}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 truncate">{stat.subtitle}</span>
            </div>

            {/* Progress Bar */}
            <div className="mt-2.5 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden" aria-hidden="true">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ backgroundColor: stat.barColor, width: `${isReady ? stat.progressPercent : 0}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
