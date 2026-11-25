import { Component } from 'react'

// File avatar/animasi yang hilang atau rusak tidak boleh menjatuhkan seluruh halaman simulasi.
export default class AvatarErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    console.error('Avatar gagal dimuat:', error)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="w-full h-full flex items-center justify-center" role="alert">
        <p className="text-xs text-slate-600 bg-white/85 px-3 py-2 rounded-xl shadow">
          Avatar klien tidak dapat dimuat. Simulasi tetap bisa dilanjutkan.
        </p>
      </div>
    )
  }
}
