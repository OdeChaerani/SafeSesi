export default function Badge({
  children,
  variant = 'neutral',
  icon,
  className = '',
}) {
  const baseStyles =
    'inline-flex items-center gap-1 font-semibold text-[11px] px-2.5 py-0.5 rounded-full select-none'

  const variants = {
    unattempted: 'bg-slate-100 text-slate-600',
    attempted: 'bg-[#352f55] text-white',
    neutral: 'bg-slate-100 text-slate-600',
    primary: 'bg-[#352f55] text-white',
    success: 'bg-emerald-50 text-emerald-700 border border-emerald-200/60',
    warning: 'bg-amber-50 text-amber-800 border border-amber-200/60',
    danger: 'bg-rose-50 text-rose-700 border border-rose-200/60',
  }

  return (
    <span
      className={`${baseStyles} ${variants[variant] || variants.neutral} ${className}`}
    >
      {icon && (
        <span className="material-symbols-outlined text-[13px]">{icon}</span>
      )}
      {children}
    </span>
  )
}

