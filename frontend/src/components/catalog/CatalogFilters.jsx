const controlClass =
  'h-9 bg-slate-50 text-[#1e1a34] text-xs rounded-lg border border-slate-300 outline-none transition focus:bg-white focus:border-[#352f55] focus:ring-2 focus:ring-[#352f55]/40'

const STATUS_OPTIONS = [
  { value: 'all', label: 'Semua status', count: 'total' },
  { value: 'unattempted', label: 'Belum dicoba', count: 'unattempted_count' },
  { value: 'attempted', label: 'Pernah dicoba', count: 'attempted_count' },
]

/** counts = respons katalog terakhir (undefined sebelum data pertama datang; angka tidak ditampilkan). */
export default function CatalogFilters({ search, onSearch, status, onStatus, counts, shown, isPending }) {
  return (
    <div role="search" className="flex flex-col sm:flex-row sm:items-center gap-2 bg-white p-3 rounded-xl border border-slate-100 shadow-xs">
      <div className="relative flex-1 sm:max-w-md">
        <label htmlFor="cari-skenario" className="sr-only">Cari skenario</label>
        <span className="material-symbols-outlined absolute left-2.5 top-2 text-[18px] text-slate-500" aria-hidden="true">search</span>
        <input
          id="cari-skenario"
          type="search"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          maxLength={100}
          placeholder="Cari judul, nama klien, atau kata kunci"
          className={`${controlClass} w-full pl-9 pr-9`}
        />
        {isPending && <span className="ss-spinner absolute right-3 top-2.5 text-[#352f55]" aria-hidden="true" />}
      </div>

      <label htmlFor="saring-status" className="sr-only">Saring menurut status</label>
      <select id="saring-status" value={status} onChange={(e) => onStatus(e.target.value)} className={`${controlClass} px-2.5 cursor-pointer`}>
        {STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
            {counts ? ` (${counts[option.count]})` : ''}
          </option>
        ))}
      </select>

      {/* Wadah selalu ada agar perubahan jumlah dibacakan pembaca layar. */}
      <p aria-live="polite" className="sm:ml-auto min-h-4 text-[11px] text-slate-600">
        {counts && !isPending ? `Menampilkan ${shown} dari ${counts.total} skenario` : ''}
      </p>
    </div>
  )
}
