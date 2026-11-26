// Sesi latihan: membuat, memuat, mengirim giliran, dan mengakhiri.
import { postJson, request } from './api'

/** POST /sessions. data = { scenario_id, mode, parent_session_id, class_id } */
export const createSession = (data) => postJson('/sessions', data)

/** GET /sessions: riwayat milik sendiri (terbaru dulu) beserta hitungan ringkasan. */
export function listSessions({ limit, type, scenarioId, status }) {
  const params = new URLSearchParams({ limit })
  if (type) params.set('type', type)
  if (scenarioId) params.set('scenario_id', scenarioId)
  if (status) params.set('status', status)
  return request(`/sessions?${params}`)
}

/** GET /sessions/{id}: ringkasan publik skenario dan transkrip. */
export const getSession = (sessionId) => request(`/sessions/${sessionId}`)

/** GET /sessions/{id}/briefing-topics: topik sesi induk yang sudah punya catatan. */
export const getBriefingTopics = (sessionId) => request(`/sessions/${sessionId}/briefing-topics`)

/** POST /sessions/{id}/turns. turn = { content, start_ms, end_ms, sent_ms, words? }; words hanya untuk suara. */
export const sendTurn = (sessionId, turn) => postJson(`/sessions/${sessionId}/turns`, turn)

/** POST /sessions/{id}/end. endedMs = posisi garis waktu saat sesi diakhiri. */
export const endSession = (sessionId, endedMs) => postJson(`/sessions/${sessionId}/end`, { ended_ms: endedMs })
