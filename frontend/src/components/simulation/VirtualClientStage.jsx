import { useState } from 'react'

export default function VirtualClientStage({
  client = {},
  clientName: propClientName,
  clientStatus = 'Mendengarkan aktif',
  onSendMessage,
  isProcessing = false,
  isTranscriptOpen = true,
  onOpenTranscript,
}) {
  const [inputText, setInputText] = useState('')
  const [isBioOpen, setIsBioOpen] = useState(false)
  const [isCamPreviewOpen, setIsCamPreviewOpen] = useState(false)
  const [isMicActive, setIsMicActive] = useState(false)
  const [isCamActive, setIsCamActive] = useState(true)

  const effectiveClient = {
    name: client.name || propClientName || 'Nadia Putri',
    age: client.age || 19,
    gender: client.gender || 'Perempuan',
    role: client.role || 'Mahasiswa',
    maritalStatus: client.maritalStatus || client.marital_status || null,
    problem:
      client.problem ||
      client.main_problem ||
      'Kewalahan membagi waktu kuliah & organisasi, memicu kelelahan mental.',
  }
  const clientName = effectiveClient.name

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputText.trim() || isProcessing) return
    onSendMessage(inputText.trim())
    setInputText('')
  }

  return (
    <div
      className="flex-1 flex flex-col items-center justify-between p-4 md:p-6 relative overflow-hidden select-none"
      style={{
        background:
          'radial-gradient(circle at 50% 28%, #453b6a 0%, #352f55 55%, #2a2444 100%)',
      }}
    >
      {/* Ambient Studio Lighting Glow */}
      <div className="absolute w-[460px] h-[460px] rounded-full bg-gradient-to-tr from-[#65587c]/25 via-[#503a73]/25 to-[#f5b51b]/15 blur-3xl pointer-events-none -translate-y-6" />

      {/* Top-Left Controls: Info Klien & Kamera Anda (Tidak menghalangi chat bar di bawah) */}
      <div className="absolute top-4 left-4 z-30 flex items-center gap-2">
        {/* 1. Info Klien Pill & Dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsBioOpen((prev) => !prev)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl shadow-lg border text-xs font-bold transition-all cursor-pointer ${
              isBioOpen
                ? 'bg-[#f5b51b] text-[#352f55] border-[#f5b51b]'
                : 'bg-white text-[#352f55] border-slate-100 hover:bg-slate-50'
            }`}
            title={isBioOpen ? 'Tutup Info Klien' : 'Buka Info Klien'}
          >
            <span className="material-symbols-outlined text-[17px] text-[#f5b51b]">
              badge
            </span>
            <span>Info Klien</span>
            <span className="material-symbols-outlined text-[16px] text-slate-400">
              {isBioOpen ? 'expand_less' : 'expand_more'}
            </span>
          </button>

          {/* Floating Dropdown Card Info Klien */}
          {isBioOpen && (
            <div className="absolute top-11 left-0 w-[280px] bg-white rounded-2xl p-3.5 shadow-2xl border border-slate-100 z-40 text-[#1e1a34]">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[#f5b51b] text-base">
                    badge
                  </span>
                  <span className="text-xs font-bold text-[#1e1a34]">Profil Klien</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsBioOpen(false)}
                  className="w-6 h-6 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 flex items-center justify-center cursor-pointer transition"
                  title="Tutup Info Klien"
                >
                  <span className="material-symbols-outlined text-[16px]">close</span>
                </button>
              </div>

              <div className="flex flex-col gap-1.5 text-[11px]">
                <div className="flex justify-between items-center gap-2">
                  <span className="text-slate-500 font-medium shrink-0">Nama:</span>
                  <span className="font-bold text-[#1e1a34] truncate text-right">
                    {effectiveClient.name}
                  </span>
                </div>
                <div className="flex justify-between items-center gap-2">
                  <span className="text-slate-500 font-medium shrink-0">Usia &amp; Gender:</span>
                  <span className="font-semibold text-slate-700 truncate text-right">
                    {effectiveClient.age} th · {effectiveClient.gender}
                  </span>
                </div>
                <div className="flex justify-between items-center gap-2">
                  <span className="text-slate-500 font-medium shrink-0">Pekerjaan:</span>
                  <span className="font-semibold text-slate-700 truncate text-right" title={effectiveClient.role}>
                    {effectiveClient.role}
                  </span>
                </div>
                {effectiveClient.maritalStatus && (
                  <div className="flex justify-between items-center gap-2">
                    <span className="text-slate-500 font-medium shrink-0">Pernikahan:</span>
                    <span className="font-semibold text-slate-700 truncate text-right">
                      {effectiveClient.maritalStatus}
                    </span>
                  </div>
                )}
                {effectiveClient.problem && (
                  <div className="mt-1 p-2 rounded-lg text-[10px] leading-relaxed text-slate-600 bg-slate-50 border border-slate-200/80 max-h-28 overflow-y-auto">
                    {effectiveClient.problem}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 2. Kamera Anda (Self Preview) Toggle Button & Mini PIP */}
        <div className="relative hidden md:block">
          <button
            type="button"
            onClick={() => setIsCamPreviewOpen((prev) => !prev)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl shadow-lg border text-xs font-bold transition-all cursor-pointer ${
              isCamPreviewOpen
                ? 'bg-[#352f55] text-white border-[#352f55]'
                : 'bg-white text-[#352f55] border-slate-100 hover:bg-slate-50'
            }`}
            title={isCamPreviewOpen ? 'Sembunyikan Kamera Anda' : 'Tampilkan Kamera Anda'}
          >
            <span className="material-symbols-outlined text-[17px] text-emerald-500">
              {isCamActive ? 'videocam' : 'videocam_off'}
            </span>
            <span className="hidden sm:inline">Kamera Anda</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          </button>

          {/* Self-Camera PIP Window */}
          {isCamPreviewOpen && (
            <div className="absolute top-11 left-0 w-44 rounded-xl p-2.5 shadow-2xl bg-white border border-slate-100 z-40 text-[#1e1a34]">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1 bg-slate-100 px-1.5 py-0.5 rounded-full border border-slate-200/80">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  <span className="text-[9px] font-bold text-[#1e1a34] tracking-wider">
                    Anda
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsCamPreviewOpen(false)}
                  className="text-slate-400 hover:text-slate-600 cursor-pointer p-0.5"
                  title="Tutup Preview"
                >
                  <span className="material-symbols-outlined text-xs">close</span>
                </button>
              </div>

              {/* Video Preview Box */}
              <div className="w-full h-16 rounded-lg bg-[#241d3b] flex items-center justify-center relative overflow-hidden mb-2">
                {isCamActive ? (
                  <span className="material-symbols-outlined text-2xl text-[#cfc0e9]/50">
                    person
                  </span>
                ) : (
                  <span className="material-symbols-outlined text-lg text-slate-400">
                    videocam_off
                  </span>
                )}
              </div>

              {/* Camera Toggle Button */}
              <button
                type="button"
                onClick={() => setIsCamActive((prev) => !prev)}
                className="w-full bg-slate-100 hover:bg-slate-200 text-[#1e1a34] py-1 px-2 rounded-lg text-[10px] font-semibold flex items-center justify-center gap-1 transition-colors cursor-pointer border border-slate-200/60"
              >
                <span className="material-symbols-outlined text-xs text-[#352f55]">
                  {isCamActive ? 'videocam' : 'videocam_off'}
                </span>
                <span>{isCamActive ? 'Kamera Aktif' : 'Kamera Mati'}</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Floating Toggle Button for Transcript (muncul di kanan saat panel tertutup) */}
      {!isTranscriptOpen && onOpenTranscript && (
        <button
          type="button"
          onClick={onOpenTranscript}
          title="Buka Transkrip Sesi"
          className="absolute right-4 top-4 z-30 flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white text-[#352f55] shadow-xl hover:shadow-2xl border border-slate-100 text-xs font-bold transition-all cursor-pointer hover:bg-slate-50"
        >
          <span className="material-symbols-outlined text-[17px] text-[#f5b51b]">
            forum
          </span>
          <span>Transkrip</span>
        </button>
      )}

      {/* 3D Avatar Center Display */}
      <div className="flex-1 flex flex-col items-center justify-center w-full z-10 my-auto">
        <div className="relative flex flex-col items-center justify-center">
          {/* Pulsing Golden Glow behind Avatar */}
          <div
            className={`absolute -top-3 w-44 h-44 rounded-full blur-2xl pointer-events-none transition-all duration-500 ${
              clientStatus === 'Sedang berbicara...'
                ? 'bg-[#f5b51b]/30 scale-110 animate-pulse'
                : 'bg-[#f5b51b]/15 animate-pulse'
            }`}
          />

          {/* Avatar Container */}
          <div
            className={`p-4 rounded-full bg-[#27213f]/70 backdrop-blur-md border transition-all duration-500 mb-2.5 ${
              clientStatus === 'Sedang berbicara...'
                ? 'border-[#f5b51b]/50 shadow-[0_0_35px_rgba(245,181,27,0.35)]'
                : 'border-white/20 shadow-2xl'
            }`}
          >
            <svg
              className="w-36 h-36 md:w-40 md:h-40 text-[#cfc0e9] drop-shadow-[0_10px_20px_rgba(0,0,0,0.5)]"
              fill="currentColor"
              viewBox="0 0 200 200"
            >
              <path
                d="M100 28 C82 28 69 42 69 61 C69 77 78 88 88 94 C88 98 86 103 82 108 C64 116 46 130 42 154 L158 154 C154 130 136 116 118 108 C114 103 112 98 112 94 C122 88 131 77 131 61 C131 42 118 28 100 28 Z"
                fill="#3f2e54"
                opacity="0.95"
              />
              <ellipse cx="100" cy="58" fill="#d7cefe" opacity="0.4" rx="24" ry="29" />
              <path
                d="M52 148 C58 128 76 117 100 117 C124 117 142 128 148 148 Z"
                fill="#544570"
                opacity="0.75"
              />
              <circle cx="93" cy="58" fill="#ffffff" opacity="0.95" r="2.5" />
              <circle cx="107" cy="58" fill="#ffffff" opacity="0.95" r="2.5" />
              <path
                d="M96 71 Q100 74 104 71"
                fill="none"
                opacity="0.8"
                stroke="#ffffff"
                strokeLinecap="round"
                strokeWidth="1.5"
              />
            </svg>
          </div>
        </div>

        {/* Client Name & Live Status Badge (Crisp White Card) */}
        <div className="flex flex-col items-center mt-3">
          <div className="flex items-center gap-1.5">
            <h2 className="text-white text-base md:text-lg font-bold drop-shadow-sm">
              {clientName}
            </h2>
            <span className="text-[#cfc0e9] text-xs font-medium">· Klien Virtual</span>
          </div>

          <div className="flex items-center gap-2 mt-1.5 px-3 py-1 rounded-full bg-white shadow-md border border-slate-100">
            <div className="flex items-center gap-1 h-2.5 text-[#f5b51b]">
              <span
                className={`w-1 h-2 bg-[#f5b51b] rounded-full ${
                  clientStatus === 'Sedang berbicara...'
                    ? 'animate-bounce'
                    : clientStatus.includes('berpikir') || clientStatus.includes('proses')
                    ? 'animate-pulse'
                    : 'opacity-40'
                }`}
                style={{ animationDelay: '0.1s' }}
              />
              <span
                className={`w-1 h-3 bg-[#f5b51b] rounded-full ${
                  clientStatus === 'Sedang berbicara...'
                    ? 'animate-bounce'
                    : clientStatus.includes('berpikir') || clientStatus.includes('proses')
                    ? 'animate-pulse'
                    : 'opacity-40'
                }`}
                style={{ animationDelay: '0.25s' }}
              />
              <span
                className={`w-1 h-2 bg-[#f5b51b] rounded-full ${
                  clientStatus === 'Sedang berbicara...'
                    ? 'animate-bounce'
                    : clientStatus.includes('berpikir') || clientStatus.includes('proses')
                    ? 'animate-pulse'
                    : 'opacity-40'
                }`}
                style={{ animationDelay: '0.4s' }}
              />
            </div>
            <span className="text-xs text-[#1e1a34] font-semibold">
              {clientStatus}
            </span>
          </div>
        </div>
      </div>

      {/* Crisp White Input Teks Bar Card */}
      <div className="w-full max-w-xl z-20 pb-2 px-4">
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 bg-white border border-slate-100 rounded-2xl p-1.5 shadow-2xl"
        >
          {/* Counselor Text Input Field */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isProcessing}
            placeholder="Tuliskan respons refleksi atau pertanyaan konseling..."
            className="flex-1 bg-slate-50 border border-slate-200/80 rounded-xl px-3.5 py-2 text-xs md:text-sm text-[#1e1a34] placeholder-slate-400 focus:outline-none focus:border-[#f5b51b] focus:bg-white transition"
          />

          {/* Mic Toggle Button (Voice Option) */}
          <button
            type="button"
            onClick={() => setIsMicActive((prev) => !prev)}
            className={`w-9 h-9 rounded-xl flex items-center justify-center transition shrink-0 cursor-pointer border ${
              isMicActive
                ? 'bg-[#f5b51b] text-[#352f55] border-[#f5b51b] shadow-sm'
                : 'bg-slate-100 hover:bg-slate-200 text-slate-600 border-slate-200/80'
            }`}
            title={isMicActive ? 'Matikan Mikrofon' : 'Gunakan Input Suara'}
          >
            <span className="material-symbols-outlined text-lg">
              {isMicActive ? 'mic' : 'mic_none'}
            </span>
          </button>

          {/* Send Button */}
          <button
            type="submit"
            disabled={!inputText.trim() || isProcessing}
            className="px-3.5 h-9 rounded-xl bg-[#f5b51b] hover:bg-[#ffd05b] disabled:opacity-50 disabled:cursor-not-allowed text-[#352f55] font-bold text-xs flex items-center gap-1 transition shadow-sm cursor-pointer shrink-0"
          >
            <span className="material-symbols-outlined text-base">send</span>
          </button>
        </form>
      </div>
    </div>
  )
}
