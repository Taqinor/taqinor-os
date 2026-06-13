// Carte lead réutilisable (colonne kanban + aperçu DragOverlay).
// Présentation pure : aucune mutation, tout vient des props et de stages.js.
import {
  CANAL_LABELS,
  PRIORITE_LABELS,
  PRIORITE_STARS,
  initials,
  isPerdu,
  tagColor,
  tagList,
} from '../../../../features/crm/stages'

const formatDateFr = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR')

// Date locale du jour au format YYYY-MM-DD (comparaison de chaînes fiable).
const isEnRetard = (iso) => {
  const t = new Date()
  const aujourdhui = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  return iso < aujourdhui
}

export default function LeadCard({ lead, busy = false, onOpen, onAutoQuote }) {
  const perdu = isPerdu(lead)
  const tags = tagList(lead)
  const etoiles = PRIORITE_STARS[lead.priorite] ?? PRIORITE_STARS.normale
  const nomComplet =
    [lead.nom, lead.prenom].filter(Boolean).join(' ') || lead.societe || '—'
  const sousTitre = lead.ville || lead.telephone || ''
  const canal = CANAL_LABELS[lead.canal]
  const avatar = initials(lead.owner_nom)

  const classes = [
    'kb-card',
    perdu ? 'kb-card-perdu' : '',
    busy ? 'kb-card-busy' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <article
      className={classes}
      onClick={onOpen ? () => onOpen(lead) : undefined}
    >
      <div className="kb-card-head">
        <span className="kb-card-name">{nomComplet}</span>
        {perdu && <span className="kb-badge-perdu">Perdu</span>}
        <button
          type="button"
          className="kb-flash"
          title="Devis auto"
          aria-label="Devis auto"
          onPointerDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation()
            if (onAutoQuote) onAutoQuote(lead)
          }}
        >
          ⚡
        </button>
      </div>

      {sousTitre && <div className="kb-card-sub">{sousTitre}</div>}

      {tags.length > 0 && (
        <div className="kb-tags">
          {tags.map((tag) => {
            const { bg, color } = tagColor(tag)
            return (
              <span
                key={tag}
                className="kb-tag"
                style={{ background: bg, color }}
              >
                {tag}
              </span>
            )
          })}
        </div>
      )}

      <div className="kb-card-foot">
        {canal && <span className="kb-canal">{canal}</span>}
        <span
          className="kb-stars"
          title={`Priorité : ${PRIORITE_LABELS[lead.priorite] ?? PRIORITE_LABELS.normale}`}
        >
          {[0, 1].map((i) => (
            <span
              key={i}
              className={i < etoiles ? 'kb-star kb-star-on' : 'kb-star'}
            >
              ★
            </span>
          ))}
        </span>
        {lead.relance_date && (
          <span
            className={
              isEnRetard(lead.relance_date)
                ? 'kb-relance kb-relance-late'
                : 'kb-relance'
            }
            title="Date de relance"
          >
            📅 {formatDateFr(lead.relance_date)}
          </span>
        )}
        {avatar && (
          <span className="kb-avatar" title={lead.owner_nom}>
            {avatar}
          </span>
        )}
      </div>
    </article>
  )
}
