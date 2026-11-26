import { useCallback, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import BriefingHeader from '../components/briefing/BriefingHeader'
import ClientProfileCard from '../components/briefing/ClientProfileCard'
import DeviceCheckModal from '../components/briefing/DeviceCheckModal'
import PreviousSessionNotes from '../components/briefing/PreviousSessionNotes'
import SessionActionCard from '../components/briefing/SessionActionCard'
import { ErrorState } from '../components/dashboard/SectionState'
import Button from '../components/ui/Button'
import Collapse from '../components/ui/Collapse'
import Toasts from '../components/ui/Toasts'
import { useRequest } from '../hooks/useRequest'
import { useToasts } from '../hooks/useToasts'
import { getClasses } from '../services/classes'
import { getScenarioBriefing } from '../services/scenarios'
import { createSession, listSessions } from '../services/sessions'
import { numberSessions } from '../utils/sessionNumbers'

const isId = (value) => /^[1-9]\d{0,17}$/.test(value)

function InvalidAddress({ message, onBack }) {
  return (
    <div role="alert" className="bg-white rounded-2xl p-8 flex flex-col items-center text-center gap-3">
      <span className="material-symbols-outlined text-[32px] text-rose-700" aria-hidden="true">error</span>
      <h1 className="text-base font-bold text-[#1e1a34]">Briefing tidak bisa dibuka</h1>
      <p className="text-sm text-slate-600 max-w-md">{message}</p>
      <Button icon="arrow_back" onClick={onBack} className="min-h-10">Kembali ke beranda</Button>
    </div>
  )
}

function Skeleton() {
  return (
    <div role="status" className="flex flex-col gap-4">
      <span className="sr-only">Memuat briefing</span>
      <span className="ss-skeleton block h-4 w-48 rounded" />
      <span className="ss-skeleton block h-7 w-80 max-w-full rounded" />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-7 h-72 bg-white rounded-2xl p-6 space-y-4">
          <span className="ss-skeleton block h-14 w-2/3 rounded-xl" />
          <span className="ss-skeleton block h-20 rounded-xl" />
          <span className="ss-skeleton block h-16 rounded-xl" />
        </div>
        <div className="lg:col-span-5 h-72 bg-white rounded-2xl p-5 space-y-3">
          <span className="ss-skeleton block h-14 rounded-xl" />
          <span className="ss-skeleton block h-14 rounded-xl" />
          <span className="ss-skeleton block h-11 rounded-xl" />
        </div>
      </div>
    </div>
  )
}

function Briefing({ scenarioId, classId }) {
  const navigate = useNavigate()
  // Katalog masih mengirim pilihan awal lewat state navigasi; data skenario selalu dari server.
  const preset = useLocation().state?.scenario
  const [chosenMode, setChosenMode] = useState(preset?.mode === 'continue' ? 'continue' : 'new')
  const [chosenParent, setChosenParent] = useState(preset?.parentSessionId ?? null)
  const [isStarting, setIsStarting] = useState(false)
  // Aksi yang menunggu cek perangkat: null, { type: 'start' }, atau { type: 'resume', sessionId }.
  const [pending, setPending] = useState(null)
  const startingRef = useRef(false)
  const { toasts, addToast, dismissToast } = useToasts()

  const loadBriefing = useCallback(async () => {
    const [scenario, classes] = await Promise.all([getScenarioBriefing(scenarioId, classId), classId ? getClasses() : []])
    const klass = classes.find((item) => item.id === classId)
    if (classId && !klass) throw new Error('Kelas ini tidak terhubung dengan akunmu.')
    return { scenario, className: klass?.name }
  }, [scenarioId, classId])
  const briefing = useRequest(loadBriefing)

  // Sesi milik sendiri pada konteks yang sama (mandiri, atau kelas ini), terbaru dulu. Semua status diambil
  // agar nomor sesi tidak bergeser saat sesi yang masih berjalan nanti selesai.
  const loadHistory = useCallback(async () => {
    // shortcut: API membatasi 100 baris; nomor sesi meleset bila satu skenario dicoba lebih dari itu.
    const data = await listSessions({ limit: 100, scenarioId, type: classId ? 'class' : 'independent' })
    return numberSessions(data.items.filter((item) => item.class_id === classId))
  }, [scenarioId, classId])
  const history = useRequest(loadHistory)

  const goBack = () => navigate(classId ? '/beranda' : '/latihan-mandiri')

  if (briefing.data === undefined) {
    if (!briefing.error) return <Skeleton />
    return (
      <div className="flex flex-col gap-3">
        <ErrorState message={`Briefing tidak bisa dibuka. ${briefing.error.message}`} onRetry={briefing.reload} />
        <Button variant="outline" icon="arrow_back" onClick={() => navigate('/beranda')} className="self-start min-h-10">
          Kembali ke beranda
        </Button>
      </div>
    )
  }

  const { scenario, className } = briefing.data
  const completed = history.data?.filter((item) => item.status === 'completed') ?? []
  const mode = chosenMode === 'continue' && completed.length > 0 ? 'continue' : 'new'
  const parentId =
    mode === 'continue' ? (completed.some((item) => item.id === chosenParent) ? chosenParent : completed[0].id) : null
  // Pilihan "lanjutkan" dari katalog belum bisa dipastikan selama riwayat dimuat.
  const isWaitingHistory = chosenMode === 'continue' && history.data === undefined && !history.error

  const openSimulation = (sessionId, publicScenario) =>
    navigate(`/simulasi/${sessionId}`, {
      state: {
        scenario: {
          sessionId,
          scenarioId,
          title: scenario.title,
          publicScenario,
          category: classId ? 'Latihan Kelas' : 'Latihan Mandiri',
        },
      },
    })

  const start = async () => {
    if (startingRef.current || isWaitingHistory) return
    startingRef.current = true
    setIsStarting(true)
    try {
      const created = await createSession({
        scenario_id: scenarioId,
        class_id: classId,
        // "repeat" = mulai dari awal untuk skenario yang sudah pernah dicoba.
        mode: mode === 'continue' ? 'continue' : scenario.total_attempts > 0 ? 'repeat' : 'new',
        parent_session_id: parentId,
      })
      openSimulation(created.id, created.scenario)
    } catch (err) {
      addToast('error', `Sesi gagal dibuat. ${err.message}`)
      startingRef.current = false
      setIsStarting(false)
      setPending(null) // tutup modal agar pesan galat terlihat
    }
  }

  const askStart = () => setPending({ type: 'start' })
  const confirm = () => (pending.type === 'resume' ? openSimulation(pending.sessionId, scenario) : start())

  return (
    <div className="flex flex-col gap-3 w-full max-w-6xl pb-4">
      <BriefingHeader title={scenario.title} className={className} onBack={goBack} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
        <div className="lg:col-span-8 flex flex-col">
          <ClientProfileCard scenario={scenario} />
          <Collapse open={mode === 'continue'}>
            <div className="pt-3">
              {parentId && (
                <PreviousSessionNotes
                  sessionId={parentId}
                  sessionNumber={completed.find((item) => item.id === parentId).number}
                  onOpenFeedback={(id) => navigate(`/evaluasi/${id}`)}
                />
              )}
            </div>
          </Collapse>
        </div>

        <div className="lg:col-span-4">
          <div className="flex flex-col gap-4 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto">
            <SessionActionCard
              className={className}
              history={history}
              completed={completed}
              mode={mode}
              onModeChange={setChosenMode}
              parentId={parentId}
              onParentChange={setChosenParent}
              activeSessionId={scenario.active_session_id}
              onResume={(sessionId) => setPending({ type: 'resume', sessionId })}
              onStart={askStart}
              isStarting={isStarting || isWaitingHistory}
            />
          </div>
        </div>
      </div>

      {/* Layar sempit: tombol mulai menempel di bawah agar selalu terjangkau. */}
      <div className="lg:hidden sticky bottom-3 z-20">
        <Button iconRight="play_arrow" loading={isStarting || isWaitingHistory} onClick={askStart} className="w-full min-h-12 !shadow-lg">
          {isStarting ? 'Menyiapkan sesi...' : mode === 'continue' ? 'Lanjutkan sesi' : 'Mulai sesi'}
        </Button>
      </div>

      {pending && (
        <DeviceCheckModal
          confirmLabel={pending.type === 'resume' || mode === 'continue' ? 'Lanjutkan sesi' : 'Mulai sesi'}
          isStarting={isStarting}
          onConfirm={confirm}
          onClose={() => setPending(null)}
        />
      )}
      <Toasts toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default function BriefingPage() {
  const { scenarioId } = useParams()
  const [searchParams] = useSearchParams()
  const classParam = searchParams.get('kelas')
  const navigate = useNavigate()

  if (!isId(scenarioId) || (classParam !== null && !isId(classParam))) {
    return <InvalidAddress message="Alamat skenario atau kelas tidak valid." onBack={() => navigate('/beranda')} />
  }
  const classId = classParam === null ? null : Number(classParam)
  // key: pindah skenario atau kelas memulai halaman dengan keadaan bersih.
  return <Briefing key={`${scenarioId}-${classId}`} scenarioId={Number(scenarioId)} classId={classId} />
}
