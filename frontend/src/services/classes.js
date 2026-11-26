// Kelas mahasiswa.
import { request } from './api'

/** GET /classes: kelas aktif milik mahasiswa (nama, tahun akademik, dosen). */
export const getClasses = () => request('/classes')

/** GET /classes/{id}/scenarios: ringkasan publik skenario kelas beserta status percobaan. */
export const getClassScenarios = (classId) => request(`/classes/${classId}/scenarios`)
