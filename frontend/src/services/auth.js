import { doRefreshToken, postJson, request, setAccessToken } from './api'

const USER_STORAGE_KEY = 'safesesi_auth_user'

export function getSavedUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveUser(user) {
  if (user) {
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
  } else {
    localStorage.removeItem(USER_STORAGE_KEY)
  }
}

/**
 * Masuk dengan email dan password.
 * Cookie refresh token (HttpOnly) disetel otomatis oleh respons backend.
 * Mengembalikan { access_token, token_type, expires_in, user }.
 */
export async function login(email, password) {
  const res = await postJson('/auth/login', { email, password })
  if (res?.access_token) {
    setAccessToken(res.access_token)
  }
  if (res?.user) {
    saveUser(res.user)
  }
  return res
}

/**
 * Keluar akun. Mencabut family refresh token di backend dan menghapus cookie.
 */
export async function logout() {
  try {
    await request('/auth/logout', { method: 'POST' })
  } catch {
    // Abaikan error jaringan saat logout
  } finally {
    setAccessToken(null)
    saveUser(null)
  }
}

/**
 * Aktivasi akun baru dengan token dan kata sandi baru.
 */
export async function activate(token, password) {
  return postJson('/auth/activate', { token, password })
}

const ROLE_LABELS = { student: 'Mahasiswa', lecturer: 'Dosen Praktikum', admin: 'Administrator' }

export const getRoleLabel = (role) => ROLE_LABELS[role] || role || 'Pengguna'

/** Data akun pengguna yang sedang masuk (dari database). */
export function getMe() {
  return request('/auth/me')
}

/**
 * Ganti kata sandi pengguna yang sedang masuk. Backend mencabut semua sesi lain dan menerbitkan
 * sesi baru untuk perangkat ini (cookie refresh baru + access token baru), jadi tidak perlu login ulang.
 */
export async function changePassword(currentPassword, newPassword) {
  const res = await postJson('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  if (res?.access_token) {
    setAccessToken(res.access_token)
  }
  if (res?.user) {
    saveUser(res.user)
  }
  return res
}

/**
 * Pulihkan sesi saat aplikasi pertama kali dimuat (atau setelah F5/reload).
 * Memanggil doRefreshToken() yang aman dari race condition (single-flight).
 */
export async function restoreSession() {
  const data = await doRefreshToken()
  if (data?.user) {
    saveUser(data.user)
    return data.user
  }
  saveUser(null)
  return null
}
