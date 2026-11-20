// Lapisan pengambil data evaluasi. Halaman hanya memakai fungsi di sini.
import { apiUrl } from '../config'

// shortcut: user dev tetap, sama seperti halaman lain; ganti dengan token login saat auth JWT tersedia.
const HEADERS = { 'Content-Type': 'application/json', 'X-Dev-User-Id': '1' }

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(apiUrl(`/api/v1${path}`), { headers: HEADERS, ...options })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server. Pastikan backend sedang berjalan.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail || `Permintaan gagal (${res.status}).`)
  return body
}

/** GET /sessions/{id}/evaluation. ApiError 404 jika evaluasi belum dibuat. */
export const getEvaluation = (sessionId) => request(`/sessions/${sessionId}/evaluation`)

/** POST /sessions/{id}/evaluation. Mengembalikan payload status (biasanya "running"). */
export const requestEvaluation = (sessionId) => request(`/sessions/${sessionId}/evaluation`, { method: 'POST' })

/** GET /sessions/{id}: ringkasan publik skenario dan transkrip. */
export const getSession = (sessionId) => request(`/sessions/${sessionId}`)
