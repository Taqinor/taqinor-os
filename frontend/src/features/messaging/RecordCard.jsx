import { useNavigate } from 'react-router-dom'
import { FileText, Users, HardHat } from 'lucide-react'

/* S19 — Carte d'enregistrement partagé dans une bulle. Un partage est un
   message normal portant un snapshot serveur (`shared_label`, `shared_url`) ou,
   pour un rendu local optimiste, un objet `record` { record_type, label,
   subtitle, link }. Cliquer ouvre l'enregistrement (navigation SPA quand l'URL
   est interne, sinon lien direct). */

const ICON = {
  lead: Users,
  devis: FileText,
  chantier: HardHat,
}

// Devine le type pour l'icône à partir du type explicite ou de l'URL.
function recordType(record) {
  if (record.record_type) return record.record_type
  const url = record.url || ''
  if (url.includes('/crm')) return 'lead'
  if (url.includes('/ventes/devis') || url.includes('/devis')) return 'devis'
  if (url.includes('/chantier')) return 'chantier'
  return null
}

export default function RecordCard({ record }) {
  const navigate = useNavigate()
  const r = record || {}
  const label = r.label || r.shared_label
  if (!label) return null
  const url = r.url || r.shared_url || r.link || ''
  const subtitle = r.subtitle
  const Icon = ICON[recordType(r)] || FileText

  const isInternal = url.startsWith('/')
  const open = (e) => {
    if (isInternal) {
      e.preventDefault()
      navigate(url)
    }
  }

  return (
    <a
      href={url || '#'}
      className="chat-record-card"
      onClick={open}
      data-testid="record-card"
    >
      <Icon size={15} aria-hidden="true" />
      <span className="chat-record-meta">
        <strong>{label}</strong>
        {subtitle && <span>{subtitle}</span>}
      </span>
    </a>
  )
}
