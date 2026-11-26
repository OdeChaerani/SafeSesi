import { useCallback, useEffect, useState } from 'react'

/**
 * Memuat data sekali dan bisa diulang. `load` harus stabil (fungsi modul atau useCallback).
 * Saat diulang, data lama tetap tersedia; jawaban yang sudah basi diabaikan.
 */
export function useRequest(load) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState({})

  useEffect(() => {
    let isStale = false
    load()
      .then((data) => {
        if (!isStale) setResult({ load, attempt, data })
      })
      .catch((error) => {
        if (!isStale) setResult((prev) => ({ load, attempt, data: prev.data, error }))
      })
    return () => {
      isStale = true
    }
  }, [load, attempt])

  const isLoading = result.load !== load || result.attempt !== attempt
  const reload = useCallback(() => setAttempt((n) => n + 1), [])
  return { data: result.data, error: isLoading ? undefined : result.error, isLoading, reload }
}
