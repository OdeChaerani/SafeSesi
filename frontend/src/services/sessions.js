// Sesi latihan: membuat, memuat, mengirim giliran, dan mengakhiri.
import { postJson, request } from './api'

/** POST /sessions. data = { scenario_id, mode, parent_session_id, class_id } */
export const createSession = (data) => postJson('/sessions', data)

/** GET /sessions?limit=n: riwayat milik sendiri (terbaru dulu) beserta hitungan ringkasan. */
export const listSessions = ({ limit }) => request(`/sessions?limit=${limit}`)

/** GET /sessions/{id}: ringkasan publik skenario dan transkrip. */
export const getSession = (sessionId) => request(`/sessions/${sessionId}`)

/** GET /sessions/{id}/briefing-topics: topik sesi induk yang sudah punya catatan. */
export const getBriefingTopics = (sessionId) => request(`/sessions/${sessionId}/briefing-topics`)

/** POST /sessions/{id}/turns. turn = { content, start_ms, end_ms, words? }; hasilnya giliran klien. */
export const sendTurn = (sessionId, turn) => postJson(`/sessions/${sessionId}/turns`, turn)

/** POST /sessions/{id}/end */
export const endSession = (sessionId) => postJson(`/sessions/${sessionId}/end`)
