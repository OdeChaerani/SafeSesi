import { getRoleLabel } from '../../services/auth'
import Avatar from '../ui/Avatar'
import Badge from '../ui/Badge'
import RowMenu from './RowMenu'

const STATUS = {
  aktif: { label: 'Aktif', variant: 'success', icon: 'check_circle' },
  menunggu: { label: 'Menunggu', variant: 'warning', icon: 'schedule' },
  kedaluwarsa: { label: 'Kedaluwarsa', variant: 'danger', icon: 'error' },
}

const ROLE_ICONS = { student: 'school', lecturer: 'psychology', admin: 'admin_panel_settings' }

const COLUMNS = ['Pengguna', 'Role', 'NPM / NIP', 'Status', 'Kelas']
const SKELETON_ROWS = 12

function Truncated({ children, className = '' }) {
  return (
    <span className={`block truncate ${className}`} title={children}>
      {children}
    </span>
  )
}

function Identity({ user }) {
  if (user.role === 'lecturer') return <Truncated>{user.nip || '-'}</Truncated>
  if (user.role !== 'student') return <span className="text-slate-500">-</span>
  return (
    <>
      <Truncated>{user.npm || user.asal_institusi || '-'}</Truncated>
      {user.npm && user.asal_institusi && <Truncated className="text-slate-500">{user.asal_institusi}</Truncated>}
    </>
  )
}

/** rows undefined = sedang memuat pertama kali (kerangka setinggi baris asli). */
export default function UserTable({ rows, resultKey, highlightId, busyIds, actionsFor }) {
  return (
    <>
      <p className="sm:hidden px-4 pb-2 text-[11px] text-slate-600">Geser tabel ke samping untuk melihat kolom lain.</p>
      <div
        className="overflow-auto max-h-[calc(100vh-15rem)] min-h-60 rounded-b-2xl focus-visible:ring-2 focus-visible:ring-[#352f55] outline-none"
        tabIndex={0}
        role="region"
        aria-label="Tabel pengguna"
      >
        <table className="w-full min-w-[820px] table-fixed text-left text-xs" aria-busy={!rows}>
          <caption className="sr-only">Daftar pengguna SafeSesi</caption>
          <colgroup>
            <col className="w-[30%]" />
            <col className="w-[17%]" />
            <col className="w-[18%]" />
            <col className="w-[14%]" />
            <col className="w-[15%]" />
            <col className="w-16" />
          </colgroup>
          <thead>
            <tr>
              {COLUMNS.map((column) => (
                <th key={column} scope="col" className="sticky top-0 z-10 bg-slate-100 px-3 h-9 text-xs font-bold text-slate-700">
                  {column}
                </th>
              ))}
              <th scope="col" className="sticky top-0 z-10 bg-slate-100">
                <span className="sr-only">Aksi</span>
              </th>
            </tr>
          </thead>
          {!rows ? (
            <tbody>
              {Array.from({ length: SKELETON_ROWS }, (_, index) => (
                <tr key={index} className="h-12 border-t border-slate-100">
                  <td className="px-3">
                    <div className="flex items-center gap-3">
                      <span className="ss-skeleton w-8 h-8 rounded-full shrink-0" />
                      <span className="flex-1 space-y-1.5">
                        <span className="ss-skeleton block h-3 w-3/4 rounded" />
                        <span className="ss-skeleton block h-2.5 w-1/2 rounded" />
                      </span>
                    </div>
                  </td>
                  {COLUMNS.slice(1).map((column) => (
                    <td key={column} className="px-3">
                      <span className="ss-skeleton block h-3 w-2/3 rounded" />
                    </td>
                  ))}
                  <td />
                </tr>
              ))}
            </tbody>
          ) : (
            <tbody key={resultKey} className="ss-fade-in">
              {rows.map((user) => {
                const status = STATUS[user.status]
                const actions = actionsFor(user)
                const classes = user.classes.join(', ')
                return (
                  <tr
                    key={user.id}
                    className={`h-12 border-t border-slate-100 even:bg-slate-50/60 hover:bg-[#f0f3ff] focus-within:bg-[#f0f3ff] transition-colors ${
                      user.id === highlightId ? 'ss-flash' : ''
                    }`}
                  >
                    <td className="px-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <Avatar name={user.name} />
                        <div className="min-w-0 leading-tight">
                          <Truncated className="font-bold text-[#1e1a34]">{user.name}</Truncated>
                          <Truncated className="text-[11px] text-slate-600">{user.email}</Truncated>
                        </div>
                      </div>
                    </td>
                    <td className="px-3">
                      <Badge variant="neutral" icon={ROLE_ICONS[user.role]} className="!text-slate-700">
                        {getRoleLabel(user.role)}
                      </Badge>
                    </td>
                    <td className="px-3 text-slate-800">
                      <Identity user={user} />
                    </td>
                    <td className="px-3">
                      <Badge variant={status.variant} icon={status.icon}>
                        {status.label}
                      </Badge>
                    </td>
                    <td className="px-3 text-slate-800">
                      {classes ? <Truncated>{classes}</Truncated> : <span className="text-slate-500">-</span>}
                    </td>
                    <td className="pr-2 text-right">
                      {actions.length > 0 && (
                        <RowMenu label={`Aksi untuk ${user.name}`} items={actions} busy={busyIds.includes(user.id)} />
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          )}
        </table>
      </div>
    </>
  )
}
