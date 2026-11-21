// Evaluasi sesi. Halaman hanya memakai fungsi di sini.
import { request } from './api'

/** GET /sessions/{id}/evaluation. ApiError 404 jika evaluasi belum dibuat. */
export const getEvaluation = (sessionId) => request(`/sessions/${sessionId}/evaluation`)

/** POST /sessions/{id}/evaluation. Mengembalikan payload status (biasanya "running"). */
export const requestEvaluation = (sessionId) => request(`/sessions/${sessionId}/evaluation`, { method: 'POST' })
