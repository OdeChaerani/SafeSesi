import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRoleLabel } from '../../services/auth'

const itemClass =
  'w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-left cursor-pointer text-slate-700 hover:bg-slate-100 focus-visible:bg-slate-100'

/** Tombol nama + role di header dengan dropdown Profil dan Keluar. */
export default function UserMenu({ user, onLogout }) {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const rootRef = useRef(null)
  const buttonRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    const onPointerDown = (e) => {
      if (!rootRef.current?.contains(e.target)) setIsOpen(false)
    }
    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return
      setIsOpen(false)
      buttonRef.current?.focus()
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [isOpen])

  const select = (action) => () => {
    setIsOpen(false)
    action?.()
  }

  return (
    <div
      ref={rootRef}
      className="relative"
      onBlur={(e) => {
        // Fokus keyboard pindah ke luar menu (Tab): tutup.
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setIsOpen(false)
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        aria-controls="user-menu"
        className="flex items-center gap-2 pl-1.5 pr-2 py-1 rounded-full bg-slate-100 hover:bg-slate-200 border border-slate-200/80 transition cursor-pointer"
      >
        <span className="w-7 h-7 rounded-full bg-[#352f55] flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-white text-[16px]" aria-hidden="true">person</span>
        </span>
        <span className="flex flex-col items-start min-w-0 max-w-[10rem] leading-tight">
          <span className="text-xs font-semibold text-[#1e1a34] truncate max-w-full">{user.name}</span>
          <span className="text-[10px] text-slate-500 truncate max-w-full">{getRoleLabel(user.role)}</span>
        </span>
        <span className="material-symbols-outlined text-[16px] text-slate-500" aria-hidden="true">expand_more</span>
      </button>

      {isOpen && (
        <div id="user-menu" className="absolute right-0 mt-1.5 w-44 py-1 bg-white rounded-xl shadow-lg border border-slate-200">
          <button type="button" className={itemClass} onClick={select(() => navigate('/profil'))}>
            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">badge</span>
            Profil
          </button>
          <button type="button" className={itemClass} onClick={select(onLogout)}>
            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">logout</span>
            Keluar
          </button>
        </div>
      )}
    </div>
  )
}
