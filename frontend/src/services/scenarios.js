// Katalog skenario untuk mahasiswa.
import { request } from './api'

/** GET /scenarios/catalog. Filter opsional: search (teks), status ('attempted' | 'unattempted'). */
export function getCatalog({ search = '', status = 'all' } = {}) {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (status !== 'all') params.set('status', status)
  return request(`/scenarios/catalog?${params}`)
}

/** GET /scenarios/{id}: ringkasan publik untuk briefing. classId diisi bila dibuka dari kelas. */
export const getScenarioBriefing = (scenarioId, classId) =>
  request(`/scenarios/${scenarioId}${classId ? `?class_id=${classId}` : ''}`)

