import { useEffect, useRef } from 'react'

// Isi dropdown Transkrip: percakapan konselor & klien, otomatis bergulir ke pesan terbaru.
export default function TranscriptPanel({ messages = [] }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center text-center py-6 px-4 select-text">
        <span className="material-symbols-outlined text-2xl text-[#f5b51b] mb-2">forum</span>
        <p className="text-xs font-bold mb-1">Transkrip masih kosong</p>
        <p className="text-[11px] leading-relaxed text-slate-500">
          Sampaikan sapaan atau pertanyaan pembuka lewat suara atau kolom teks.
        </p>
      </div>
    )
  }

  return (
    // select-text: halaman simulasi memakai select-none, tapi teks transkrip harus bisa diblok & disalin.
    <div ref={containerRef} className="max-h-[min(60vh,30rem)] overflow-y-auto flex flex-col gap-3 pr-1 select-text">
      {messages.map((msg, index) => {
        const isCounselor = msg.sender === 'counselor'
        return (
          <div key={index} className={`flex flex-col w-full ${isCounselor ? 'items-end' : 'items-start'}`}>
            <div className="flex items-center gap-1.5 mb-1 px-1">
              <span className={`text-[10px] font-bold ${isCounselor ? 'text-[#352f55]' : 'text-amber-700'}`}>{msg.name}</span>
              <span className="text-[9px] text-slate-400">
                {msg.time}
                {msg.isTyped && ' · diketik'}
              </span>
            </div>
            <div
              className={`max-w-[88%] px-3.5 py-2.5 text-xs md:text-[13px] leading-relaxed rounded-2xl border ${
                isCounselor
                  ? 'bg-[#352f55] border-[#352f55] text-white rounded-tr-xs'
                  : 'bg-slate-50 border-slate-200 rounded-tl-xs'
              }`}
            >
              <span>{msg.text}</span>
              {msg.isTyping && (
                <span className="inline-flex items-center">
                  {!msg.text && <span className="text-slate-400 italic text-[11px] mr-1">Sedang menjawab</span>}
                  <span className="inline-block w-1.5 h-3.5 bg-[#f5b51b] rounded-xs animate-pulse align-middle ml-0.5" aria-hidden="true" />
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
