export default function AudioCheckBar() {
  return (
    <div className="p-3.5 rounded-xl bg-white/10 border border-white/10 flex items-center justify-between text-[#d3daea] text-xs">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[17px] text-[#f5b51b]">
          headset_mic
        </span>
        <span className="text-[11px] md:text-xs">
          Disarankan memakai earphone untuk kejernihan audio
        </span>
      </div>

      <div className="flex items-center gap-1.5 font-bold text-white text-[11px] shrink-0">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>Mikrofon Aktif</span>
      </div>
    </div>
  )
}

