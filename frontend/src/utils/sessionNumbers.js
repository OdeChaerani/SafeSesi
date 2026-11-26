/** Memberi nomor urut (tertua = 1) pada daftar sesi yang terurut terbaru dulu, beserta nomor sesi induknya. */
export function numberSessions(newestFirst) {
  const numbers = new Map(newestFirst.map((item, index) => [item.id, newestFirst.length - index]))
  return newestFirst.map((item) => ({
    ...item,
    number: numbers.get(item.id),
    parentNumber: numbers.get(item.parent_session_id),
  }))
}
