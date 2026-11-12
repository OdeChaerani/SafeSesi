// Alamat backend dari variabel env Vite (lihat frontend/.env.example).
// 127.0.0.1 dipakai sebagai default, bukan localhost: di Windows, localhost bisa
// dicoba lewat IPv6 (::1) dulu sementara uvicorn hanya listen di IPv4.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

/** URL lengkap endpoint API, mis. apiUrl('/api/v1/sessions') */
export const apiUrl = (path) => `${API_BASE_URL}${path}`
