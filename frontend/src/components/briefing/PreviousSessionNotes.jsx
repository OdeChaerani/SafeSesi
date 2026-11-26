import { useCallback } from 'react'
import { useRequest } from '../../hooks/useRequest'
import { getBriefingTopics } from '../../services/sessions'
import { ErrorState } from '../dashboard/SectionState'
import Button from '../ui/Button'

const FEEDBACK_LABEL = {
  none: 'Minta evaluasi sesi itu',
  running: 'Lihat proses evaluasi',
  completed: 'Lihat umpan balik',
  failed: 'Jalankan ulang evaluasi',
}

/** Catatan topik (hanya yang terisi, disaring backend) dari sesi yang akan dilanjutkan. */
export default function PreviousSessionNotes({ sessionId, sessionNumber, onOpenFeedback }) {
  const load = useCallback(() => getBriefingTopics(sessionId), [sessionId])
  const { data, error, isLoading, reload } = useRequest(load)

  let content
  if (error) {
    content = <ErrorState message={`Catatan sesi sebelumnya belum bisa dimuat. ${error.message}`} onRetry={reload} />
  } else if (isLoading) {
    // Catatan sesi lain tidak boleh terlihat saat pilihan baru sedang dimuat.
    content = (
      <div role="status" className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <span className="sr-only">Memuat catatan sesi sebelumnya</span>
        {[0, 1].map((key) => (
          <span key={key} className="ss-skeleton block h-16 rounded-xl" />
        ))}
      </div>
    )
  } else if (data.topics.length === 0) {
    content = <p className="text-xs text-slate-600">Belum ada catatan pembahasan dari sesi ini.</p>
  } else {
    content = (
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {data.topics.map((topic, index) => (
          <li
            key={topic.name}
            className="ss-fade-up p-2.5 rounded-lg border border-slate-200 bg-slate-50"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <h3 className="text-xs font-bold text-[#1e1a34] break-words">{topic.name}</h3>
            <p className="text-[11px] text-slate-700 leading-relaxed mt-0.5">{topic.description}</p>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <section aria-labelledby="catatan-sebelumnya" className="bg-white rounded-xl p-4 shadow-xs border border-slate-100 flex flex-col gap-2.5">
      <h2 id="catatan-sebelumnya" className="text-xs font-bold text-[#1e1a34]">Catatan dari Sesi {sessionNumber}</h2>
      {content}
      <div className="flex flex-wrap gap-2 pt-1">
        {!isLoading && !error && (
          <Button variant="outline" size="sm" icon="assessment" className="min-h-9" onClick={() => onOpenFeedback(sessionId)}>
            {FEEDBACK_LABEL[data.evaluation_status]}
          </Button>
        )}
        <Button variant="outline" size="sm" icon="description" className="min-h-9" disabled title="Halaman transkrip segera hadir">
          Transkrip (segera hadir)
        </Button>
      </div>
    </section>
  )
}
