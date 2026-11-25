import UserMenu from './UserMenu'

export default function Navbar({
  user,
  isSidebarOpen = true,
  onToggleSidebar,
  onLogout,
}) {
  return (
    <header className="fixed top-0 left-0 right-0 h-14 z-50 flex items-center justify-between px-5 bg-white border-b border-slate-200 rounded-b-2xl shadow-xs">
      {/* Brand & Subtitle + Sidebar Toggle */}
      <div className="flex items-center gap-3">
        {/* Toggle Sidebar Button */}
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="w-8 h-8 rounded-lg text-[#352f55] hover:bg-slate-100 flex items-center justify-center transition cursor-pointer"
            title={isSidebarOpen ? 'Sembunyikan Sidebar' : 'Tampilkan Sidebar'}
          >
            <span className="material-symbols-outlined text-[20px]">
              {isSidebarOpen ? 'menu_open' : 'menu'}
            </span>
          </button>
        )}

        <span className="text-lg leading-tight tracking-tight flex items-center font-bold">
          <span className="text-[#f5b51b]">Safe</span>
          <span className="text-[#352f55]">Sesi</span>
        </span>

        <div className="h-5 w-px bg-slate-200 hidden md:block" />

        <span className="text-xs text-[#1e1a34] font-medium hidden md:inline-block">
          Ruang Belajar Konseling Virtual
        </span>
      </div>

      {/* Action / Profile Badges */}
      <div className="flex items-center gap-3">
        {user && <UserMenu user={user} onLogout={onLogout} />}
      </div>
    </header>
  )
}
