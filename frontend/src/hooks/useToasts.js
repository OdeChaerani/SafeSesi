import { useCallback, useRef, useState } from 'react'

/** Daftar notifikasi untuk <Toasts>. type: 'success' | 'error'. */
export function useToasts() {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(0)

  const addToast = useCallback((type, message) => {
    const id = ++nextId.current
    setToasts((prev) => [...prev, { id, type, message }])
  }, [])

  const dismissToast = useCallback((id) => setToasts((prev) => prev.filter((toast) => toast.id !== id)), [])

  return { toasts, addToast, dismissToast }
}
