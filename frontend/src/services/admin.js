import { postJson, request } from './api'

/** Daftar pengguna. `query` = query string hasil URLSearchParams. */
export const listUsers = (query) => request(`/admin/users?${query}`)

export const createUser = (data) => postJson('/admin/users', data)

/** Tautan hasil kedua panggilan ini hanya dikembalikan sekali. */
export const resendActivation = (id) => postJson(`/admin/users/${id}/resend-activation`)

export const resetPassword = (id) => postJson(`/admin/users/${id}/reset-password`)
