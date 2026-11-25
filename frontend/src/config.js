// Alamat backend dari variabel env Vite (lihat frontend/.env.example).
// Di mode development (Vite dev server), selalu gunakan relative URL ('')
// agar request /api/... selalu melewati Vite proxy bawaan server.
// Ini mencegah browser memblokir cookie HTTP-Only SameSite=Lax akibat
// perbedaan origin/port antara frontend (5173) dan backend (8000).
// Di production (production build), gunakan VITE_API_BASE_URL jika ada.
export const API_BASE_URL = import.meta.env.DEV
  ? ''
  : (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

/** URL lengkap endpoint API, mis. apiUrl('/api/v1/sessions') */
export const apiUrl = (path) => `${API_BASE_URL}${path}`
