import Avatar from '../ui/Avatar'
import Badge from '../ui/Badge'

/** Hanya ringkasan publik skenario: identitas dasar, ringkasan awal, dan target perubahan (BRD "Sesi pertama"). */
export default function ClientProfileCard({ scenario }) {
  const facts = [
    ['cake', scenario.client_age && `${scenario.client_age} tahun`],
    ['person', scenario.client_gender],
    ['work', scenario.client_role],
  ].filter(([, text]) => text)

  return (
    <section aria-labelledby="profil-klien" className="ss-fade-up bg-white rounded-xl p-4 shadow-xs border border-slate-100 flex flex-col gap-3">
      <div className="flex items-center gap-3 pb-3 border-b border-slate-100">
        <Avatar name={scenario.client_name} className="w-10 h-10 text-sm" />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-slate-600">Klien virtual</p>
          <h2 id="profil-klien" className="text-sm md:text-base font-bold text-[#1e1a34] break-words">{scenario.client_name}</h2>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {facts.map(([icon, text]) => (
              <Badge key={icon} icon={icon} className="!text-slate-700">{text}</Badge>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-xs font-bold text-[#1e1a34] mb-1">Ringkasan pengantar</h3>
        <p className="text-xs text-slate-700 leading-relaxed">
          {scenario.initial_summary || 'Skenario ini belum memiliki ringkasan pengantar.'}
        </p>
      </div>

      {scenario.change_target && (
        <div className="flex items-start gap-2.5 p-3 rounded-lg bg-[#f0f3ff] border border-[#d7cefe]">
          <span className="material-symbols-outlined text-[18px] text-[#352f55] shrink-0" aria-hidden="true">explore</span>
          <div>
            <h3 className="text-xs font-bold text-[#1e1a34]">Target perubahan</h3>
            <p className="text-xs text-slate-700 leading-relaxed mt-0.5">{scenario.change_target}</p>
            {/* BRD: konteks perubahan bukan tujuan yang sudah disepakati. */}
            <p className="text-[11px] text-slate-600 mt-1">Belum menjadi tujuan yang disepakati klien.</p>
          </div>
        </div>
      )}
    </section>
  )
}
