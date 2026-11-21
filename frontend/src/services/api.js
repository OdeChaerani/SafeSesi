// Klien API bersama: semua panggilan backend lewat request() agar header dan pesan error seragam.
import { apiUrl } from '../config'

// shortcut: user dev tetap; ganti dengan token login di satu tempat ini saat auth JWT tersedia.
const HEADERS = { 'Content-Type': 'application/json', 'X-Dev-User-Id': '1' }

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status // 0 = server tidak terjangkau
  }
}

/** Panggil /api/v1{path}. Mengembalikan body JSON; melempar ApiError berisi `detail` dari backend. */
export async function request(path, options = {}) {
  let res
  try {
    res = await fetch(apiUrl(`/api/v1${path}`), { ...options, headers: { ...HEADERS, ...options.headers } })
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server. Pastikan backend sedang berjalan.')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail || `Permintaan gagal (${res.status}).`)
  return body
}

export const postJson = (path, data) => request(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) })
