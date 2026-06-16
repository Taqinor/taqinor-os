// Carte chantier réutilisable (colonne kanban + aperçu DragOverlay).
// Présentation pure : aucune mutation, tout vient des props et de statuses.js.
// Même langage visuel que la carte lead (classes kb-*).
import {
  statusLabel,
  TYPE_LABELS,
} from '../../../features/installations/statuses'
import AssigneePicker from '../../../components/AssigneePicker'

const formatDateFr = (iso) => {
  if (!iso) return null
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

export default function ChantierCard({
  item, busy = false, onOpen, users = [], onReassign,
}) {
  const annule = Boolean(item.annule)
  const titre = item.client_nom || item.reference || '—'
  const sousTitre = item.site_ville || item.reference || ''
  const pose = formatDateFr(item.date_pose_prevue)
  const kwc = item.puissance_installee_kwc

  const classes = [
    'kb-card',
    annule ? 'kb-card-perdu' : '',
    busy ? 'kb-card-busy' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <article
      className={classes}
      onClick={onOpen ? () => onOpen(item) : undefined}
    >
      <div className="kb-card-head">
        <span className="kb-card-name">{titre}</span>
        {annule && <span className="kb-badge-perdu">Annulé</span>}
      </div>

      {sousTitre && <div className="kb-card-sub">{sousTitre}</div>}

      <div className="kb-card-sub">
        {statusLabel(item.statut)}
        {item.type_installation && (
          <> · {TYPE_LABELS[item.type_installation] ?? item.type_installation}</>
        )}
      </div>

      <div className="kb-card-foot">
        {kwc != null && kwc !== '' && (
          <span className="kb-canal">{kwc} kWc</span>
        )}
        {pose && (
          <span className="kb-relance" title="Pose prévue">📅 {pose}</span>
        )}
        <span
          className="kb-card-assignee"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
        >
          <AssigneePicker
            users={users}
            value={item.technicien_responsable ?? ''}
            onChange={(uid) => onReassign?.(item, uid)}
            size={24}
            compact
            disabled={!onReassign}
          />
        </span>
      </div>
    </article>
  )
}
