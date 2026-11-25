import { useState } from 'react'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

export default function DashboardLayout({
  children,
  user,
  activeTab,
  onSelectTab,
  onLogout,
}) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  return (
    <div className="relative min-h-screen bg-surface font-body text-body text-on-surface">
      <Navbar
        user={user}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        onLogout={onLogout}
      />
      <Sidebar
        user={user}
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        isOpen={isSidebarOpen}
        onLogout={onLogout}
      />
      <main
        className={`relative pt-14 min-h-screen overflow-x-hidden bg-[#352f55] transition-all duration-300 ease-in-out ${
          isSidebarOpen ? 'w-[calc(100%-15rem)] ml-60' : 'w-full ml-0'
        }`}
      >
        <div className="flex flex-col w-full">
          <div className="max-w-[1400px] mx-auto w-full p-4 md:p-6 lg:p-8 flex flex-col gap-6">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
