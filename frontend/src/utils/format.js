/** Durasi dalam bahasa Indonesia: "0 menit", "kurang dari 1 menit", "45 menit", "2 jam 5 menit". */
export function formatDuration(seconds) {
  if (seconds > 0 && seconds < 60) return 'kurang dari 1 menit'
  const minutes = Math.floor((seconds || 0) / 60)
  if (minutes < 60) return `${minutes} menit`
  const rest = minutes % 60
  return `${Math.floor(minutes / 60)} jam${rest ? ` ${rest} menit` : ''}`
}

const dateTime = new Intl.DateTimeFormat('id-ID', {
  timeZone: 'Asia/Jakarta',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

/** Tanggal dan jam di zona Asia/Jakarta. */
export const formatDateTime = (value) => `${dateTime.format(new Date(value))} WIB`
