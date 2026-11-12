export default function CatalogFilters({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  totalCount = 0,
  unattemptedCount = 0,
  attemptedCount = 0,
  displayedCount = 0,
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 justify-between bg-white p-3 rounded-2xl border border-slate-200/80 shadow-xs">
      <div className="flex flex-wrap items-center gap-3 flex-1 min-w-0">
        {/* Input Pencarian */}
        <div className="relative flex-1 min-w-[240px] max-w-md">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-[18px]">
            search
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Cari judul skenario atau kata kunci..."
            className="w-full h-10 pl-9 pr-4 bg-slate-50 border border-slate-200 rounded-xl text-xs md:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:bg-white focus:border-[#352f55] transition-all"
          />
        </div>

        {/* Dropdown Status */}
        <div className="relative shrink-0">
          <select
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
            className="h-10 pl-3 pr-8 bg-slate-50 text-slate-900 text-xs md:text-sm font-medium rounded-xl border border-slate-200 focus:outline-none focus:bg-white focus:border-[#352f55] transition-all appearance-none cursor-pointer"
          >
            <option value="all">Semua Status ({totalCount})</option>
            <option value="unattempted">
              Belum Dicoba ({unattemptedCount})
            </option>
            <option value="attempted">
              Sudah Dicoba ({attemptedCount})
            </option>
          </select>
          <span className="material-symbols-outlined absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-[18px] pointer-events-none">
            expand_more
          </span>
        </div>
      </div>

      {/* Counter Skenario */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 text-slate-500 text-xs font-medium shrink-0">
        <span className="material-symbols-outlined text-[16px]">dataset</span>
        <span>
          Menampilkan {displayedCount} dari {totalCount} skenario
        </span>
      </div>
    </div>
  )
}

