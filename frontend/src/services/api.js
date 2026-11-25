// Klien API bersama: semua panggilan backend lewat request() agar header dan penanganan token seragam.
import { apiUrl } from '../config'

let accessToken = null
let onAuthExpiredCallback = null
let refreshPromise = null

export function setAccessToken(token) {
  accessToken = token
}

export function getAccessToken() {
  return accessToken
}

export function setOnAuthExpired(callback) {
  onAuthExpiredCallback = callback
}

export class ApiError extends Error {
  constructor(status, message, retryAfter = null, field = null) {
    super(message)
    this.field = field // isian formulir yang bermasalah, bila backend menyebutnya
    this.status = status // 0 = server tidak terjangkau
    this.retryAfter = retryAfter // detik (header Retry-After pada 429), atau null
  }
}

function parseRetryAfter(res) {
  const seconds = Number(res.headers.get('Retry-After'))
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null
}

/**
 * Meminta rotasi refresh token ke backend.
 * Menggunakan shared promise (single-flight) agar pemanggilan bersamaan
 * hanya memicu SATU kali request ke backend (mencegah token family revoked akibat deteksi reuse).
 */
export async function doRefreshToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(apiUrl('/api/v1/auth/refresh'), {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        })
        if (res.status === 400 || res.status === 401) {
          // Refresh token ditolak: sesi benar-benar berakhir.
          setAccessToken(null)
          if (onAuthExpiredCallback) onAuthExpiredCallback()
          return null
        }
        if (!res.ok) {
          // Mis. 429 (dibatasi) atau 5xx: sesi belum tentu berakhir, jadi token dipertahankan.
          const body = await res.json().catch(() => null)
          throw new ApiError(res.status, body?.detail || `Permintaan gagal (${res.status}).`, parseRetryAfter(res))
        }
        const data = await res.json()
        setAccessToken(data.access_token)
        return data
      } catch (err) {
        if (err instanceof ApiError) throw err // 429/5xx dari atas: sesi tetap
        setAccessToken(null)
        if (onAuthExpiredCallback) onAuthExpiredCallback()
        return null
      } finally {
        refreshPromise = null
      }
    })()
  }
  return refreshPromise
}

/** Panggil /api/v1{path}. Mengembalikan body JSON; melempar ApiError berisi `detail` dari backend. */
export async function request(path, options = {}) {
  // Endpoint auth yang butuh login: 401 (access token habis) tetap ditangani refresh seperti endpoint biasa.
  const isAuthEndpoint = path.startsWith('/auth/') && !['/auth/me', '/auth/change-password'].includes(path)
  const headers = { ...options.headers }

  if (accessToken && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  if (
    options.body &&
    typeof options.body === 'string' &&
    !headers['Content-Type']
  ) {
    headers['Content-Type'] = 'application/json'
  }

  const fetchOptions = {
    ...options,
    headers,
    credentials: 'include',
  }

  let res
  try {
    res = await fetch(apiUrl(`/api/v1${path}`), fetchOptions)
  } catch {
    throw new ApiError(0, 'Tidak dapat terhubung ke server. Pastikan backend sedang berjalan.')
  }

  // Interceptor 401: lakukan refresh token jika bukan endpoint auth
  if (res.status === 401 && !isAuthEndpoint) {
    const data = await doRefreshToken()
    if (data?.access_token) {
      const retryHeaders = {
        ...headers,
        Authorization: `Bearer ${data.access_token}`,
      }
      try {
        res = await fetch(apiUrl(`/api/v1${path}`), {
          ...fetchOptions,
          headers: retryHeaders,
        })
      } catch {
        throw new ApiError(0, 'Tidak dapat terhubung ke server. Pastikan backend sedang berjalan.')
      }
    }
  }

  if (res.status === 204) {
    return null
  }

  const body = await res.json().catch(() => null)
  if (!res.ok) {
    // detail berupa daftar = kesalahan validasi skema (FastAPI); ambil pesan dan nama isian pertama.
    const invalid = Array.isArray(body?.detail) ? body.detail[0] : null
    const message = invalid ? invalid.msg?.replace(/^Value error, /, '') : body?.detail
    const field = invalid ? invalid.loc?.at(-1) : body?.field
    throw new ApiError(res.status, message || `Permintaan gagal (${res.status}).`, parseRetryAfter(res), field ?? null)
  }
  return body
}

export const postJson = (path, data) =>
  request(path, {
    method: 'POST',
    body: data === undefined ? undefined : JSON.stringify(data),
  })
