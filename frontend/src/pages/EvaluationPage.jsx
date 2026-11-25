import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { getEvaluation, requestEvaluation } from '../services/evaluations'
import { getSession } from '../services/sessions'

const POLL_MS = 3000
const SHORT_SESSION_S = 300
const LIMITED_SESSION_S = 600

const CODES = {
  GI: { name: 'Memberi informasi', info: 'Menyampaikan informasi atau penjelasan tanpa membujuk.' },
  P: { name: 'Membujuk', info: 'Memberi saran atau arahan tanpa meminta izin klien.' },
  PWP: { name: 'Membujuk dengan izin', info: 'Memberi saran setelah meminta izin klien.' },
  Q: { name: 'Pertanyaan', info: 'Semua pertanyaan, terbuka maupun tertutup.' },
  SR: { name: 'Refleksi sederhana', info: 'Mengulang ucapan klien dengan kata lain.' },
  CR: { name: 'Refleksi kompleks', info: 'Menangkap makna yang tersirat dari ucapan klien.' },
  AF: { name: 'Afirmasi', info: 'Menghargai usaha atau kekuatan klien.' },
  SEEK: { name: 'Mengajak kerja sama', info: 'Meminta pendapat klien atau mengajak berpikir bersama.' },
  EA: { name: 'Menegaskan otonomi', info: 'Menegaskan bahwa klien yang memutuskan.' },
  CONFRONT: { name: 'Konfrontasi', info: 'Menyalahkan, mengkritik, atau berdebat dengan klien.' },
}

const CODE_GROUPS = [
  { title: 'Refleksi', codes: ['SR', 'CR'] },
  { title: 'Pertanyaan', codes: ['Q'] },
  { title: 'Sejalan dengan MI', codes: ['AF', 'SEEK', 'EA'] },
  { title: 'Tidak sejalan dengan MI', codes: ['P', 'CONFRONT'] },
  { title: 'Lainnya', codes: ['GI', 'PWP'] },
]

const GLOBALS = {
  cultivating_change_talk: { name: 'Menumbuhkan Change Talk', info: 'Mengundang dan menguatkan ucapan klien yang mendukung perubahan.' },
  softening_sustain_talk: { name: 'Melunakkan Sustain Talk', info: 'Tidak ikut memperkuat alasan klien untuk tidak berubah.' },
  partnership: { name: 'Kemitraan', info: 'Memperlakukan klien sebagai mitra yang setara.' },
  empathy: { name: 'Empati', info: 'Berusaha memahami sudut pandang dan perasaan klien.' },
}

const PROCESSES = {
  engaging: { name: 'Engaging', icon: 'handshake', info: 'Membangun hubungan' },
  focusing: { name: 'Focusing', icon: 'center_focus_strong', info: 'Menentukan arah bersama' },
  evoking: { name: 'Evoking', icon: 'emoji_objects', info: 'Menggali alasan berubah' },
  planning: { name: 'Planning', icon: 'checklist', info: 'Menyusun langkah' },
}

const BANDS = {
  baik: { label: 'Baik', variant: 'success', icon: 'check_circle' },
  cukup: { label: 'Cukup', variant: 'warning', icon: 'remove_circle' },
  di_bawah_acuan: { label: 'Kurang', variant: 'danger', icon: 'arrow_downward' },
}

const TABS = [
  { id: 'ringkasan', label: 'Ringkasan', icon: 'dashboard' },
  { id: 'miti', label: 'Detail MITI', icon: 'bar_chart' },
  { id: 'transkrip', label: 'Transkrip', icon: 'forum' },
  { id: 'pengamatan', label: 'Pengamatan', icon: 'visibility' },
]

const num = (v) => v.toLocaleString('id-ID', { maximumFractionDigits: 2 })
const minutes = (s) => (s == null ? '-' : s < 60 ? `${s} detik` : `${Math.round(s / 60)} menit`)

// --- Komponen kecil -----------------------------------------------------------------------

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Angka dihitung naik dari 0 saat pertama tampil.
function CountUp({ value, format = num, duration = 700 }) {
  const [shown, setShown] = useState(() => (reducedMotion() ? value : 0))
  const frame = useRef(0)
  useEffect(() => {
    if (reducedMotion()) return undefined
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      setShown(value * (1 - (1 - t) ** 3))
      if (t < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [value, duration])
  return format(Number.isInteger(value) ? Math.round(shown) : Math.round(shown * 100) / 100)
}

function Card({ title, icon, action, children, className = '' }) {
  return (
    <section className={`ss-fade-up bg-white p-5 rounded-2xl shadow-xs border border-slate-100 flex flex-col gap-4 ${className}`}>
      {title && (
        <div className="flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm md:text-base font-bold text-[#1e1a34]">
            <span className="w-7 h-7 rounded-lg bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
              <span className="material-symbols-outlined text-[17px]">{icon}</span>
            </span>
            {title}
          </h2>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

function Hint({ children }) {
  return <p className="text-[11px] text-[#64748b] flex items-center gap-1"><span className="material-symbols-outlined text-[14px]">info</span>{children}</p>
}

function CodeChip({ code }) {
  const c = CODES[code]
  return (
    <span className="relative group inline-flex">
      <button type="button" className="cursor-help rounded-full transition-transform duration-150 hover:scale-110 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#f5b51b]" aria-label={`${code}: ${c.name}. ${c.info}`}>
        <Badge variant="primary">{code}</Badge>
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full mt-1 z-20 w-56 rounded-lg bg-[#1e1a34] text-white text-[11px] leading-snug px-2.5 py-1.5 shadow-lg opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0 transition-all duration-150"
      >
        <b>{c.name}</b> · {c.info}
      </span>
    </span>
  )
}

function BandBadge({ band }) {
  const b = BANDS[band]
  return b ? <Badge variant={b.variant} icon={b.icon}>{b.label}</Badge> : null
}

// Meteran satu nilai; garis kuning = ambang cukup dan baik.
function Meter({ value, min, max, thresholds, unit = '' }) {
  const pct = (v) => `${Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100))}%`
  return (
    <div className="flex flex-col gap-1">
      <div className="relative h-2 w-full bg-slate-100 rounded-full">
        {value != null && <div className="ss-grow-x h-full rounded-full bg-[#352f55]" style={{ width: pct(value) }} />}
        {thresholds &&
          ['cukup', 'baik'].map((k) => (
            <span key={k} className="absolute -top-1 h-4 w-0.5 bg-[#f5b51b] rounded-full -translate-x-1/2" style={{ left: pct(thresholds[k]) }} />
          ))}
      </div>
      {thresholds && (
        <span className="text-[10px] text-[#64748b]">
          Cukup ≥ {num(thresholds.cukup)}{unit} · Baik ≥ {num(thresholds.baik)}{unit}
        </span>
      )}
    </div>
  )
}

function Reason({ children, label = 'Lihat alasan' }) {
  return (
    <details className="group text-xs text-[#1e1a34]">
      <summary className="cursor-pointer list-none text-[#352f55] font-semibold flex items-center gap-0.5 select-none w-fit hover:text-[#1e1a34] transition-colors">
        <span className="material-symbols-outlined text-[16px] group-open:rotate-90 transition-transform">chevron_right</span>
        {label}
      </summary>
      <div className="ss-fade-in mt-2 leading-relaxed text-[#475569]">{children}</div>
    </details>
  )
}

function TurnTag({ n }) {
  return <span className="text-[10px] font-bold text-[#64748b] bg-slate-100 rounded-md px-1.5 py-0.5">Giliran {n}</span>
}

function EmptyNote({ icon, title, children }) {
  return (
    <div className="flex flex-col items-center text-center gap-2 py-8">
      <div className="w-11 h-11 rounded-xl bg-[#ede9fe] text-[#352f55] flex items-center justify-center">
        <span className="material-symbols-outlined text-[24px]">{icon}</span>
      </div>
      <h3 className="text-sm font-bold text-[#1e1a34]">{title}</h3>
      <p className="text-xs text-[#64748b] max-w-sm">{children}</p>
    </div>
  )
}

// --- Keadaan sebelum hasil tersedia --------------------------------------------------------

function StatusPanel({ evaluation, notFound, onRun, busy }) {
  if (notFound) {
    return (
      <Card>
        <EmptyNote icon="play_circle" title="Sesi ini belum dinilai">
          Jalankan evaluasi untuk melihat skor MITI dan umpan balik dari percakapanmu.
        </EmptyNote>
        <div className="flex justify-center -mt-4 pb-4">
          <Button icon={busy ? 'hourglass_top' : 'play_arrow'} onClick={onRun} disabled={busy}>{busy ? 'Memulai...' : 'Jalankan evaluasi'}</Button>
        </div>
      </Card>
    )
  }
  if (evaluation.status === 'running') {
    return (
      <Card>
        <div className="flex flex-col items-center text-center gap-2 py-8" role="status">
          <span className="material-symbols-outlined animate-spin text-[32px] text-[#352f55]">progress_activity</span>
          <h3 className="text-sm font-bold text-[#1e1a34]">Sedang dinilai</h3>
          <p className="text-xs text-[#64748b]">Biasanya butuh 1–2 menit. Halaman ini akan diperbarui sendiri.</p>
        </div>
      </Card>
    )
  }
  return (
    <Card>
      <div role="alert">
        <EmptyNote icon="error" title="Penilaian gagal">{evaluation.error_message || 'Terjadi kendala saat menilai.'}</EmptyNote>
      </div>
      <div className="flex justify-center -mt-4 pb-4">
        <Button icon={busy ? 'hourglass_top' : 'refresh'} onClick={onRun} disabled={busy}>{busy ? 'Memulai...' : 'Coba lagi'}</Button>
      </div>
    </Card>
  )
}

// --- Tab Ringkasan (b, c, d) ---------------------------------------------------------------

function SessionLimit({ seconds }) {
  if (seconds == null || seconds >= LIMITED_SESSION_S) return null
  const short = seconds <= SHORT_SESSION_S
  return (
    <div className="flex gap-3 items-start bg-amber-50 border border-amber-200/60 rounded-xl px-4 py-3">
      <span className="material-symbols-outlined text-amber-700 text-[20px]">schedule</span>
      <p className="text-xs md:text-sm text-amber-900">
        {short
          ? 'Sesimu kurang dari 5 menit, jadi yang dinilai hanya kode perilaku. Skor, umpan balik, dan pengamatan proses MI butuh percakapan yang lebih panjang.'
          : 'Sesimu kurang dari 10 menit. Skor tetap ditampilkan, tapi baca dengan hati-hati karena percakapannya masih pendek.'}
      </p>
    </div>
  )
}

function SummaryTile({ name, info, measure }) {
  return (
    <div className="ss-fade-up ss-lift bg-white p-4 rounded-2xl shadow-xs border border-slate-100 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-slate-500">{name}</h3>
          <p className="text-[11px] text-slate-400">{info}</p>
        </div>
        <BandBadge band={measure.reference_band} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold text-[#1e1a34]">{measure.value == null ? '–' : <CountUp value={measure.value} />}</span>
        <span className="text-xs text-slate-500">/ 5</span>
      </div>
      <Meter value={measure.value} min={1} max={5} thresholds={measure.reference_thresholds} />
    </div>
  )
}

function ScoreDots({ score }) {
  return (
    <div className="flex gap-1" aria-label={`Skor ${score} dari 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className="h-2 w-6 rounded-full bg-slate-100 overflow-hidden">
          {i <= score && <span className="ss-grow-x block h-full bg-[#352f55]" style={{ animationDelay: `${i * 90}ms` }} />}
        </span>
      ))}
    </div>
  )
}

function FeedbackColumn({ title, icon, tone, items, empty }) {
  return (
    <Card title={title} icon={icon}>
      {items.length === 0 && <p className="text-xs text-[#64748b]">{empty}</p>}
      <ul className="flex flex-col gap-3">
        {items.map((f, i) => (
          <li key={i} className="flex gap-2.5 items-start">
            <span className={`material-symbols-outlined text-[18px] mt-0.5 ${tone.icon}`}>{tone.bullet}</span>
            <div className="flex flex-col gap-1.5 min-w-0">
              <p className="text-sm text-[#1e1a34] leading-relaxed">{f.content}</p>
              <p className={`text-xs text-[#64748b] border-l-2 pl-2 ${tone.border}`}>
                <TurnTag n={f.turn_no} /> <span className="italic">“{f.excerpt}”</span>
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function SummaryTab({ session, evaluation, isShort }) {
  const sm = evaluation.summary_measures
  const s = session.scenario
  return (
    <>
      <Card title="Tentang sesi" icon="description">
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-[11px] font-semibold text-slate-500">Klien</dt>
            <dd className="text-[#1e1a34] font-semibold">{s.client_name}</dd>
            <dd className="text-xs text-[#64748b]">{s.client_age} tahun · {s.client_role}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold text-slate-500">Yang dinilai</dt>
            <dd className="text-[#1e1a34] font-semibold">Seluruh sesi</dd>
            <dd className="text-xs text-[#64748b]">{minutes(evaluation.assessed_duration_seconds)}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-semibold text-slate-500">Target perubahan</dt>
            <dd className="text-xs text-[#1e1a34] leading-relaxed">{s.change_target}</dd>
          </div>
        </dl>
        <SessionLimit seconds={evaluation.assessed_duration_seconds} />
      </Card>

      {!isShort && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            <SummaryTile name="Technical Global" info="Seberapa terarah percakapan pada perubahan" measure={sm.technical_global} />
            <SummaryTile name="Relational Global" info="Kualitas hubungan dalam percakapan MI" measure={sm.relational_global} />
          </div>

          <Card title="Empat skor global" icon="insights" action={<span className="text-[11px] text-[#64748b]">Skala 1–5, tidak dijumlahkan</span>}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {evaluation.global_scores.map((g) => (
                <div key={g.dimension} className="ss-lift border border-slate-100 rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-bold text-sm text-[#1e1a34]">{GLOBALS[g.dimension].name}</h3>
                    <span className="text-lg font-bold text-[#352f55]">{g.score}</span>
                  </div>
                  <ScoreDots score={g.score} />
                  <p className="text-[11px] text-[#64748b]">{GLOBALS[g.dimension].info}</p>
                  <Reason>
                    {g.reason}
                    <span className="block mt-1 text-[#64748b]">Lihat giliran {g.evidence_turn_nos.join(', ')}</span>
                  </Reason>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            <FeedbackColumn
              title="Kekuatan"
              icon="thumb_up"
              tone={{ bullet: 'check_circle', icon: 'text-emerald-600', border: 'border-emerald-300' }}
              items={evaluation.feedback.filter((f) => f.kind === 'strength')}
              empty="Belum terlihat cukup bukti untuk kekuatan tertentu."
            />
            <FeedbackColumn
              title="Bisa dikembangkan"
              icon="trending_up"
              tone={{ bullet: 'arrow_upward', icon: 'text-amber-600', border: 'border-amber-300' }}
              items={evaluation.feedback.filter((f) => f.kind === 'improvement')}
              empty="Tidak ada hal yang menonjol untuk dikembangkan."
            />
          </div>
        </>
      )}

    </>
  )
}

// --- Tab Detail MITI (e, f) ----------------------------------------------------------------

function RatioTile({ name, info, measure, display, max, unit, zeroText }) {
  return (
    <div className="ss-fade-up ss-lift bg-white p-4 rounded-2xl shadow-xs border border-slate-100 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-slate-500">{name}</h3>
          <p className="text-[11px] text-slate-400">{info}</p>
        </div>
        <BandBadge band={measure.reference_band} />
      </div>
      <span className="text-3xl font-bold text-[#1e1a34]">{measure.value == null ? '–' : <CountUp value={measure.value} format={display} />}</span>
      {measure.value == null ? (
        <p className="text-[11px] text-[#64748b]">Tidak dapat dihitung. {zeroText}</p>
      ) : (
        <Meter value={measure.value} min={0} max={max} thresholds={measure.reference_thresholds} unit={unit} />
      )}
    </div>
  )
}

function CountTile({ name, info, measure }) {
  return (
    <div className="ss-fade-up ss-lift bg-white p-4 rounded-2xl shadow-xs border border-slate-100 flex flex-col gap-2">
      <h3 className="text-xs font-semibold text-slate-500">{name}</h3>
      <p className="text-[11px] text-slate-400 -mt-1.5">{info}</p>
      <span className="text-3xl font-bold text-[#1e1a34]"><CountUp value={measure.value} /></span>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(measure.counts).map(([code, n]) => (
          <span key={code} className="text-[10px] font-semibold text-slate-500 bg-slate-100 rounded-md px-1.5 py-0.5">{code} {n}</span>
        ))}
      </div>
    </div>
  )
}

function FrequencyChart({ frequencies }) {
  const max = Math.max(1, ...Object.values(frequencies))
  return (
    <Card title="Jumlah setiap kode" icon="bar_chart" action={<Hint>Arahkan kursor ke kode untuk artinya</Hint>}>
      <div className="flex flex-col gap-4">
        {CODE_GROUPS.map((g) => (
          <div key={g.title} className="flex flex-col gap-1.5">
            <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{g.title}</h3>
            {g.codes.map((code) => {
              const n = frequencies[code]
              return (
                <div key={code} className="grid grid-cols-[5.5rem_1fr_2rem] sm:grid-cols-[11rem_1fr_2rem] items-center gap-3">
                  <span className="flex items-center gap-2 min-w-0">
                    <CodeChip code={code} />
                    <span className="hidden sm:inline text-xs text-[#1e1a34] truncate">{CODES[code].name}</span>
                  </span>
                  <span className="h-3 bg-slate-50 rounded-r-md">
                    {n > 0 && (
                      <span className="ss-grow-x block h-full bg-[#352f55] rounded-r-md transition-colors hover:bg-[#f5b51b]" style={{ width: `${(n / max) * 100}%` }} title={`${CODES[code].name}: ${n}`} />
                    )}
                  </span>
                  <span className={`text-sm font-bold text-right ${n ? 'text-[#1e1a34]' : 'text-slate-300'}`}>{n}</span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </Card>
  )
}

function AlternativesCard({ evaluation, turns }) {
  const items = evaluation.feedback.filter((f) => f.kind === 'alternative_response')
  const codesOf = (n) => evaluation.codes_by_turn.find((t) => t.turn_no === n)?.codes || []
  const clientAfter = (n) => turns.find((t) => t.turn_no > n && t.speaker === 'client')
  return (
    <Card title="Contoh respons lain" icon="lightbulb" action={<Hint>Contoh untuk belajar, bukan satu-satunya jawaban benar</Hint>}>
      {items.length === 0 && <p className="text-xs text-[#64748b]">Belum ada contoh respons untuk sesi ini.</p>}
      {items.map((f, i) => {
        const client = clientAfter(f.turn_no)
        const codes = codesOf(f.turn_no)
        return (
          <div key={i} className="group/alt ss-lift border border-slate-100 rounded-xl p-4 flex flex-col gap-3">
            <div className="flex items-center gap-2 flex-wrap">
              <TurnTag n={f.turn_no} />
              {codes.map((u) => <CodeChip key={u.unit_no} code={u.code} />)}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
              <div className="bg-slate-50 rounded-xl p-3">
                <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Ucapanmu</span>
                <p className="text-sm text-[#1e1a34] mt-1">“{f.excerpt}”</p>
                {client && <p className="text-xs text-[#64748b] mt-2">Klien: “{client.content}”</p>}
              </div>
              <span className="material-symbols-outlined self-center justify-self-center text-[#f5b51b] rotate-90 md:rotate-0 transition-transform md:group-hover/alt:translate-x-1">arrow_forward</span>
              <div className="bg-emerald-50 border border-emerald-200/60 rounded-xl p-3">
                <span className="text-[10px] font-bold uppercase tracking-wide text-emerald-700">Bisa dicoba</span>
                <p className="text-sm text-[#1e1a34] mt-1">“{f.content}”</p>
              </div>
            </div>
            {f.explanation && (
              <p className="flex gap-2 text-xs text-[#475569] leading-relaxed">
                <span className="material-symbols-outlined text-[16px] text-[#f5b51b]">tips_and_updates</span>
                <span>{f.explanation}</span>
              </p>
            )}
            {codes.length > 0 && (
              <Reason label="Kenapa diberi kode ini">
                <ul className="flex flex-col gap-1">
                  {codes.map((u) => <li key={u.unit_no}><b>{u.code}</b> · {u.reason}</li>)}
                </ul>
              </Reason>
            )}
          </div>
        )
      })}
    </Card>
  )
}

function MitiTab({ evaluation, turns, isShort }) {
  const sm = evaluation.summary_measures
  const cr = sm.pct_complex_reflection
  const rq = sm.reflection_question_ratio
  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <RatioTile name="Refleksi kompleks" info="Persen dari semua refleksi" measure={cr} display={(v) => `${num(v)}%`} max={100} unit="%" zeroText="Belum ada refleksi." />
        <RatioTile name="Refleksi : Pertanyaan" info="Refleksi untuk tiap pertanyaan" measure={rq} display={(v) => `${num(v)} : 1`} max={3} unit=" : 1" zeroText={`Ada ${rq.counts.SR + rq.counts.CR} refleksi, tapi belum ada pertanyaan.`} />
        <CountTile name="Sejalan dengan MI" info="Total MIA" measure={sm.total_mia} />
        <CountTile name="Tidak sejalan dengan MI" info="Total MINA" measure={sm.total_mina} />
      </div>
      <Hint>Tanda kuning pada garis adalah acuan dari MITI. Acuan ini bahan belajar, bukan penentu lulus.</Hint>
      <FrequencyChart frequencies={evaluation.frequencies} />
      {!isShort && <AlternativesCard evaluation={evaluation} turns={turns} />}
    </>
  )
}

// --- Tab Transkrip (g) ---------------------------------------------------------------------

function TranscriptTab({ evaluation, turns }) {
  const codesByTurn = Object.fromEntries(evaluation.codes_by_turn.map((t) => [t.turn_no, t.codes]))
  return (
    <Card title="Transkrip dengan kode" icon="forum" action={<Hint>Arahkan kursor ke kode untuk artinya</Hint>}>
      <ol className="flex flex-col gap-3">
        {turns.map((t, idx) => {
          const enter = { animationDelay: `${Math.min(idx * 40, 600)}ms` }
          if (t.speaker !== 'counselor') {
            return (
              <li key={t.turn_no} style={enter} className="ss-fade-up self-end max-w-[85%] bg-slate-50 rounded-2xl rounded-tr-sm px-4 py-2.5">
                <span className="text-[10px] font-bold text-slate-400">Klien · {t.turn_no}</span>
                <p className="text-sm text-[#475569]">{t.content}</p>
              </li>
            )
          }
          const codes = codesByTurn[t.turn_no] || []
          return (
            <li key={t.turn_no} style={enter} className="ss-fade-up self-start max-w-[85%] bg-[#ede9fe]/60 rounded-2xl rounded-tl-sm px-4 py-2.5 flex flex-col gap-2">
              <span className="text-[10px] font-bold text-[#352f55]">Kamu · {t.turn_no}</span>
              <p className="text-sm text-[#1e1a34]">{t.content}</p>
              {codes.length > 0 ? (
                <>
                  <div className="flex flex-wrap gap-1.5">{codes.map((u) => <CodeChip key={u.unit_no} code={u.code} />)}</div>
                  <Reason>
                    <ul className="flex flex-col gap-1.5">
                      {codes.map((u) => (
                        <li key={u.unit_no}>
                          <b>{u.code}</b> · <i>“{u.excerpt}”</i> — {u.reason}
                          {u.uncertainty_note && <span className="block text-amber-800">Catatan: {u.uncertainty_note}</span>}
                        </li>
                      ))}
                    </ul>
                  </Reason>
                </>
              ) : (
                <span className="text-[11px] text-[#64748b]">Tidak diberi kode</span>
              )}
            </li>
          )
        })}
      </ol>
    </Card>
  )
}

// --- Tab Pengamatan (h, i) -----------------------------------------------------------------

function ObservationTab({ processes, isShort }) {
  const byName = Object.fromEntries(processes.map((p) => [p.process, p]))
  return (
    <>
      <Card title="Proses MI yang terlihat" icon="route" action={<Hint>Tanpa skor, bukan tahap wajib</Hint>}>
        {isShort ? (
          <EmptyNote icon="schedule" title="Tidak diamati">Sesi kurang dari 5 menit terlalu pendek untuk mengamati proses MI.</EmptyNote>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {Object.entries(PROCESSES).map(([key, meta]) => {
              const p = byName[key]
              const seen = p?.evidence_found
              return (
                <div key={key} className={`ss-lift rounded-xl p-4 flex flex-col gap-2 border ${seen ? 'border-[#352f55]/20 bg-[#ede9fe]/40' : 'border-dashed border-slate-200'}`}>
                  <span className={`w-9 h-9 rounded-lg flex items-center justify-center ${seen ? 'bg-[#352f55] text-white' : 'bg-slate-100 text-slate-400'}`}>
                    <span className="material-symbols-outlined text-[20px]">{meta.icon}</span>
                  </span>
                  <div>
                    <h3 className="font-bold text-sm text-[#1e1a34]">{meta.name}</h3>
                    <p className="text-[11px] text-[#64748b]">{meta.info}</p>
                  </div>
                  {seen ? (
                    <>
                      <span className="text-xs font-semibold text-[#352f55]">Terlihat di giliran {p.start_turn_no}–{p.end_turn_no}</span>
                      <Reason>
                        {p.reason}
                        {p.excerpt && <span className="block mt-1 italic">{p.excerpt}</span>}
                      </Reason>
                    </>
                  ) : (
                    <span className="text-xs text-slate-500">Belum cukup bukti</span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>
      <Card title="Pengamatan vokal dan ekspresi wajah" icon="graphic_eq">
        <EmptyNote icon="hourglass_empty" title="Belum tersedia">Fitur ini sedang dikembangkan.</EmptyNote>
      </Card>
    </>
  )
}

// --- Halaman ------------------------------------------------------------------------------

export default function EvaluationPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [evaluation, setEvaluation] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('ringkasan')

  const loadEvaluation = useCallback(
    () =>
      getEvaluation(sessionId)
        .then((data) => {
          setEvaluation(data)
          setNotFound(false)
        })
        .catch((err) => {
          // 404 "Evaluasi ... belum dibuat" = belum dijalankan; 404 lain = sesi tidak ada.
          if (err.status === 404 && err.message.startsWith('Evaluasi')) setNotFound(true)
          else setLoadError(err.message)
        }),
    [sessionId],
  )

  useEffect(() => {
    getSession(sessionId)
      .then(setSession)
      .catch((err) => setLoadError(err.message))
    loadEvaluation()
  }, [sessionId, loadEvaluation])

  useEffect(() => {
    if (evaluation?.status !== 'running') return undefined
    const timer = setTimeout(loadEvaluation, POLL_MS)
    return () => clearTimeout(timer)
  }, [evaluation, loadEvaluation])

  const handleRun = async () => {
    setBusy(true)
    try {
      const started = await requestEvaluation(sessionId)
      setNotFound(false)
      // POST hanya mengirim status; detail hasil selalu diambil lewat GET.
      if (started.status === 'completed') await loadEvaluation()
      else setEvaluation(started)
    } catch (err) {
      setLoadError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const ready = session && evaluation?.status === 'completed'
  const seconds = evaluation?.assessed_duration_seconds ?? session?.duration_seconds
  const isShort = ready && seconds != null && seconds <= SHORT_SESSION_S

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#f5b51b]" />
            <span className="text-[11px] text-[#d3daea] font-medium tracking-wide">Hasil Evaluasi</span>
          </div>
          <h1 className="text-xl md:text-2xl text-white tracking-tight font-bold">{session ? session.scenario.title : 'Memuat sesi...'}</h1>
          {session && (
            <div className="flex flex-wrap gap-2 mt-1">
              <span className="text-[11px] text-white bg-white/10 rounded-full px-2.5 py-0.5 flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">person</span>{session.scenario.client_name}
              </span>
              <span className="text-[11px] text-white bg-white/10 rounded-full px-2.5 py-0.5 flex items-center gap-1">
                <span className="material-symbols-outlined text-[14px]">timer</span>{minutes(session.duration_seconds)}
              </span>
            </div>
          )}
        </div>
        <Button variant="outline" size="sm" icon="arrow_back" onClick={() => navigate('/latihan-mandiri')} className="self-start md:self-auto">
          Kembali
        </Button>
      </div>

      {loadError && (
        <Card>
          <div role="alert"><EmptyNote icon="error" title="Data tidak dapat dimuat">{loadError}</EmptyNote></div>
        </Card>
      )}

      {!loadError && !ready && (notFound || evaluation) && (
        <StatusPanel evaluation={evaluation} notFound={notFound} onRun={handleRun} busy={busy} />
      )}

      {!loadError && !ready && !notFound && !evaluation && (
        <p className="text-sm text-white/80" role="status">Memuat hasil evaluasi...</p>
      )}

      {ready && (
        <>
          <nav className="bg-white rounded-xl p-1 shadow-xs border border-slate-100 flex gap-1 overflow-x-auto" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`flex-1 min-w-max inline-flex items-center justify-center gap-1.5 text-xs md:text-sm font-bold px-3 py-2 rounded-lg transition-all duration-200 active:scale-95 ${
                  tab === t.id ? 'bg-[#352f55] text-white' : 'text-[#352f55] hover:bg-slate-100'
                }`}
              >
                <span className="material-symbols-outlined text-[16px]">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>

          <div key={tab} className="flex flex-col gap-5">
          {tab === 'ringkasan' && <SummaryTab session={session} evaluation={evaluation} isShort={isShort} />}
          {tab === 'miti' && <MitiTab evaluation={evaluation} turns={session.turns} isShort={isShort} />}
          {tab === 'transkrip' && <TranscriptTab evaluation={evaluation} turns={session.turns} />}
          {tab === 'pengamatan' && <ObservationTab processes={evaluation.processes} isShort={isShort} />}
          </div>
        </>
      )}
    </div>
  )
}
