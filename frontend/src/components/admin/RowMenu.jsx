import { useEffect, useId, useRef, useState } from 'react'

/**
 * Menu aksi satu baris. Posisi fixed agar tidak terpotong wadah tabel yang bisa digulir.
 * items: [{ label, icon, onSelect }]
 */
export default function RowMenu({ label, items, busy = false }) {
  const [position, setPosition] = useState(null)
  const buttonRef = useRef(null)
  const menuRef = useRef(null)
  const menuId = useId()
  const isOpen = position !== null

  const open = () => {
    const rect = buttonRef.current.getBoundingClientRect()
    const right = window.innerWidth - rect.right
    const height = items.length * 40 + 16
    setPosition(
      rect.bottom + height > window.innerHeight
        ? { right, bottom: window.innerHeight - rect.top + 4, transformOrigin: 'bottom right' }
        : { right, top: rect.bottom + 4, transformOrigin: 'top right' },
    )
  }

  const close = () => setPosition(null)

  useEffect(() => {
    if (!isOpen) return undefined
    menuRef.current?.querySelector('[role="menuitem"]')?.focus({ preventScroll: true })
    const onPointerDown = (e) => {
      if (!menuRef.current?.contains(e.target) && !buttonRef.current?.contains(e.target)) close()
    }
    document.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [isOpen])

  const onMenuKeyDown = (e) => {
    const nodes = [...menuRef.current.querySelectorAll('[role="menuitem"]')]
    const index = nodes.indexOf(document.activeElement)
    const next = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: nodes.length - 1 }[e.key]
    if (next !== undefined) {
      e.preventDefault()
      nodes[(next + nodes.length) % nodes.length].focus()
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      // Tab: fokus kembali ke tombol dulu, lalu browser memindahkannya ke elemen berikutnya.
      if (e.key === 'Escape') e.preventDefault()
      buttonRef.current.focus()
      close()
    }
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => {
          if (busy) return
          if (isOpen) close()
          else open()
        }}
        aria-disabled={busy}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-controls={isOpen ? menuId : undefined}
        aria-busy={busy}
        className="w-10 h-10 rounded-lg inline-flex items-center justify-center text-slate-700 hover:bg-slate-200 active:scale-95 focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none cursor-pointer aria-disabled:cursor-wait transition"
      >
        {busy ? (
          <span className="ss-spinner" aria-hidden="true" />
        ) : (
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">more_vert</span>
        )}
      </button>
      {isOpen && (
        <div
          ref={menuRef}
          id={menuId}
          role="menu"
          aria-label={label}
          onKeyDown={onMenuKeyDown}
          style={position}
          className="ss-menu fixed z-[55] min-w-60 py-2 bg-white rounded-xl shadow-lg border border-slate-200"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => {
                buttonRef.current.focus()
                close()
                item.onSelect()
              }}
              className="w-full h-10 px-3.5 flex items-center gap-2.5 text-xs md:text-sm font-semibold text-left text-slate-800 hover:bg-slate-100 focus:bg-slate-100 outline-none cursor-pointer transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </div>
      )}
    </>
  )
}
