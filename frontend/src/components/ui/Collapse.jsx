/** Isi yang meluncur buka/tutup (CSS .ss-collapse); saat tertutup tidak bisa difokus atau dibaca. */
export default function Collapse({ open, id, children }) {
  return (
    <div id={id} className="ss-collapse" data-open={open} inert={!open}>
      <div>{children}</div>
    </div>
  )
}
