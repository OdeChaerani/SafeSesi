import ScenarioCard from './ScenarioCard'

export default function ScenarioGrid({ scenarios, onStartExercise, isLoading = false }) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-white rounded-2xl p-5 border border-slate-200/80 animate-pulse flex flex-col justify-between h-56"
          >
            <div className="flex flex-col gap-3">
              <div className="w-20 h-5 bg-slate-200 rounded-full" />
              <div className="w-3/4 h-5 bg-slate-200 rounded-md" />
              <div className="w-full h-10 bg-slate-100 rounded-md" />
            </div>
            <div className="flex items-center gap-3 pt-3 border-t border-slate-100">
              <div className="w-10 h-10 rounded-full bg-slate-200" />
              <div className="flex flex-col gap-1.5 flex-1">
                <div className="w-28 h-3.5 bg-slate-200 rounded-md" />
                <div className="w-20 h-3 bg-slate-100 rounded-md" />
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (!scenarios || scenarios.length === 0) {
    return (
      <div className="bg-white rounded-2xl p-8 border border-slate-200/80 text-center flex flex-col items-center justify-center gap-2 py-12">
        <div className="w-12 h-12 rounded-xl bg-slate-100 text-slate-400 flex items-center justify-center">
          <span className="material-symbols-outlined text-[28px]">search_off</span>
        </div>
        <h4 className="text-base font-bold text-[#1e1a34]">Tidak ada skenario ditemukan</h4>
        <p className="text-xs md:text-sm text-[#64748b] max-w-sm">
          Coba sesuaikan kata kunci pencarian atau ganti filter status untuk menemukan skenario yang sesuai.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {scenarios.map((scenario) => (
        <ScenarioCard
          key={scenario.id}
          scenario={scenario}
          onStartExercise={onStartExercise}
        />
      ))}
    </div>
  )
}

