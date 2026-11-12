import { useNavigate } from 'react-router-dom'
import WelcomeBanner from '../components/dashboard/WelcomeBanner'
import StatCards from '../components/dashboard/StatCards'
import ClassActivities from '../components/dashboard/ClassActivities'
import RecentHistory from '../components/dashboard/RecentHistory'

export default function DashboardPage({ onStartExercise }) {
  const navigate = useNavigate()

  const handleStartExercise = (activity) => {
    if (onStartExercise) {
      onStartExercise(activity)
    } else {
      const scenarioId = activity.scenarioId || activity.id || 1
      navigate(`/latihan-mandiri/${scenarioId}/briefing`, {
        state: { scenario: activity },
      })
    }
  }

  const handleViewAllHistory = () => {
    navigate('/riwayat')
  }

  const handleHistoryAction = (item) => {
    console.log('Aksi riwayat:', item.actionLabel, item.title)
  }

  return (
    <>
      {/* 1. Header Sambutan Personal */}
      <WelcomeBanner userName="Rani" />

      {/* 2. 4 Kartu Statistik */}
      <StatCards />

      {/* 3. Kegiatan Kelas yang Menunggu */}
      <ClassActivities onStartExercise={handleStartExercise} />

      {/* 4. Riwayat Terbaru */}
      <RecentHistory
        onViewAll={handleViewAllHistory}
        onItemAction={handleHistoryAction}
      />
    </>
  )
}
