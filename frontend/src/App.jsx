import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import DashboardLayout from './components/layout/DashboardLayout'
import DashboardPage from './pages/DashboardPage'
import CatalogPage from './pages/CatalogPage'
import BriefingPage from './pages/BriefingPage'
import SimulationPage from './pages/SimulationPage'
import LoginPage from './pages/LoginPage'
import ActivationPage from './pages/ActivationPage'
import LecturerPage from './pages/LecturerPage'
import AdminPage from './pages/AdminPage'
import EvaluationPage from './pages/EvaluationPage'
import { getSavedUser, logout, restoreSession, saveUser } from './services/auth'
import { getAccessToken, setOnAuthExpired } from './services/api'

function getRoleHome(role) {
  switch (role) {
    case 'lecturer':
      return '/dosen'
    case 'admin':
      return '/admin'
    case 'student':
    default:
      return '/beranda'
  }
}

function ProtectedRoute({ user, allowedRoles, children }) {
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getRoleHome(user.role)} replace />
  }
  return children
}

function App() {
  const navigate = useNavigate()
  // Muat data user tersimpan agar UI langsung tahu peran pengguna tanpa flicker
  const [user, setUser] = useState(() => getSavedUser())
  const [isInitializing, setIsInitializing] = useState(!getAccessToken())

  useEffect(() => {
    // Daftarkan listener saat refresh token kedaluwarsa di tengah jalan
    setOnAuthExpired(() => {
      saveUser(null)
      setUser(null)
      navigate('/login', { replace: true })
    })

    // Hanya pulihkan sesi jika access token belum ada di memori (mis. saat pertama buka / reload F5)
    if (!getAccessToken()) {
      restoreSession()
        .then((userData) => {
          if (userData) {
            setUser(userData)
          } else {
            // Sesi kedaluwarsa atau tidak valid di backend
            saveUser(null)
            setUser(null)
          }
        })
        .finally(() => {
          setIsInitializing(false)
        })
    }
  }, [navigate])

  const handleLoginSuccess = (userData) => {
    saveUser(userData)
    setUser(userData)
    navigate(getRoleHome(userData?.role), { replace: true })
  }

  const handleLogout = async () => {
    await logout()
    saveUser(null)
    setUser(null)
    navigate('/login', { replace: true })
  }

  if (isInitializing) {
    return (
      <div className="w-full min-h-screen flex flex-col items-center justify-center bg-[#352f55] text-white">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-3 border-amber-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm font-medium tracking-wide text-slate-200">
            Memuat SafeSesi...
          </span>
        </div>
      </div>
    )
  }

  const isAuthenticated = Boolean(user)

  return (
    <Routes>
      {/* 1. Public Route: Login */}
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to={getRoleHome(user.role)} replace />
          ) : (
            <LoginPage onLoginSuccess={handleLoginSuccess} />
          )
        }
      />

      {/* 2. Public Route: Aktivasi Akun (membaca token dari hash URL) */}
      <Route
        path="/aktivasi"
        element={
          isAuthenticated ? (
            <Navigate to={getRoleHome(user.role)} replace />
          ) : (
            <ActivationPage />
          )
        }
      />

      {/* 3. Protected Routes untuk Mahasiswa */}
      <Route
        path="/"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
              <DashboardPage user={user} />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/beranda"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
              <DashboardPage user={user} />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/latihan-mandiri"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
              <CatalogPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/latihan-mandiri/:scenarioId/briefing"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
              <BriefingPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/kelas-saya"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
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
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
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

      {/* Sesi Simulasi Real-Time (Layar Penuh) */}
      <Route
        path="/simulasi/:sessionId"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <SimulationPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/evaluasi/:sessionId"
        element={
          <ProtectedRoute user={user} allowedRoles={['student']}>
            <DashboardLayout user={user} onLogout={handleLogout}>
              <EvaluationPage />
            </DashboardLayout>
          </ProtectedRoute>
        }
      />

      {/* 4. Protected Routes untuk Dosen */}
      <Route
        path="/dosen"
        element={
          <ProtectedRoute user={user} allowedRoles={['lecturer']}>
            <LecturerPage user={user} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />

      {/* 5. Protected Routes untuk Administrator */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute user={user} allowedRoles={['admin']}>
            <AdminPage user={user} onLogout={handleLogout} />
          </ProtectedRoute>
        }
      />

      {/* 6. Catch-all: Redirect ke home sesuai role atau ke login */}
      <Route
        path="*"
        element={
          <Navigate to={user ? getRoleHome(user.role) : '/login'} replace />
        }
      />
    </Routes>
  )
}

export default App
