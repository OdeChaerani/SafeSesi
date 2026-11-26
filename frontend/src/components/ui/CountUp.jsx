import { useEffect, useRef, useState } from 'react'

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const formatNumber = (v) => v.toLocaleString('id-ID', { maximumFractionDigits: 2 })

/** Angka dihitung naik dari 0 saat pertama tampil. */
export default function CountUp({ value, format = formatNumber, duration = 700 }) {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0))
  const frame = useRef(0)
  useEffect(() => {
    if (reducedMotion()) return undefined
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      setShown(value * (1 - (1 - t) ** 3))
      if (t < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [value, duration])
  return format(Number.isInteger(value) ? Math.round(shown) : Math.round(shown * 100) / 100)
}
