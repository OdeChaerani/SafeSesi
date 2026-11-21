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
  constructor(status, message) {
    super(message)
    this.status = status // 0 = server tidak terjangkau
  }
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
        if (!res.ok) {
          setAccessToken(null)
          if (onAuthExpiredCallback) onAuthExpiredCallback()
          return null
        }
        const data = await res.json()
        setAccessToken(data.access_token)
        return data
      } catch {
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
  const isAuthEndpoint = path.startsWith('/auth/')
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
    throw new ApiError(res.status, body?.detail || `Permintaan gagal (${res.status}).`)
  }
  return body
}

export const postJson = (path, data) =>
  request(path, {
    method: 'POST',
    body: data === undefined ? undefined : JSON.stringify(data),
  })
