// Carte lead réutilisable (colonne kanban + aperçu DragOverlay).
// Présentation pure : aucune mutation, tout vient des props et de stages.js —
// SAUF la mini-popover « ✗ Perdu » (VX223), qui suit le même patron que
// CallLogPopover ci-dessous : un enfant auto-contenu appelle crmApi
// directement plutôt que de faire remonter une prop de mutation supplémentaire.
// VX187 — memo() : chaque frappe dans la recherche/un filtre re-rendait
// TOUTES les cartes visibles (zéro `memo(` dans tout le fichier). Ne tient
// que si les callbacks parents sont stables (voir useCallback sur
// onOpenLead/onAutoQuote/changeStage dans LeadsPage.jsx).
import { useEffect, useRef, useState, memo } from 'react'
// VX45 — emoji ⚡ fonctionnel remplacé par l'icône lucide (rendu variable
// selon l'OS avec un emoji brut).
import { Zap } from 'lucide-react'
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
import { telHref, waHref } from '../../../../lib/contactLinks'
// VX122 — finesse française : espace fine insécable devant « : » du tooltip.
import { nbsp } from '../../../../lib/format'
import crmApi from '../../../../api/crmApi'
import ExternalLink from '../../../../ui/ExternalLink'
// VX24 — score de qualité désormais aussi visible sur la carte (ex Liste seule).
// VX87 — nudge post-appel « Appel terminé — noter le résultat ? ».
import ScoreBadge from '../../../../features/crm/ScoreBadge'
import CallLogPopover, { useCallEndedNudge } from '../../../../features/crm/CallLogPopover'
import { Button, Popover, PopoverTrigger, PopoverContent } from '../../../../ui'

// VX43 — Swipe-to-action horizontal maison (touchstart/move/end, zéro
// dépendance). Les liens tel:/wa.me existaient déjà mais en texte 12px noyé
// dans la carte (kb-card-contact) — ici on les révèle en GRAND (≥44px) par un
// balayage vers la gauche, le geste iOS/Android attendu sur une liste de cartes.
//
// Seuil de distance anti-scroll : le geste ne s'engage QUE si le mouvement est
// nettement plus horizontal que vertical (sinon un swipe raté couperait le
// scroll vertical du kanban/de la liste). Fonctions pures locales (le test
// node en garde une copie exacte — un fichier de composant n'exporte que des
// composants, règle react-refresh).
const SWIPE_REVEAL_PX = 96 // largeur du panneau d'actions révélé

/** Le geste ne s'arme que si le mouvement est majoritairement horizontal
    (anti-scroll vertical) et dépasse un petit seuil d'intention (5px). */
function shouldArmSwipe(deltaX, deltaY) {
  if (Math.abs(deltaX) < 5) return false
  return Math.abs(deltaX) > Math.abs(deltaY)
}

/** Distance de traînée bornée à [-SWIPE_REVEAL_PX, 0] (on ne révèle que vers
    la gauche ; un balayage vers la droite ne fait rien — pas d'action là). */
function clampSwipeOffset(deltaX, maxReveal = SWIPE_REVEAL_PX) {
  return Math.max(-maxReveal, Math.min(0, deltaX))
}

/** Lâcher au-delà de la moitié du panneau → reste ouvert (aimanté) ; sinon
    referme (aimanté à 0). */
function resolveSwipeSnap(offset, maxReveal = SWIPE_REVEAL_PX) {
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

// VX223 — canal léger « focus au prochain ouvert », posé par le bouton
// « → Renseigner la facture » ci-dessous SANS ajouter de prop de navigation
// à travers LeadsPage.jsx/KanbanView.jsx (qui composent déjà `onOpen`) :
// LeadForm.jsx (même fichier de la tâche) consomme cette clé une fois puis la
// retire — jamais un focus fantôme sur un futur lead sans rapport.
const PENDING_FOCUS_KEY = 'taqinor.leadform.pendingFocus'
function requestFocusSection(leadId, section) {
  try {
    sessionStorage.setItem(PENDING_FOCUS_KEY, JSON.stringify({ leadId, section }))
  } catch { /* best-effort — sessionStorage indisponible (navigation privée…) */ }
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


function LeadCard({
  lead, busy = false, onOpen, onAutoQuote, users = [], onReassign,
  selected = false, onToggleSelect, onPlanifierRelance,
  // VX223 — notifié après un « ✗ Perdu » réussi (optionnel : le kanban se
  // resynchronise de toute façon à son prochain refetch périodique existant).
  onChanged,
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
  // VX24 — anatomie de carte à 2 niveaux : UNE seule pilule d'alerte
  // prioritaire au premier plan (perdu > rappel > expiré) au lieu d'empiler
  // jusqu'à 3 pilules en tête de carte. « Inactif N j » + horloge d'activité
  // sont relégués en pied de carte (kb-card-foot), discrets.
  const alertePill = perdu
    ? { key: 'perdu', label: 'Perdu', className: 'kb-badge-perdu' }
    : lead.contact_preference === 'phone_ok'
      ? {
          key: 'rappel', label: '☎ Rappel demandé',
          className: 'kb-badge-rappel rounded-full bg-info/15 px-1.5 py-0.5 text-info',
          title: 'Le client a demandé à être rappelé par téléphone',
        }
      : dernierDevisExpire
        ? {
            key: 'expire', label: 'Devis expiré',
            className: 'kb-badge-expire rounded-full bg-warning/15 px-1.5 py-0.5 text-warning',
            title: 'Le dernier devis du lead est expiré',
          }
        : null
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

  // VX87 — nudge post-appel : armé juste avant d'ouvrir tel:, proposé au
  // retour dans l'onglet (visibilitychange).
  const { nudgeVisible, armCallNudge, dismissNudge } = useCallEndedNudge()

  // VX223 — « ✗ Perdu » en 2 clics : (1) ouvrir la mini-popover, (2) choisir
  // un motif (datalist des motifs gérés, texte libre toléré) → confirmer, UNE
  // seule requête PATCH `perdu`+`motif_perte` (jamais deux, jamais le
  // formulaire complet). Motifs chargés paresseusement à la PREMIÈRE ouverture
  // (jamais à chaque montage de carte — un kanban a des dizaines de cartes).
  const [perduOpen, setPerduOpen] = useState(false)
  const [perduMotif, setPerduMotif] = useState('')
  const [perduBusy, setPerduBusy] = useState(false)
  const [motifsPerte, setMotifsPerte] = useState(null) // null = pas encore chargés
  useEffect(() => {
    if (!perduOpen || motifsPerte !== null) return
    crmApi.getMotifsPerte()
      .then((r) => setMotifsPerte(((r.data?.results ?? r.data) || []).filter((m) => !m.archived)))
      .catch(() => setMotifsPerte([]))
  }, [perduOpen, motifsPerte])
  const confirmPerdu = async () => {
    const motif = perduMotif.trim()
    if (!motif) return
    setPerduBusy(true)
    try {
      await crmApi.updateLead(lead.id, { perdu: true, motif_perte: motif })
      setPerduOpen(false)
      setPerduMotif('')
      onChanged?.()
    } catch {
      // best-effort — la carte se resynchronise au prochain refetch du kanban
    } finally {
      setPerduBusy(false)
    }
  }

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
              onClick={(e) => { e.stopPropagation(); swipe.close(); armCallNudge() }}
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
            <ExternalLink
              href={wa}
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
            </ExternalLink>
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
        {/* VX24 — ScoreBadge partagé (features/crm) ; VX221 — tooltip top-3 facteurs. */}
        <ScoreBadge lead={lead} />
        {/* VX24 — une seule pilule d'alerte prioritaire (perdu > rappel > expiré) */}
        {alertePill && (
          <span className={alertePill.className} title={alertePill.title}>
            {alertePill.label}
          </span>
        )}
        {/* VX223 — « ✗ Perdu » en 2 clics : mini-popover motif, jamais besoin
            d'ouvrir la fiche pour ce geste quotidien. Absent si déjà perdu. */}
        {!perdu && (
          <Popover
            open={perduOpen}
            onOpenChange={(v) => { setPerduOpen(v); if (!v) setPerduMotif('') }}
          >
            <PopoverTrigger asChild>
              <button
                type="button"
                className="kb-mark-perdu"
                title="Marquer perdu"
                aria-label={`Marquer ${nomComplet} comme perdu`}
                onPointerDown={(e) => e.stopPropagation()}
                onTouchStart={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  width: '20px', height: '20px', border: 'none', background: 'transparent',
                  color: 'var(--muted-foreground)', cursor: 'pointer', fontSize: '13px',
                  lineHeight: 1, padding: 0,
                }}
              >
                ✗
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '220px' }}>
                <p style={{ fontSize: '13px', fontWeight: 500, margin: 0 }}>Marquer perdu</p>
                <input
                  className="form-control"
                  list={`kb-motifs-${lead.id}`}
                  placeholder="Motif de perte"
                  value={perduMotif}
                  onChange={(e) => setPerduMotif(e.target.value)}
                  autoFocus
                />
                <datalist id={`kb-motifs-${lead.id}`}>
                  {(motifsPerte ?? []).map((m) => <option key={m.id} value={m.nom} />)}
                </datalist>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                  <Button type="button" variant="outline" size="sm" onClick={() => setPerduOpen(false)}>
                    Annuler
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={!perduMotif.trim() || perduBusy}
                    loading={perduBusy}
                    onClick={confirmPerdu}
                  >
                    Confirmer
                  </Button>
                </div>
              </div>
            </PopoverContent>
          </Popover>
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
          <Zap size={14} aria-hidden="true" />
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
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '11px', borderRadius: '9999px', padding: '1px 8px', background: 'var(--color-primary-muted, rgba(37,99,235,.12))', color: 'var(--color-primary, #2563eb)' }}
                  title="Toutes les données nécessaires sont réunies pour générer un devis en un clic">
              <Zap size={11} aria-hidden="true" /> Prêt à deviser en 1 clic
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
              onClick={(e) => { e.stopPropagation(); armCallNudge() }}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              ☎ {lead.telephone}
            </a>
          )}
          {wa && (
            <ExternalLink
              className="kb-card-wa"
              href={wa}
              title="Ouvrir WhatsApp"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              WhatsApp
            </ExternalLink>
          )}
        </div>
      )}

      {/* VX223 — texte inerte → bouton : ouvre la fiche ET fait défiler
          jusqu'à la section « Profil énergétique » (champ bloquant du devis
          auto), au lieu d'obliger à chercher soi-même où renseigner la
          facture. */}
      {factureManquante && (
        <button
          type="button"
          className="kb-card-facture-manquante mt-0.5 cursor-pointer border-0 bg-transparent p-0 text-left text-[11px] text-warning underline-offset-2 hover:underline"
          title={factureManquante}
          onPointerDown={(e) => e.stopPropagation()}
          onTouchStart={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation()
            requestFocusSection(lead.id, 'energie')
            onOpen?.(lead)
          }}
        >
          → Renseigner la facture
        </button>
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
          title={nbsp(`Priorité : ${PRIORITE_LABELS[lead.priorite] ?? PRIORITE_LABELS.normale}`)}
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
        {/* VX24 — « Inactif N j » relégué en pied de carte, discret (n'était
            plus une pilule de tête à côté de perdu/rappel/expiré). */}
        {inactif && (
          <span
            className="kb-foot-inactif text-[11px] text-muted-foreground"
            title={`Aucune modification depuis ${jInactif} jours`}
          >
            Inactif {jInactif} j
          </span>
        )}
        {/* VX24 — horloge d'activité reléguée au pied, même traitement discret. */}
        {lead.next_activity && (
          <span
            className={`kb-act-clock kb-foot-clock ${lead.next_activity.state}`}
            title={`Activité ${lead.next_activity.summary} — ${lead.next_activity.due_date}`}
          >
            ⏰
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

      {/* VX87 — nudge post-appel : proposé au retour dans l'onglet après un
          tap tel: (armCallNudge), jamais intrusif — dismissable, ne bloque
          rien. */}
      {nudgeVisible && (
        <div
          className="kb-call-nudge"
          role="status"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <span className="kb-call-nudge-text">Appel terminé — noter le résultat ?</span>
          <CallLogPopover
            leadId={lead.id}
            trigger={<button type="button" className="kb-call-nudge-log">Noter</button>}
            onLogged={dismissNudge}
          />
          <button
            type="button"
            className="kb-call-nudge-dismiss"
            aria-label="Ignorer"
            onClick={dismissNudge}
          >
            ✕
          </button>
        </div>
      )}
      </article>
    </div>
  )
}

export default memo(LeadCard)
