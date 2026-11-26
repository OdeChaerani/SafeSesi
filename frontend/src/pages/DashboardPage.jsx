import { useNavigate } from 'react-router-dom'
import ClassActivities from '../components/dashboard/ClassActivities'
import RecentHistory from '../components/dashboard/RecentHistory'
import StatCards from '../components/dashboard/StatCards'
import WelcomeBanner from '../components/dashboard/WelcomeBanner'
import { useRequest } from '../hooks/useRequest'
import { getClasses } from '../services/classes'
import { getCatalog } from '../services/scenarios'
import { listSessions } from '../services/sessions'
import { formatDuration } from '../utils/format'

const loadRecentSessions = () => listSessions({ limit: 3 })
const loadCatalog = () => getCatalog()

// Beranda mahasiswa: ringkasan latihan, kegiatan kelas, dan tiga sesi terakhir.
export default function DashboardPage({ user }) {
  const navigate = useNavigate()
  const sessions = useRequest(loadRecentSessions)
  const catalog = useRequest(loadCatalog)
  const classes = useRequest(getClasses)

  const percent = (part, whole) => (whole > 0 ? Math.round((part / whole) * 100) : 0)

  // Batang di bawah angka: proporsi bila ada pembandingnya, selain itu garis aksen (penuh bila ada isinya).
  const stats = [
    {
      id: 'selesai',
      title: 'Sesi selesai',
      icon: 'check_circle',
      iconFill: true,
      subtitle: 'Sesi latihan yang diselesaikan',
      source: sessions,
      value: sessions.data?.completed_sessions,
      barColor: '#352f55',
      progressPercent: percent(sessions.data?.completed_sessions, sessions.data?.total_sessions),
    },
    {
      id: 'dicoba',
      title: 'Skenario dicoba',
      icon: 'explore',
      subtitle: 'Latihan mandiri dari katalog',
      source: catalog,
      value: catalog.data?.attempted_count,
      unit: catalog.data && `/ ${catalog.data.total}`,
      barColor: '#f5b51b',
      progressPercent: percent(catalog.data?.attempted_count, catalog.data?.total),
    },
    {
      id: 'waktu',
      title: 'Waktu latihan',
      icon: 'timer',
      subtitle: 'Akumulasi durasi sesi selesai',
      source: sessions,
      value: sessions.data?.total_duration_seconds,
      // Di bawah 1 jam: angka besar dengan satuan kecil, seperti kartu lain.
      format: (s) => (s >= 3600 ? formatDuration(s) : s > 0 && s < 60 ? '<1' : String(Math.floor(s / 60))),
      unit: sessions.data?.total_duration_seconds < 3600 ? 'menit' : undefined,
      barColor: '#352f55',
      progressPercent: sessions.data?.total_duration_seconds > 0 ? 100 : 0,
    },
    {
      id: 'kelas',
      title: 'Kelas aktif',
      icon: 'school',
      subtitle: 'Kelas praktikum aktif',
      source: classes,
      value: classes.data?.length,
      barColor: '#f5b51b',
      progressPercent: classes.data?.length > 0 ? 100 : 0,
    },
  ]

  const openSimulation = (sessionId, scenario) =>
    navigate(`/simulasi/${sessionId}`, { state: { scenario: { ...scenario, sessionId } } })

  const resume = (item, sessionId) => openSimulation(sessionId, { scenarioId: item.id, title: item.title })

  const openBriefing = (item, classId) =>
    navigate(`/latihan-mandiri/${item.id}/briefing`, {
      state: {
        scenario: {
          ...item,
          classId,
          category: 'Latihan Kelas',
          // Mode "lanjutkan" hanya sah bila ada sesi selesai; tanpa itu halaman briefing tidak boleh menawarkannya.
          attempt_status: item.last_completed_session_id ? item.attempt_status : 'unattempted',
        },
      },
    })

  return (
    <>
      <WelcomeBanner
        userName={user?.name?.trim().split(/\s+/)[0]}
        academicYears={[...new Set(classes.data?.map((klass) => klass.academic_year))]}
      />
      <StatCards stats={stats} />
      <ClassActivities classes={classes} onOpenBriefing={openBriefing} onResume={resume} />
      <RecentHistory sessions={sessions} onStartFirst={() => navigate('/latihan-mandiri')} />
    </>
  )
}
