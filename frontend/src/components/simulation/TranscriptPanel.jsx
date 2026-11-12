import { useEffect, useRef } from 'react'

export default function TranscriptPanel({
  messages = [],
  width = 340,
  onClose,
  onStartResize,
}) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages])

  return (
    <aside
      className="relative h-full flex flex-col shadow-2xl z-20 border-l border-white/10 shrink-0 select-none transition-[width] duration-75 bg-[#221a35] text-white"
      style={{
        width: `${width}px`,
      }}
    >
      {/* Interactive Resize Handle on Left Border */}
      <div
        onMouseDown={onStartResize}
        title="Tahan dan geser ke kiri/kanan untuk mengatur lebar transkrip"
        className="absolute top-0 -left-1.5 bottom-0 w-3 cursor-col-resize z-30 flex items-center justify-center group hover:bg-[#f5b51b]/30 active:bg-[#f5b51b]/50 transition-colors"
      >
        <div className="w-0.5 h-8 rounded-full bg-white/20 group-hover:bg-[#f5b51b] transition-colors" />
      </div>

      {/* Panel Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-white/10 shadow-xs shrink-0 bg-[#1c152c]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="material-symbols-outlined text-[#f5b51b] text-lg font-bold">
            forum
          </span>
          <h3 className="text-xs md:text-sm font-bold text-white truncate">
            Transkrip Sesi
          </h3>
        </div>

        <div className="flex items-center gap-2">
          {/* Live Badge */}
          <div className="flex items-center gap-1.5 bg-emerald-500/20 border border-emerald-400/30 px-2 py-0.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[9px] text-emerald-300 tracking-wider uppercase font-bold">
              Live
            </span>
          </div>

          {/* Close Panel Button */}
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              title="Tutup Panel Transkrip"
              className="w-7 h-7 rounded-lg bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition cursor-pointer border border-white/10"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          )}
        </div>
      </div>

      {/* Dialogue Bubble Stream */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-3.5 flex flex-col gap-3 bg-[#221a35]"
      >
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center select-none my-auto">
            <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-3 text-[#f5b51b]">
              <span className="material-symbols-outlined text-2xl">forum</span>
            </div>
            <p className="text-xs font-bold text-white mb-1">
              Transkrip Masih Kosong
            </p>
            <p className="text-[11px] leading-relaxed text-[#d1cfe2]/60 max-w-[210px]">
              Sesi konseling baru saja dimulai. Sampaikan sapaan awal atau pertanyaan pembuka kepada klien di kolom input.
            </p>
          </div>
        ) : (
          messages.map((msg, index) => {
            const isCounselor = msg.sender === 'counselor'
            return (
              <div
                key={index}
                className={`flex flex-col w-full ${
                  isCounselor ? 'items-end' : 'items-start'
                }`}
              >
                {/* Sender & Timestamp */}
                <div className="flex items-center gap-1.5 mb-1 px-1">
                  <span
                    className={`text-[10px] font-bold ${
                      isCounselor ? 'text-white' : 'text-[#f5b51b]'
                    }`}
                  >
                    {msg.name}
                  </span>
                  <span className="text-[9px] text-[#d1cfe2]/60">{msg.time}</span>
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[88%] px-3.5 py-2.5 text-xs md:text-[13px] leading-relaxed rounded-2xl ${
                    isCounselor
                      ? 'text-white rounded-tr-xs bg-[#4a3b6f] border border-white/15 shadow-sm'
                      : 'bg-white text-[#1e1a34] rounded-tl-xs font-medium border border-slate-200/80 shadow-sm'
                  }`}
                >
                  <span>{msg.text}</span>
                  {msg.isTyping && (
                    <span className="inline-flex items-center">
                      {!msg.text && (
                        <span className="text-slate-400 italic text-[11px] mr-1">
                          Sedang mengetik
                        </span>
                      )}
                      <span
                        className="inline-block w-1.5 h-3.5 bg-[#352f55] rounded-xs animate-pulse align-middle ml-0.5"
                        aria-hidden="true"
                      />
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </aside>
  )
}