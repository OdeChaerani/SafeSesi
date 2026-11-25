import { useState } from 'react'
import AuthBackground from '../components/auth/AuthBackground'
import AuthHero from '../components/auth/AuthHero'
import LoginForm from '../components/auth/LoginForm'
import { login } from '../services/auth'

export default function LoginPage({ onLoginSuccess }) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLoginSubmit = async ({ email, password }) => {
    setIsLoading(true)
    setError('')
    try {
      const data = await login(email, password)
      if (onLoginSuccess) {
        onLoginSuccess(data.user)
      }
    } catch (err) {
      setError(err.message || 'Email atau kata sandi salah.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="w-full min-h-screen flex items-center justify-center relative bg-[#352f55] select-none">
      <div className="min-h-screen w-full flex flex-col lg:flex-row relative overflow-hidden">
        {/* 1. Dynamic SVG Background */}
        <AuthBackground />

        {/* 2. Left Column: Brand & Academic Manifesto */}
        <AuthHero />

        {/* 3. Right Column: Authentication Card */}
        <section className="flex-1 flex items-center justify-center p-6 sm:p-10 lg:p-12 xl:p-16 relative overflow-hidden z-10">
          <LoginForm
            onSubmit={handleLoginSubmit}
            isLoading={isLoading}
            error={error}
          />
        </section>
      </div>
    </main>
  )
}
