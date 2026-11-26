import { lazy, Suspense, useState } from 'react'
import AvatarErrorBoundary from './AvatarErrorBoundary'
import CameraPreview from './CameraPreview'
import ToolbarDropdown from './ToolbarDropdown'
import TranscriptPanel from './TranscriptPanel'
import VoiceInput from './VoiceInput'
import { avatarUrl } from './avatarModels'
import roomImage from '../../assets/background.png'
import tableImage from '../../assets/table.png' // lapisan transparan seukuran latar: meja & vas di depan klien

// Three.js cukup besar; dimuat terpisah hanya di halaman simulasi.
const ClientAvatar = lazy(() => import('./ClientAvatar'))

export default function VirtualClientStage({
  client,
  onSendMessage,
  isProcessing = false,
  messages = [],
  sessionId,
  getElapsedMs = () => 0,
  voice,
  expression = 'neutral',
}) {
  const [isBioOpen, setIsBioOpen] = useState(false)
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(true)
  const [isCamPreviewOpen, setIsCamPreviewOpen] = useState(true)
  const [isCamActive, setIsCamActive] = useState(true)

  const [inputText, setInputText] = useState('')
  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = inputText.trim()
    if (!text || isProcessing) return
    voice?.unlock() // klik kirim = interaksi pengguna, audio klien boleh diputar setelahnya
    setInputText('')
    if (!(await onSendMessage(text))) setInputText(text) // gagal terkirim: ketikan dikembalikan
  }

  return (
    <div
      className="flex-1 flex flex-col items-center justify-between p-4 md:p-6 relative overflow-hidden select-none"
      // Latar dan meja dipotong dengan cara yang sama (cover, rata bawah) agar posisinya tetap sejajar.
      style={{ background: `url(${roomImage}) center bottom / cover no-repeat, #f4efe7` }}
    >

      {/* Kiri atas: Info Klien & Kamera; kanan atas: Transkrip (semua berupa dropdown) */}
      <div className="absolute top-4 left-4 z-30 flex items-center gap-2">
        <ToolbarDropdown
          icon="badge"
          label="Info Klien"
          title="Profil Klien"
          open={isBioOpen}
          onToggle={() => setIsBioOpen((prev) => !prev)}
        >
          <div className="flex flex-col gap-1.5 text-[11px]">
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-500 font-medium shrink-0">Nama:</span>
              <span className="font-bold text-[#1e1a34] truncate text-right">
                {client.name}
              </span>
            </div>
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-500 font-medium shrink-0">Usia &amp; Gender:</span>
              <span className="font-semibold text-slate-700 truncate text-right">
                {client.age} th · {client.gender}
              </span>
            </div>
            <div className="flex justify-between items-center gap-2">
              <span className="text-slate-500 font-medium shrink-0">Pekerjaan:</span>
              <span className="font-semibold text-slate-700 truncate text-right" title={client.role}>
                {client.role}
              </span>
            </div>
            {client.problem && (
              <div className="mt-1 p-2 rounded-lg text-[10px] leading-relaxed text-slate-600 bg-slate-50 border border-slate-200/80 max-h-28 overflow-y-auto">
                {client.problem}
              </div>
            )}
          </div>
        </ToolbarDropdown>

        <div className="hidden md:block">
          <ToolbarDropdown
            icon={isCamActive ? 'videocam' : 'videocam_off'}
            label="Kamera Anda"
            open={isCamPreviewOpen}
            onToggle={() => setIsCamPreviewOpen((prev) => !prev)}
            width="w-52"
            keepMounted // kamera tetap menyala saat dropdown ditutup (untuk pengamatan ekspresi nanti)
            indicator={<span className={`w-1.5 h-1.5 rounded-full ${isCamActive ? 'bg-emerald-500' : 'bg-slate-300'}`} />}
          >
          {/* Video Preview Box: hanya pratinjau, tidak direkam */}
          <div className="w-full h-28 rounded-lg bg-slate-100 flex items-center justify-center relative overflow-hidden mb-2">
            {isCamActive ? (
              <CameraPreview />
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
            <span className="material-symbols-outlined text-xs text-[#f5b51b]">
              {isCamActive ? 'videocam' : 'videocam_off'}
            </span>
            <span>{isCamActive ? 'Kamera Aktif' : 'Kamera Mati'}</span>
          </button>
          </ToolbarDropdown>
        </div>
      </div>

      <div className="absolute top-4 right-4 z-30">
        <ToolbarDropdown
          icon="forum"
          label="Transkrip"
          title="Transkrip Sesi"
          open={isTranscriptOpen}
          onToggle={() => setIsTranscriptOpen((prev) => !prev)}
          align="right"
          width="w-[360px]"
        >
          <TranscriptPanel messages={messages} />
        </ToolbarDropdown>
      </div>

      {/* Klien duduk di seberang meja: latar (seluruh halaman) -> avatar -> gambar meja di depan */}
      <div className="absolute inset-0 z-10">
        <AvatarErrorBoundary key={avatarUrl(client.avatarFile, client.gender)}>
        <Suspense
          fallback={
            <div className="w-full h-full flex items-center justify-center text-slate-500 text-xs" role="status">
              Memuat klien…
            </div>
          }
        >
          <ClientAvatar url={avatarUrl(client.avatarFile, client.gender)} getSpeech={voice?.getSpeech} expression={expression} />
        </Suspense>
        </AvatarErrorBoundary>
      </div>
      <img
        src={tableImage}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-cover object-bottom z-[15] pointer-events-none origin-top scale-[1.08]"
      />
      {voice?.needsUnlock && (
        <button
          type="button"
          onClick={() => voice.unlock()}
          className="absolute bottom-28 left-1/2 -translate-x-1/2 z-30 flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#f5b51b] text-[#352f55] text-xs font-bold shadow-xl hover:bg-[#ffd05b] active:scale-95 transition cursor-pointer"
        >
          <span className="material-symbols-outlined text-[18px]">volume_up</span>
          Putar suara klien
        </button>
      )}
      <div className="flex-1" />

      {/* Input konselor: suara (satu rekaman = satu giliran) atau teks */}
      <div className="relative w-full max-w-xl z-20 pb-3 px-4">
        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 bg-white border border-slate-100 rounded-2xl p-1.5 shadow-2xl"
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isProcessing}
            placeholder="Ketik respons atau tekan mikrofon…"
            className="flex-1 min-w-0 bg-slate-50 border border-slate-200/80 rounded-xl px-3.5 py-2 text-xs md:text-sm text-[#1e1a34] placeholder-slate-400 focus:outline-none focus:border-[#f5b51b] focus:bg-white transition"
          />
          <VoiceInput
            sessionId={sessionId}
            getElapsedMs={getElapsedMs}
            onSend={onSendMessage}
            onPress={() => voice?.unlock()}
            disabled={isProcessing}
          />
          <button
            type="submit"
            disabled={!inputText.trim() || isProcessing}
            aria-label="Kirim respons teks"
            className="px-3.5 h-11 rounded-xl bg-[#f5b51b] hover:bg-[#ffd05b] disabled:opacity-50 disabled:cursor-not-allowed text-[#352f55] font-bold text-xs flex items-center gap-1 transition shadow-sm cursor-pointer shrink-0"
          >
            <span className="material-symbols-outlined text-base">send</span>
          </button>
        </form>
      </div>
    </div>
  )
}
