import { useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import DashboardLayout from './components/layout/DashboardLayout'
import DashboardPage from './pages/DashboardPage'
import CatalogPage from './pages/CatalogPage'
import BriefingPage from './pages/BriefingPage'
import SimulationPage from './pages/SimulationPage'
import LoginPage from './pages/LoginPage'
import EvaluationPage from './pages/EvaluationPage'

const AUTH_STORAGE_KEY = 'safesesi_auth_user'

function ProtectedRoute({ isAuthenticated, children }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  const navigate = useNavigate()

  // Muat status autentikasi dari localStorage agar persisten saat F5 / reload
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(AUTH_STORAGE_KEY)
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const isAuthenticated = Boolean(user)

  const handleLogin = (credentials) => {
    const userObj = {
      username: credentials?.username || 'Rani Aulia',
      role: 'Mahasiswa Angkatan 2023',
      token: 'dev-token-student-1',
    }
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(userObj))
    setUser(userObj)
    navigate('/beranda', { replace: true })
  }

  const handleLogout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setUser(null)
    navigate('/login', { replace: true })
  }

  return (
    <Routes>
      {/* 1. Public Route: Login */}
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/beranda" replace />
          ) : (
            <LoginPage onLogin={handleLogin} />
          )
        }
      />

      {/* 2. Protected Routes di dalam DashboardLayout */}
      <Route
        path="/"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <DashboardPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/beranda"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <DashboardPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/latihan-mandiri"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <CatalogPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      {/* Subpage Briefing: /latihan-mandiri/:scenarioId/briefing */}
      <Route
        path="/latihan-mandiri/:scenarioId/briefing"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <BriefingPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/kelas-saya"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <div className="bg-white p-6 md:p-8 rounded-2xl shadow-xs border border-slate-100 flex flex-col items-center justify-center text-center gap-3 py-14">
                <div className="w-12 h-12 rounded-xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
                  <span className="material-symbols-outlined text-[28px]">
                    school
                  </span>
                </div>
                <h2 className="text-lg md:text-xl text-[#1e1a34] font-bold">
                  Kelas Praktikum Saya
                </h2>
                <p className="text-xs md:text-sm text-[#64748b] max-w-md">
                  Daftar penugasan terstruktur dari dosen pengampu praktikum konseling Anda.
                </p>
              </div>
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/riwayat"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <div className="bg-white p-6 md:p-8 rounded-2xl shadow-xs border border-slate-100 flex flex-col items-center justify-center text-center gap-3 py-14">
                <div className="w-12 h-12 rounded-xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
                  <span className="material-symbols-outlined text-[28px]">
                    history
                  </span>
                </div>
                <h2 className="text-lg md:text-xl text-[#1e1a34] font-bold">
                  Riwayat Sesi Konseling
                </h2>
                <p className="text-xs md:text-sm text-[#64748b] max-w-md">
                  Arsip seluruh transkrip percakapan, metrik evaluasi OARS, dan catatan perkembangan klien.
                </p>
              </div>
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      {/* 3. Immersive Simulation Room (Layar Penuh tanpa Sidebar) */}
      <Route
        path="/simulasi/:sessionId"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <SimulationPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/evaluasi/:sessionId"
        element={
          <ProtectedRoute isAuthenticated={isAuthenticated}>
            <DashboardLayout onLogout={handleLogout}>
              <EvaluationPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      {/* 4. Catch-all: Redirect ke beranda atau login */}
      <Route
        path="*"
        element={
          <Navigate to={isAuthenticated ? '/beranda' : '/login'} replace />
        }
      />
    </Routes>
  )
}

export default App
