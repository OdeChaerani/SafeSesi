// Tombol pil + kartu dropdown di atas panggung simulasi (Info Klien, Kamera, Transkrip).
// keepMounted: isi tetap terpasang saat ditutup (hanya disembunyikan), mis. agar kamera tidak dimatikan.
export default function ToolbarDropdown({ icon, label, title, open, onToggle, align = 'left', width = 'w-[280px]', indicator, keepMounted = false, children }) {
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl shadow-lg border text-xs font-bold transition-all cursor-pointer ${
          open ? 'bg-[#f5b51b] text-[#352f55] border-[#f5b51b]' : 'bg-white text-[#352f55] border-slate-100 hover:bg-slate-50'
        }`}
      >
        <span className={`material-symbols-outlined text-[17px] ${open ? 'text-[#352f55]' : 'text-[#f5b51b]'}`}>{icon}</span>
        <span>{label}</span>
        {indicator}
        <span className={`material-symbols-outlined text-[16px] ${open ? 'text-[#352f55]/70' : 'text-slate-400'}`}>
          {open ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {(open || keepMounted) && (
        <div
          hidden={!open}
          className={`absolute top-11 ${align === 'right' ? 'right-0' : 'left-0'} ${width} max-w-[calc(100vw-2rem)] bg-white rounded-2xl p-3.5 shadow-2xl border border-slate-100 z-40 text-[#1e1a34] ss-fade-up`}
        >
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[#f5b51b] text-base">{icon}</span>
              <span className="text-xs font-bold">{title || label}</span>
            </div>
            <button
              type="button"
              onClick={onToggle}
              className="w-6 h-6 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 flex items-center justify-center cursor-pointer transition"
              aria-label={`Tutup ${label}`}
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
          {children}
        </div>
      )}
    </div>
  )
}
