// Semua cukup gelap untuk teks putih (kontras AA).
const COLORS = ['#352f55', '#7b5800', '#0f766e', '#1d4ed8', '#9f1239', '#6d28d9', '#166534', '#9a3412']

/** Lingkaran inisial dengan warna turunan dari nama. Hiasan: namanya harus tertulis di dekatnya. */
export default function Avatar({ name, className = 'w-8 h-8 text-[11px]' }) {
  const words = name.trim().split(/\s+/)
  const initials = [words[0], words.length > 1 ? words.at(-1) : ''].map((w) => w.charAt(0)).join('').toUpperCase()
  const hash = [...name].reduce((sum, char) => (sum * 31 + char.codePointAt(0)) >>> 0, 0)
  return (
    <span
      aria-hidden="true"
      className={`rounded-full shrink-0 flex items-center justify-center font-bold text-white ${className}`}
      style={{ backgroundColor: COLORS[hash % COLORS.length] }}
    >
      {initials}
    </span>
  )
}
