export default function SessionModeSelector({
  selectedMode = 'new',
  onSelectMode,
  lastSessionInfo = {
    attemptNo: 2,
    timestamp: '08:12',
    relativeTime: '2 hari lalu',
  },
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 p-1.5 bg-white/10 rounded-2xl border border-white/15 w-fit">
      {/* Tombol Sesi Baru */}
      <button
        type="button"
        onClick={() => onSelectMode('new')}
        className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all cursor-pointer ${
          selectedMode === 'new'
            ? 'bg-white text-[#1e1a34] shadow-md font-bold'
            : 'text-white/80 hover:text-white hover:bg-white/10'
        }`}
      >
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
            selectedMode === 'new'
              ? 'bg-[#f5b51b] text-[#1e1a34]'
              : 'bg-white/10 text-white'
          }`}
        >
          <span className="material-symbols-outlined text-[18px]">
            play_arrow
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-bold leading-tight">Sesi Baru</span>
          <span
            className={`text-[11px] leading-tight ${
              selectedMode === 'new' ? 'text-slate-500' : 'text-white/60'
            }`}
          >
            Mulai simulasi dari awal skenario
          </span>
        </div>
      </button>

      {/* Tombol Sesi Lanjutan */}
      <button
        type="button"
        onClick={() => onSelectMode('continue')}
        className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-all cursor-pointer ${
          selectedMode === 'continue'
            ? 'bg-white text-[#1e1a34] shadow-md font-bold'
            : 'text-white/80 hover:text-white hover:bg-white/10'
        }`}
      >
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
            selectedMode === 'continue'
              ? 'bg-[#f5b51b] text-[#1e1a34]'
              : 'bg-white/10 text-white'
          }`}
        >
          <span className="material-symbols-outlined text-[18px]">
            history
          </span>
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold leading-tight">
              Sesi Lanjutan
            </span>
            {selectedMode === 'continue' && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#ede9fe] text-[#352f55]">
                Aktif
              </span>
            )}
          </div>
          <span
            className={`text-[11px] leading-tight ${
              selectedMode === 'continue' ? 'text-slate-500' : 'text-white/60'
            }`}
          >
            Percobaan ke-{lastSessionInfo.attemptNo || 2} · {lastSessionInfo.timestamp || '08:12'}
          </span>
        </div>
      </button>
    </div>
  )
}

