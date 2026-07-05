// Carte lead réutilisable (colonne kanban + aperçu DragOverlay).
// Présentation pure : aucune mutation, tout vient des props et de stages.js.
import {
  CANAL_LABELS,
  PRIORITE_LABELS,
  PRIORITE_STARS,
  isPerdu,
  tagColor,
  tagList,
} from '../../../../features/crm/stages'
import AssigneePicker from '../../../../components/AssigneePicker'

const formatDateFr = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR')

// Date locale du jour au format YYYY-MM-DD (comparaison de chaînes fiable).
const isEnRetard = (iso) => {
  const t = new Date()
  const aujourdhui = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  return iso < aujourdhui
}

// Seuil d'inactivité (jours sans modification) au-delà duquel on alerte.
const INACTIF_JOURS = 14

// Nombre de jours entiers écoulés depuis `date_modification` (timestamp ISO),
// ou null si la date est absente/invalide.
const joursInactif = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const jours = Math.floor((Date.now() - d.getTime()) / 86400000)
  return jours >= 0 ? jours : null
}

// Action suggérée selon l'étape du lead (libellé + indice « cliquable »).
// QUOTE_SENT/FOLLOW_UP sans relance → invite à planifier une relance.
const prochaineAction = (lead) => {
  const stage = lead?.stage
  if (stage === 'NEW') return { label: 'À contacter', planifier: false }
  if (stage === 'CONTACTED') return { label: 'Envoyer un devis', planifier: false }
  if ((stage === 'QUOTE_SENT' || stage === 'FOLLOW_UP') && !lead?.relance_date) {
    return { label: 'Planifier une relance', planifier: true }
  }
  return null
}

// Numéro de téléphone nettoyé pour un lien tel: / wa.me (chiffres et + initial).
const telHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}
const waHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const digits = s.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}` : null
}

export default function LeadCard({
  lead, busy = false, onOpen, onAutoQuote, users = [], onReassign,
  selected = false, onToggleSelect, onPlanifierRelance,
}) {
  const perdu = isPerdu(lead)
  const tags = tagList(lead)
  const etoiles = PRIORITE_STARS[lead.priorite] ?? PRIORITE_STARS.normale
  const nomComplet =
    [lead.nom, lead.prenom].filter(Boolean).join(' ') || lead.societe || '—'
  const sousTitre = lead.ville || lead.telephone || ''
  const canal = CANAL_LABELS[lead.canal]
  // Devis le plus récent (le serializer trie du plus récent au plus ancien).
  const dernierDevisExpire = lead.devis?.[0]?.statut === 'expire'
  const jInactif = joursInactif(lead.date_modification)
  const inactif = jInactif != null && jInactif >= INACTIF_JOURS && !perdu
  const action = prochaineAction(lead)
  const tel = telHref(lead.telephone)
  const wa = waHref(lead.whatsapp)
  // ⚡ indisponible : on explique pourquoi (devis_auto.message).
  const factureManquante =
    lead.devis_auto && !lead.devis_auto.pret ? lead.devis_auto.message : null

  const classes = [
    'kb-card',
    perdu ? 'kb-card-perdu' : '',
    busy ? 'kb-card-busy' : '',
    selected ? 'kb-card-selected' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <article
      className={classes}
      onClick={onOpen ? () => onOpen(lead) : undefined}
    >
      <div className="kb-card-head">
        {onToggleSelect && (
          <input
            type="checkbox"
            className="kb-card-check"
            aria-label={`Sélectionner ${nomComplet}`}
            checked={selected}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
            onChange={() => onToggleSelect(lead.id)}
          />
        )}
        <span className="kb-card-name">{nomComplet}</span>
        {perdu && <span className="kb-badge-perdu">Perdu</span>}
        {lead.contact_preference === 'phone_ok' && (
          <span
            className="kb-badge-rappel rounded-full bg-info/15 px-1.5 py-0.5 text-info"
            title="Le client a demandé à être rappelé par téléphone"
          >
            ☎ Rappel demandé
          </span>
        )}
        {dernierDevisExpire && (
          <span
            className="kb-badge-expire rounded-full bg-warning/15 px-1.5 py-0.5 text-warning"
            title="Le dernier devis du lead est expiré"
          >
            Devis expiré
          </span>
        )}
        {inactif && (
          <span
            className="kb-badge-inactif rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground"
            title={`Aucune modification depuis ${jInactif} jours`}
          >
            Inactif {jInactif} j
          </span>
        )}
        {lead.next_activity && (
          <span
            className={`kb-act-clock ${lead.next_activity.state}`}
            title={`Activité ${lead.next_activity.summary} — ${lead.next_activity.due_date}`}
          >
            ⏰
          </span>
        )}
        <button
          type="button"
          className="kb-flash"
          disabled={!lead.devis_auto?.pret}
          title={lead.devis_auto?.pret
            ? 'Devis auto'
            : (lead.devis_auto?.message ?? 'Devis auto indisponible')}
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

      {(tel || wa) && (
        <div
          className="kb-card-contact"
          style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '2px' }}
        >
          {tel && (
            <a
              className="kb-card-tel"
              href={tel}
              title="Appeler"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              ☎ {lead.telephone}
            </a>
          )}
          {wa && (
            <a
              className="kb-card-wa"
              href={wa}
              target="_blank"
              rel="noopener noreferrer"
              title="Ouvrir WhatsApp"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              WhatsApp
            </a>
          )}
        </div>
      )}

      {factureManquante && (
        <div
          className="kb-card-facture-manquante mt-0.5 text-[11px] text-warning"
          title="Le devis auto (⚡) est désactivé tant qu'il manque des informations"
        >
          Facture manquante : {factureManquante}
        </div>
      )}

      {action && (
        action.planifier && onPlanifierRelance ? (
          <button
            type="button"
            className="kb-card-action kb-card-action-link mt-0.5 cursor-pointer border-0 bg-transparent p-0 text-left text-[11px] text-info"
            onClick={(e) => { e.stopPropagation(); onPlanifierRelance(lead) }}
            onPointerDown={(e) => e.stopPropagation()}
            onTouchStart={(e) => e.stopPropagation()}
          >
            → {action.label}
          </button>
        ) : (
          <div className="kb-card-action mt-0.5 text-[11px] text-muted-foreground">
            → {action.label}
          </div>
        )
      )}

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
        <span
          className="kb-card-assignee"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
        >
          <AssigneePicker
            users={users}
            value={lead.owner ?? ''}
            onChange={(id) => onReassign?.(lead, id)}
            size={24}
            compact
            disabled={!onReassign}
          />
        </span>
      </div>
    </article>
  )
}
