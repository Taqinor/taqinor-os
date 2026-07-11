// Carte lead réutilisable (colonne kanban + aperçu DragOverlay).
// Présentation pure : aucune mutation, tout vient des props et de stages.js.
import { useRef, useState } from 'react'
import {
  CANAL_LABELS,
  PRIORITE_LABELS,
  PRIORITE_STARS,
  formatMAD,
  isPerdu,
  tagColor,
  tagList,
} from '../../../../features/crm/stages'
import AssigneePicker from '../../../../components/AssigneePicker'

// VX43 — Swipe-to-action horizontal maison (touchstart/move/end, zéro
// dépendance). Les liens tel:/wa.me existaient déjà mais en texte 12px noyé
// dans la carte (kb-card-contact) — ici on les révèle en GRAND (≥44px) par un
// balayage vers la gauche, le geste iOS/Android attendu sur une liste de cartes.
//
// Seuil de distance anti-scroll : le geste ne s'engage QUE si le mouvement est
// nettement plus horizontal que vertical (sinon un swipe raté couperait le
// scroll vertical du kanban/de la liste). Fonctions pures exportées pour test.
export const SWIPE_REVEAL_PX = 96 // largeur du panneau d'actions révélé
export const SWIPE_OPEN_THRESHOLD = SWIPE_REVEAL_PX / 2

/** Le geste ne s'arme que si le mouvement est majoritairement horizontal
    (anti-scroll vertical) et dépasse un petit seuil d'intention (5px). */
export function shouldArmSwipe(deltaX, deltaY) {
  if (Math.abs(deltaX) < 5) return false
  return Math.abs(deltaX) > Math.abs(deltaY)
}

/** Distance de traînée bornée à [-SWIPE_REVEAL_PX, 0] (on ne révèle que vers
    la gauche ; un balayage vers la droite ne fait rien — pas d'action là). */
export function clampSwipeOffset(deltaX, maxReveal = SWIPE_REVEAL_PX) {
  return Math.max(-maxReveal, Math.min(0, deltaX))
}

/** Lâcher au-delà de la moitié du panneau → reste ouvert (aimanté) ; sinon
    referme (aimanté à 0). */
export function resolveSwipeSnap(offset, maxReveal = SWIPE_REVEAL_PX) {
  return Math.abs(offset) >= maxReveal / 2 ? -maxReveal : 0
}

/** Hook local : expose `offset` (px, ≤0) + les handlers tactiles à poser sur
    la carte. `enabled=false` (pas de tel/wa) désactive tout le geste. */
function useSwipeReveal(enabled) {
  const [offset, setOffset] = useState(0)
  const start = useRef(null)
  const armed = useRef(false)

  const onTouchStart = (e) => {
    if (!enabled) return
    const t = e.touches?.[0]
    if (!t) return
    start.current = { x: t.clientX, y: t.clientY }
    armed.current = false
  }
  const onTouchMove = (e) => {
    if (!enabled || !start.current) return
    const t = e.touches?.[0]
    if (!t) return
    const deltaX = t.clientX - start.current.x
    const deltaY = t.clientY - start.current.y
    if (!armed.current) {
      if (!shouldArmSwipe(deltaX, deltaY)) return
      armed.current = true
    }
    setOffset(clampSwipeOffset(deltaX))
  }
  const onTouchEnd = () => {
    if (!enabled) return
    start.current = null
    if (armed.current) {
      armed.current = false
      setOffset((prev) => resolveSwipeSnap(prev))
    }
  }
  const close = () => setOffset(0)

  return {
    offset,
    close,
    handlers: { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel: onTouchEnd },
  }
}

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

// QX31 — Speed-to-lead : minutes écoulées depuis `date_creation` (timestamp
// ISO), ou null si absente/invalide. Composant présentation pure (pas de
// setInterval) : le libellé se recalcule à chaque rendu naturel de la carte
// (le kanban re-rend déjà périodiquement via son polling/refetch existant).
const minutesDepuis = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const minutes = Math.floor((Date.now() - d.getTime()) / 60000)
  return minutes >= 0 ? minutes : null
}

// Libellé FR compact : « il y a 12 min », « il y a 2 h », « il y a 3 j ».
const formatDepuis = (minutes) => {
  if (minutes < 60) return `il y a ${minutes} min`
  const heures = Math.floor(minutes / 60)
  if (heures < 24) return `il y a ${heures} h`
  const jours = Math.floor(heures / 24)
  return `il y a ${jours} j`
}

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
  // QX31 — minuteur premier contact : uniquement en colonne NEW (dès que le
  // lead est contacté, son étape change et le minuteur disparaît de lui-même).
  const minutesNouveau = lead.stage === 'NEW' ? minutesDepuis(lead.date_creation) : null
  // ⚡ indisponible : on explique pourquoi (devis_auto.message).
  const factureManquante =
    lead.devis_auto && !lead.devis_auto.pret ? lead.devis_auto.message : null

  // QX28 — chips de « préparation » : ce que le site a déjà capturé pour ce
  // lead, invisible jusqu'ici (le vendeur ne pouvait pas distinguer un lead
  // riche en données d'un lead vide sans ouvrir la fiche).
  const roofReady = !!lead.roof_point
  const factureReady = lead.facture_hiver != null && lead.facture_hiver !== ''
  const devisReady = !!lead.devis_auto?.pret

  const classes = [
    'kb-card',
    perdu ? 'kb-card-perdu' : '',
    busy ? 'kb-card-busy' : '',
    selected ? 'kb-card-selected' : '',
  ]
    .filter(Boolean)
    .join(' ')

  // VX43 — le geste ne s'active que si au moins une action est disponible
  // (sinon rien à révéler derrière la carte).
  const swipe = useSwipeReveal(!!(tel || wa))

  return (
    <div className="kb-swipe-wrap" style={{ position: 'relative' }}>
      {(tel || wa) && (
        <div
          className="kb-swipe-actions"
          aria-hidden={swipe.offset === 0}
          style={{
            position: 'absolute', inset: 0, display: 'flex',
            justifyContent: 'flex-end', alignItems: 'stretch',
            overflow: 'hidden', borderRadius: 'var(--radius, 10px)',
          }}
        >
          {tel && (
            <a
              href={tel}
              aria-label="Appeler (glissement)"
              title="Appeler"
              onClick={(e) => { e.stopPropagation(); swipe.close() }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: `${SWIPE_REVEAL_PX / (tel && wa ? 2 : 1)}px`, minHeight: '44px',
                background: 'var(--color-success, #16a34a)', color: '#fff',
                fontSize: '18px', textDecoration: 'none',
              }}
            >
              ☎
            </a>
          )}
          {wa && (
            <a
              href={wa}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Ouvrir WhatsApp (glissement)"
              title="Ouvrir WhatsApp"
              onClick={(e) => { e.stopPropagation(); swipe.close() }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: `${SWIPE_REVEAL_PX / (tel && wa ? 2 : 1)}px`, minHeight: '44px',
                background: 'var(--color-info, #25D366)', color: '#fff',
                fontSize: '18px', textDecoration: 'none',
              }}
            >
              💬
            </a>
          )}
        </div>
      )}
      <article
        className={classes}
        onClick={onOpen ? () => onOpen(lead) : undefined}
        {...swipe.handlers}
        style={{
          transform: swipe.offset ? `translateX(${swipe.offset}px)` : undefined,
          transition: 'transform 150ms ease',
          position: 'relative',
        }}
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
          style={{ position: 'relative' }}
          disabled={!lead.devis_auto?.pret}
          title={lead.devis_auto?.pret
            ? (roofReady ? 'Devis auto — repère toit disponible' : 'Devis auto')
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
          {/* QX28 — badge le bouton quand un repère toit (GPS) existe : le
              devis auto peut s'appuyer sur des données réelles, pas estimées. */}
          {roofReady && (
            <span
              className="kb-flash-roof-badge"
              style={{
                position: 'absolute', top: '-2px', right: '-2px',
                width: '7px', height: '7px', borderRadius: '9999px',
                background: 'var(--color-success, #16a34a)',
              }}
              title="Repère toit (GPS) disponible"
              aria-hidden="true"
            />
          )}
        </button>
      </div>

      {sousTitre && <div className="kb-card-sub">{sousTitre}</div>}

      {/* QX31 — Speed-to-lead : minuteur premier contact sur les cartes NEW
          (« il y a 12 min, non contacté »). Disparaît dès que le lead change
          d'étape (il n'est alors plus dans la colonne NEW). */}
      {minutesNouveau != null && (
        <div
          className="kb-card-first-touch"
          style={{ fontSize: '11px', color: minutesNouveau >= 30 ? 'var(--color-destructive, #dc2626)' : 'var(--color-warning, #d97706)', fontWeight: 500 }}
          title="Temps écoulé depuis la création du lead — non encore contacté"
        >
          ⏱ {formatDepuis(minutesNouveau)}, non contacté
        </div>
      )}

      {/* QX28 — chips de préparation : ce que le site a déjà capturé. Visibles
          seulement pour les signaux réellement présents (jamais un chip
          "manquant" — juste l'absence du chip positif). */}
      {(roofReady || factureReady || devisReady) && (
        <div className="kb-readiness-chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '2px' }}>
          {roofReady && (
            <span className="kb-chip kb-chip-roof"
                  style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-success-muted, rgba(22,163,74,.12))', color: 'var(--color-success, #16a34a)' }}
                  title="Un repère GPS de toiture a été capturé (site ou 3D)">
              📍 Toit épinglé (GPS)
            </span>
          )}
          {factureReady && (
            <span className="kb-chip kb-chip-facture"
                  style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-info-muted, rgba(37,99,235,.12))', color: 'var(--color-info, #2563eb)' }}
                  title="Une facture d'électricité a été saisie">
              🧾 Facture saisie
            </span>
          )}
          {devisReady && (
            <span className="kb-chip kb-chip-devis"
                  style={{ fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-primary-muted, rgba(37,99,235,.12))', color: 'var(--color-primary, #2563eb)' }}
                  title="Toutes les données nécessaires sont réunies pour générer un devis en un clic">
              ⚡ Prêt à deviser en 1 clic
            </span>
          )}
        </div>
      )}

      {/* XSAL7 — montant estimé (pipeline pondéré pré-devis), affiché
          seulement quand présent ; le devis (s'il existe) prime ailleurs. */}
      {lead.montant_estime != null && lead.montant_estime !== '' && (
        <div className="kb-card-montant-estime" title="Montant estimé (avant devis)">
          ≈ {formatMAD(parseFloat(lead.montant_estime))}
        </div>
      )}

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
    </div>
  )
}
