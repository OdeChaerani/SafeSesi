import ScenarioCard from './ScenarioCard'

const gridClass = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3'

export function ScenarioGridSkeleton() {
  return (
    <div role="status" className={gridClass}>
      <span className="sr-only">Memuat katalog skenario</span>
      {[0, 1, 2].map((key) => (
        <div key={key} className="h-56 bg-white rounded-xl p-4 border border-slate-100 flex flex-col gap-3">
          <span className="ss-skeleton block h-4 w-24 rounded-full" />
          <span className="ss-skeleton block h-4 w-3/4 rounded" />
          <span className="ss-skeleton block h-9 rounded" />
          <span className="ss-skeleton block h-8 w-2/3 rounded mt-auto" />
          <span className="ss-skeleton block h-9 rounded-lg" />
        </div>
      ))}
    </div>
  )
}

/** isStale: hasil lama sedang diperbarui; tetap tampil, hanya diredupkan. */
export default function ScenarioGrid({ scenarios, isStale, onStart }) {
  return (
    <ul aria-busy={isStale} className={`${gridClass} transition-opacity duration-200 ${isStale ? 'opacity-60' : ''}`}>
      {scenarios.map((scenario, index) => (
        <ScenarioCard key={scenario.id} scenario={scenario} index={index} onStart={onStart} />
      ))}
    </ul>
  )
}
