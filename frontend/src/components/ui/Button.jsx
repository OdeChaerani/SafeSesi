export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconRight,
  className = '',
  disabled = false,
  type = 'button',
  onClick,
  ...props
}) {
  const baseStyles =
    'inline-flex items-center justify-center font-bold transition-all cursor-pointer select-none focus:outline-none'

  const variants = {
    primary:
      'bg-[#f5b51b] hover:bg-[#e2a613] text-[#1e1a34] shadow-xs active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
    secondary:
      'bg-[#352f55] hover:bg-[#282343] text-white shadow-xs active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
    outline:
      'bg-slate-100 hover:bg-slate-200 text-[#352f55] border border-slate-200/80 shadow-xs active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
    ghost:
      'bg-transparent hover:bg-slate-100 text-[#352f55] active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
    danger:
      'bg-rose-500 hover:bg-rose-600 text-white shadow-xs active:scale-95 disabled:opacity-50 disabled:pointer-events-none',
  }

  const sizes = {
    sm: 'text-xs px-3 py-1.5 rounded-lg gap-1',
    md: 'text-xs md:text-sm px-4 py-2.5 rounded-xl gap-1.5',
    lg: 'text-sm md:text-base px-5 py-3 rounded-xl gap-2',
  }

  const iconSizes = {
    sm: 'text-[16px]',
    md: 'text-[16px]',
    lg: 'text-[18px]',
  }

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${baseStyles} ${variants[variant] || variants.primary} ${
        sizes[size] || sizes.md
      } ${className}`}
      {...props}
    >
      {icon && (
        <span
          className={`material-symbols-outlined ${
            iconSizes[size] || 'text-[16px]'
          }`}
        >
          {icon}
        </span>
      )}
      {children}
      {iconRight && (
        <span
          className={`material-symbols-outlined ${
            iconSizes[size] || 'text-[16px]'
          }`}
        >
          {iconRight}
        </span>
      )}
    </button>
  )
}

