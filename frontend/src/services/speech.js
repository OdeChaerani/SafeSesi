// Suara: transkripsi ucapan konselor (Groq, lewat backend) dan audio ucapan klien (ElevenLabs, lewat backend).
// API key tidak pernah ada di frontend.
import { request } from './api'

/** Kirim rekaman (Blob webm). Hasil: { text, words: [{word, start_ms, end_ms}], duration_ms }.
 * preview = teks sementara selama masih merekam (dicatat terpisah di log backend). */
export const transcribeAudio = (sessionId, blob, { preview = false } = {}) =>
  request(`/sessions/${sessionId}/transcribe${preview ? '?preview=true' : ''}`, {
    method: 'POST',
    headers: { 'Content-Type': blob.type.split(';')[0] || 'audio/webm' },
    body: blob,
  })

/** Ucapan klien pada giliran turnNo: { audio: ArrayBuffer (MP3), visemes: [{viseme, start_ms, end_ms}], charEndMs: [ms per huruf] }. */
export async function getClientAudio(sessionId, turnNo) {
  const { audio_base64: b64, visemes, char_end_ms: charEndMs } = await request(`/sessions/${sessionId}/turns/${turnNo}/audio`)
  return { audio: Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)).buffer, visemes: visemes || [], charEndMs: charEndMs || [] }
}
