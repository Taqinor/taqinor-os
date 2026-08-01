// Carte lead réutilisable (colonne kanban + aperçu DragOverlay).
// LB13 — anatomie à 4 zones (blueprint D3) : nom → valeur → UNE ligne d'action
// → pied. Contrat DOM conservé (`article.kb-card`, `.kb-card-name`, e2e). Plus
// aucun style présentationnel inline sur la face de la carte : tout passe par
// des classes `.kb-card*` (index.css). Ce qui QUITTE la face : liens tel/WA
// permanents (→ actions rapides révélées au survol, permanentes sur
// `(hover:none)`), chips readiness (→ micro-icônes 12px tooltipées au pied),
// étoiles de priorité, « Inactif N j »+horloge (→ pill d'âge), tags plafonnés
// à 2 + « +N ».
//
// Présentation pure : aucune mutation directe — la mini-popover « ✗ Perdu »
// (VX223) passe par le callback stable `onMarkPerdu` (LB5, blueprint I2)
// plutôt que d'appeler crmApi en direct (bug recon2-03 #3).
// VX187/LB6 — memo() : chaque frappe dans la recherche/un filtre re-rendait
// TOUTES les cartes visibles. Ne tient que si les callbacks parents sont
// stables (useCallback sur onOpenLead/onAutoQuote/changeStage/… dans LeadsPage).
import { useRef, useState, memo } from 'react'
// VX45 — icônes lucide (rendu stable multi-OS, contrairement à un emoji brut).
import { Zap, MapPin, FileText, MoreHorizontal, Lock } from 'lucide-react'
import {
  CANAL_LABELS,
  PIPELINE_STAGES,
  TYPE_INSTALLATION_LABELS,
  formatMAD,
  isPerdu,
  latestDevisTotal,
  tagColor,
  tagList,
} from '../../../../features/crm/stages'
// LB14 — rampe « rotting » réutilisée TELLE QUELLE (module pur, testable node).
// Les seuils sont indexés sur l'ORDRE de PIPELINE_STAGES (jamais une clé
// d'étape en dur) — renommer une étape reste impossible sans passer par stages.js.
import { rottingLevel, thresholdsForIndex } from '../../../../features/crm/workspace/rotting'
import AssigneePicker from '../../../../components/AssigneePicker'
import { telHref, waHref } from '../../../../lib/contactLinks'
// VX122 — finesse française : espace fine insécable devant « : » du tooltip.
import { nbsp } from '../../../../lib/format'
import ExternalLink from '../../../../ui/ExternalLink'
// VX24 — score de qualité visible sur la carte (ex Liste seule).
// VX221 — tooltip top-3 facteurs.
import ScoreBadge from '../../../../features/crm/ScoreBadge'
// VX87 — nudge post-appel « Appel terminé — noter le résultat ? ».
import CallLogPopover, { useCallEndedNudge } from '../../../../features/crm/CallLogPopover'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../../../ui'
// LB15 — flux « Marquer perdu » partagé (fin de la triplication carte/liste).
import PerduPopover from '../PerduPopover'

// VX43 — Swipe-to-action horizontal maison (touchstart/move/end, zéro
// dépendance). Les liens tel:/wa.me sont révélés en GRAND (≥44px) par un
// balayage vers la gauche, le geste iOS/Android attendu sur une liste de cartes.
//
// VERROU D'AXE (physique tactile) — l'ancien seuil se RÉ-ÉVALUAIT à chaque
// touchmove (`|dx| ≥ 5 && |dx| > |dy|`) : pendant un scroll vertical, le bruit
// horizontal du pouce armait le geste dès qu'une frame passait sous ce seuil,
// la carte suivait ce bruit, et le relâchement l'aimantait toute seule à
// -96px. On décide donc l'axe UNE SEULE FOIS par geste, et la décision tient
// jusqu'au touchend. Fonctions pures locales (le test node en garde une copie
// exacte — un fichier de composant n'exporte que des composants, règle
// react-refresh).
const SWIPE_REVEAL_PX = 96 // largeur du panneau d'actions révélé
const AXIS_LOCK_PX = 10 // distance à laquelle l'axe du geste se décide
const SWIPE_ARM_PX = 12 // course horizontale FRANCHE exigée pour armer
const SWIPE_ARM_RATIO = 1.5 // ... et nettement plus horizontale que verticale

/** resolveAxisLock — verrou d'axe du geste, décidé UNE SEULE fois. Renvoie :
      'pending'  — trop tôt pour trancher (aucun axe n'a parcouru 10px) ;
      'rejected' — geste VERTICAL (|dy| ≥ |dx|) : le scroll de la colonne le
                   possède, plus rien ne pourra armer le swipe de ce geste ;
      'armed'    — geste franchement horizontal : le swipe prend la main.
    Le bruit horizontal du pouce pendant un scroll vertical retombe donc
    toujours sur 'rejected', et la carte ne bouge plus d'un pixel. */
function resolveAxisLock(deltaX, deltaY) {
  const dx = Math.abs(deltaX)
  const dy = Math.abs(deltaY)
  if (Math.max(dx, dy) < AXIS_LOCK_PX) return 'pending'
  if (dy >= dx) return 'rejected'
  return dx >= SWIPE_ARM_PX && dx > SWIPE_ARM_RATIO * dy ? 'armed' : 'pending'
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
  // `phase` — 'idle' (rien en cours) | 'dragging' (le doigt traîne la carte)
  // | 'snapping' (aimantation au relâchement, ou fermeture après un tap sur
  // une action révélée). La transition transform n'est RETIRÉE que pendant
  // 'dragging' : sinon la carte arrive 150ms derrière le pouce, exactement la
  // sensation de traîne constatée au toucher. 'idle' garde la valeur d'origine
  // — le desktop, qui ne produit aucun touchevent et reste donc toujours en
  // 'idle', est rigoureusement inchangé (y compris ses transitions de survol).
  const [phase, setPhase] = useState('idle')
  const start = useRef(null)
  // Verrou d'axe du geste EN COURS : 'pending' | 'rejected' | 'armed'.
  const axis = useRef('pending')

  const onTouchStart = (e) => {
    if (!enabled) return
    const t = e.touches?.[0]
    if (!t) return
    start.current = { x: t.clientX, y: t.clientY }
    axis.current = 'pending'
    setPhase('idle')
  }
  const onTouchMove = (e) => {
    if (!enabled || !start.current) return
    // Verrou posé sur le vertical : le geste appartient au scroll jusqu'au
    // bout — on ne ré-évalue plus rien, quel que soit le bruit du pouce.
    if (axis.current === 'rejected') return
    const t = e.touches?.[0]
    if (!t) return
    const deltaX = t.clientX - start.current.x
    const deltaY = t.clientY - start.current.y
    if (axis.current !== 'armed') {
      axis.current = resolveAxisLock(deltaX, deltaY)
      if (axis.current !== 'armed') return
    }
    setPhase('dragging')
    setOffset(clampSwipeOffset(deltaX))
  }
  const onTouchEnd = () => {
    if (!enabled) return
    start.current = null
    if (axis.current === 'armed') {
      axis.current = 'pending'
      setPhase('snapping')
      setOffset((prev) => resolveSwipeSnap(prev))
    }
  }
  const close = () => { setPhase('snapping'); setOffset(0) }

  return {
    offset,
    phase,
    close,
    handlers: { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel: onTouchEnd },
  }
}

// VX223 — canal léger « focus au prochain ouvert », posé par le lien
// « → Renseigner la facture » ci-dessous SANS ajouter de prop de navigation
// à travers LeadsPage.jsx/KanbanView.jsx : LeadForm.jsx consomme cette clé une
// fois puis la retire — jamais un focus fantôme sur un futur lead sans rapport.
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

// QX31 — Speed-to-lead : minutes écoulées depuis `date_creation` (timestamp
// ISO), ou null si absente/invalide. Composant présentation pure (pas de
// setInterval) : le libellé se recalcule à chaque rendu naturel de la carte
// (filtre, recherche, mise à jour du store après une action) — le board n'a
// AUCUN rafraîchissement périodique, le libellé peut donc rester figé tant
// que rien ne re-rend la carte. C'est assumé : une précision à la minute ne
// vaut pas un timer par carte.
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

// Nombre de tags rendus « en clair » avant le repli « +N » (blueprint D3).
const TAGS_VISIBLE = 2

// APX2 — nombre de POINTS de tag rendus au repos avant le « +N » (les
// libellés en clair restent, révélés). 3 points tiennent en 3rem sur L3.
const TAG_DOTS_VISIBLE = 3

/* APX2 — LE BUDGET DE SIGNAUX (fondateur 2026-08-01, « we see a lot of leads
   at once »).
   ---------------------------------------------------------------------------
   La carte au repos tient en TROIS lignes ≤76 px. Le contrat LB13 « 4 zones »
   est explicitement REMPLACÉ : rien ne disparaît, tout se CONDENSE.

   La règle dure : la ligne d'action (précédence D3, inchangée) doit rester
   DISTINGUABLE SANS SURVOL. On ne peut donc pas simplement la cacher — son
   TEXTE part dans la zone révélée, mais son ÉTAT reste au repos sous forme
   d'une icône colorée sur L2, jamais supprimée. `signalFor` est la fonction
   pure qui traduit la ligne d'action en {tone, glyph, label} : une seule
   source pour le texte révélé ET l'icône au repos — impossible qu'ils
   divergent. */
const SIGNAL_TONES = {
  perdu: 'perdu',
  danger: 'danger',
  warning: 'warning',
  info: 'info',
  success: 'success',
  muted: 'muted',
}

/** signalFor — état condensé de la ligne d'action (même précédence que le
    rendu ci-dessous). Retourne null quand il n'y a RIEN à signaler. */
function signalFor({ perdu, relanceEnRetard, rappelDemande, dernierDevisExpire, nextActivityState, slaMinutes, factureManquante, action }) {
  if (perdu) return { tone: SIGNAL_TONES.perdu, glyph: '✗', label: 'Perdu' }
  if (relanceEnRetard) return { tone: SIGNAL_TONES.danger, glyph: '⚠', label: 'Relance en retard' }
  if (rappelDemande) return { tone: SIGNAL_TONES.info, glyph: '☎', label: 'Rappel demandé' }
  if (dernierDevisExpire) return { tone: SIGNAL_TONES.warning, glyph: '⌛', label: 'Devis expiré' }
  if (nextActivityState) {
    const tone = nextActivityState === 'overdue'
      ? SIGNAL_TONES.danger
      : nextActivityState === 'today' ? SIGNAL_TONES.warning : SIGNAL_TONES.success
    return { tone, glyph: '⏰', label: 'Activité planifiée' }
  }
  if (slaMinutes != null) {
    return {
      tone: slaMinutes >= 30 ? SIGNAL_TONES.danger : SIGNAL_TONES.warning,
      glyph: '⏱',
      label: 'À contacter — premier contact en attente',
    }
  }
  if (factureManquante) return { tone: SIGNAL_TONES.warning, glyph: '↯', label: 'Facture à renseigner' }
  if (action) return { tone: SIGNAL_TONES.muted, glyph: '→', label: action.label }
  return null
}

function LeadCard({
  lead, busy = false, onOpen, onAutoQuote, users = [], onReassign,
  selected = false, onToggleSelect, onPlanifierRelance,
  // LB5 — callback stable de LeadsPage (dispatch updateLead, store seul
  // source de vérité — jamais de refetch ni de crmApi direct depuis la carte).
  onMarkPerdu,
  // LB15 — action « Archiver » du menu ••• (optionnelle : masquée si non
  // câblée, ce qui est le cas du kanban/prévision aujourd'hui). Primitive/
  // callback stable — n'affecte pas la sonde mémo LB6.
  onArchive,
  // LB13 — quand une sélection est active ailleurs sur le board, la checkbox
  // reste visible sur TOUTES les cartes (comportement D3 : on ne cherche pas
  // la case au survol pendant qu'on constitue une sélection).
  // LB38 — la prop est enfin CÂBLÉE (KanbanView passe `selected.size > 0`) :
  // déclarée depuis LB13, elle valait toujours `false`, donc la règle
  // `.kb-card-selection-active .kb-card-check` d'index.css était morte et les
  // cartes non survolées cachaient encore leur case au desktop. Primitive
  // booléenne (jamais le `Set` entier) : memo(DraggableCard)/memo(LeadCard)
  // ne comparent qu'un booléen, la sonde LB6 reste verte.
  selectionActive = false,
}) {
  const perdu = isPerdu(lead)
  const tags = tagList(lead)
  const nomComplet =
    [lead.nom, lead.prenom].filter(Boolean).join(' ') || lead.societe || '—'
  // APX2 — L1 = « nom · société », les DEUX tronqués sur une seule ligne. La
  // société n'est rendue que si elle n'est pas déjà le nom affiché (cas d'un
  // lead sans nom de contact : `nomComplet` vaut alors déjà la société).
  const societeLabel = lead.societe && lead.societe !== nomComplet ? lead.societe : null
  const canal = CANAL_LABELS[lead.canal]
  const typeLabel = TYPE_INSTALLATION_LABELS[lead.type_installation] || null
  // Devis le plus récent (le serializer trie du plus récent au plus ancien).
  const dernierDevisExpire = lead.devis?.[0]?.statut === 'expire'

  // ── Zone VALEUR — total du dernier devis, sinon montant estimé (préfixe
  //    « est. ») ; rien si aucun des deux. XSAL7 : le devis prime l'estimation.
  const devisTotal = latestDevisTotal(lead)
  const estimeRaw =
    lead.montant_estime != null && lead.montant_estime !== ''
      ? parseFloat(lead.montant_estime)
      : null
  const valeur = devisTotal > 0
    ? { montant: formatMAD(devisTotal), estime: false }
    : (estimeRaw != null && Number.isFinite(estimeRaw))
      ? { montant: formatMAD(estimeRaw), estime: true }
      : null

  const tel = telHref(lead.telephone)
  const wa = waHref(lead.whatsapp)
  // QX31 — minuteur premier contact : uniquement en colonne NEW (dès que le
  // lead est contacté, son étape change et le minuteur disparaît de lui-même).
  const minutesNouveau = lead.stage === 'NEW' ? minutesDepuis(lead.date_creation) : null
  // ⚡ indisponible : on explique pourquoi (devis_auto.message).
  const factureManquante =
    lead.devis_auto && !lead.devis_auto.pret ? lead.devis_auto.message : null

  // QX28 — signaux de « préparation » captés par le site, désormais des
  // micro-icônes 12px tooltipées dans le pied (jamais un chip « manquant » —
  // seule l'absence du signal positif).
  const roofReady = !!lead.roof_point
  const factureReady = lead.facture_hiver != null && lead.facture_hiver !== ''
  const devisReady = !!lead.devis_auto?.pret

  // ── LB13/LB14 — pill d'âge (rotting) : ancienneté dans l'étape courante.
  //    Absorbe l'ancien « Inactif N j » + l'horloge. LB14 la teintera via
  //    data-rot (workspace/rotting.js) ; ici, valeur brute neutre.
  const ageJours =
    typeof lead.stage_since_days === 'number' && lead.stage_since_days >= 0
      ? lead.stage_since_days
      : null
  // LB14 — niveau de « rotting » (ok|warning|danger) selon l'ancienneté dans
  // l'étape courante. Jamais de rot sur un lead perdu, ni sur SIGNED/COLD
  // (thresholdsForIndex renvoie null → rottingLevel = 'ok').
  const rot = perdu
    ? 'ok'
    : rottingLevel(lead.stage_since_days, thresholdsForIndex(PIPELINE_STAGES.indexOf(lead.stage)))

  const relanceEnRetard = !perdu && !!lead.relance_date && isEnRetard(lead.relance_date)
  const rappelDemande = !perdu && lead.contact_preference === 'phone_ok'
  const action = prochaineAction(lead)

  // APX2 — l'icône colorée qui reste au repos, dérivée de la MÊME précédence
  // que la ligne d'action révélée (une seule source de vérité).
  const signal = signalFor({
    perdu,
    relanceEnRetard,
    rappelDemande,
    dernierDevisExpire,
    nextActivityState: lead.next_activity?.state ?? null,
    slaMinutes: minutesNouveau,
    factureManquante,
    action,
  })

  const classes = [
    'kb-card',
    // APX2 — modifieur de DENSITÉ propre à la carte LEAD. `.kb-card` est
    // partagé avec le kanban Installations et `ui/StatusAccentCard` : toutes
    // les règles de densité APX2 sont scopées ici pour ne JAMAIS bouger d'un
    // pixel une surface qui appartient à une autre lane.
    'kb-card--lead',
    perdu ? 'kb-card-perdu' : '',
    busy ? 'kb-card-busy' : '',
    selected ? 'kb-card-selected' : '',
    selectionActive ? 'kb-card-selection-active' : '',
  ]
    .filter(Boolean)
    .join(' ')

  // VX43 — le geste ne s'active que si au moins une action est disponible
  // (sinon rien à révéler derrière la carte).
  const swipe = useSwipeReveal(!!(tel || wa))

  // VX87 — nudge post-appel : armé juste avant d'ouvrir tel:, proposé au
  // retour dans l'onglet (visibilitychange).
  const { nudgeVisible, armCallNudge, dismissNudge } = useCallEndedNudge()

  // LB15 — le flux « ✗ Marquer perdu » (motif + datalist, chargement paresseux
  // des motifs, PATCH via le store) vit désormais dans PerduPopover.jsx
  // (partagé LeadCard/ListView). La carte n'en garde QUE l'état d'ouverture,
  // piloté par l'item « ✗ Marquer perdu » du menu •••.
  const [perduOpen, setPerduOpen] = useState(false)

  return (
    <div className="kb-swipe-wrap" style={{ position: 'relative' }}>
      {(tel || wa) && (
        <div
          className="kb-swipe-actions"
          aria-hidden={swipe.offset === 0}
          // LB17 — bande cachée réellement inerte : l'aria-hidden seul laissait
          // les <a> tabbables (recon-05). `inert` (React 19) les sort du tab
          // order ET de l'interaction tant que le panneau n'est pas révélé.
          inert={swipe.offset === 0}
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
                background: 'var(--success)', color: 'var(--success-foreground)',
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
                background: 'var(--brand-whatsapp)', color: 'var(--brand-whatsapp-foreground)',
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
        data-rot={rot}
        onClick={onOpen ? () => onOpen(lead) : undefined}
        {...swipe.handlers}
        style={{
          transform: swipe.offset ? `translateX(${swipe.offset}px)` : undefined,
          // Verrou d'axe : pendant la traîne du doigt, transform 1:1 SANS
          // transition ; la transition n'habille QUE l'aimantation finale.
          // Hors geste tactile ('idle'), la valeur d'origine est conservée —
          // le desktop ne change pas d'un pixel.
          transition: swipe.phase === 'dragging' ? 'none' : 'transform 150ms ease',
          position: 'relative',
        }}
      >
        {/* ── L1 / TÊTE : checkbox (révélée) · nom · société · menu (révélé) ──
            APX2 : le ScoreBadge a quitté la tête pour le micro-badge de L2 (le
            budget de signaux de la carte au repos vit sur UNE ligne). ── */}
        <div className="kb-card-head">
          {onToggleSelect && (
            // LB17 — cible tactile ≥44×44 via le label enveloppant (stylesheet,
            // jamais une taille inline) : tue le sliver 16px horizontal
            // (recon-05 touch) sans agrandir la case visuelle en pointeur fin.
            <label
              className="kb-check-hit"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              <input
                type="checkbox"
                className="kb-card-check"
                aria-label={`Sélectionner ${nomComplet}`}
                checked={selected}
                onChange={() => onToggleSelect(lead.id)}
              />
            </label>
          )}
          <span className="kb-card-name">{nomComplet}</span>
          {societeLabel && <span className="kb-card-societe">{societeLabel}</span>}
          {/* LB15 — menu ••• (révélé au survol/focus, permanent au toucher) :
              toutes les actions du lead, atteignables au clavier. Le bouton ✗
              20×20 a quitté la face (blueprint D3). */}
          <div className="kb-card-menu" onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="kb-card-menu-btn"
                  aria-label={`Actions du lead ${nomComplet}`}
                  onClick={(e) => e.stopPropagation()}
                  onPointerDown={(e) => e.stopPropagation()}
                  onTouchStart={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal size={16} aria-hidden="true" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                onClick={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
              >
                {onOpen && (
                  <DropdownMenuItem onSelect={() => onOpen(lead)}>Ouvrir</DropdownMenuItem>
                )}
                {onPlanifierRelance && (
                  <DropdownMenuItem onSelect={() => onPlanifierRelance(lead)}>
                    Planifier une relance
                  </DropdownMenuItem>
                )}
                {onAutoQuote && lead.devis_auto?.pret && (
                  <DropdownMenuItem onSelect={() => onAutoQuote(lead)}>
                    <Zap size={14} aria-hidden="true" /> Devis auto
                  </DropdownMenuItem>
                )}
                {!perdu && onMarkPerdu && (
                  <DropdownMenuItem
                    destructive
                    onSelect={() => {
                      // Ouverture différée d'un frame : la fermeture du menu ne
                      // referme pas aussitôt la popover contrôlée (LB15).
                      requestAnimationFrame(() => setPerduOpen(true))
                    }}
                  >
                    ✗ Marquer perdu
                  </DropdownMenuItem>
                )}
                {onArchive && (
                  <DropdownMenuItem onSelect={() => onArchive(lead)}>Archiver</DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {/* LB15 — popover « Marquer perdu » PARTAGÉE (contrôlée par le menu),
              ancrée au coin de la carte. Un seul composant perdu dans le code. */}
          {!perdu && onMarkPerdu && (
            <PerduPopover
              lead={lead}
              onMarkPerdu={onMarkPerdu}
              open={perduOpen}
              onOpenChange={setPerduOpen}
              anchor={<span className="kb-perdu-anchor" aria-hidden="true" />}
              idPrefix="kb-motifs"
            />
          )}
        </div>

        {/* ── L2 / VALEUR + BUDGET DE SIGNAUX (APX2) : montant `.num`, puis les
            trois signaux qui NE DISPARAISSENT JAMAIS au repos —
            (1) l'icône colorée de la ligne d'action (relance en retard / devis
                expiré / SLA… restent distinguables SANS survol),
            (2) le micro-badge de score (VX221, tooltip conservé),
            (3) la pastille « rotting » (rampe LB14, teintée par [data-rot]).
            La ligne est TOUJOURS rendue : c'est le socle du budget, même sans
            montant. Le chip « type d'installation » est passé dans la zone
            révélée (il condense, il ne disparaît pas). ── */}
        <div className="kb-card-value">
          {valeur && (
            <span
              className="kb-card-montant num"
              title={valeur.estime ? nbsp('Montant estimé (avant devis)') : nbsp('Total TTC du dernier devis')}
            >
              {valeur.estime ? 'est. ' : ''}{valeur.montant}
            </span>
          )}
          <span className="kb-card-signals">
            {signal && (
              <span
                className={`kb-card-signal kb-signal-${signal.tone}`}
                title={nbsp(signal.label)}
                aria-label={signal.label}
                role="img"
              >
                {signal.glyph}
              </span>
            )}
            {/* VX24 — ScoreBadge partagé (features/crm) ; VX221 — tooltip top-3 facteurs.
                APX2 : rendu en micro-badge (classe de taille sur l'enveloppe,
                le composant partagé reste intact — la sonde VX221 aussi). */}
            <span className="kb-card-score-micro">
              <ScoreBadge lead={lead} />
            </span>
            {/* LB14 — pastille de rotting : le liseré `[data-rot='danger']` et
                la pill d'âge existent déjà ; cette pastille rend le niveau
                lisible au repos même quand la pill d'âge est absente. */}
            {rot !== 'ok' && (
              <span
                className="kb-rot-dot"
                aria-label={rot === 'danger' ? 'Lead qui stagne' : 'Lead qui commence à traîner'}
                title={nbsp(rot === 'danger' ? 'Stagne dans cette étape' : 'Commence à traîner dans cette étape')}
                role="img"
              />
            )}
          </span>

          {/* ── APX7 — ACTIONS RAPIDES, SUR LA LIGNE DU MONTANT.
              Elles vivaient dans la zone révélée : au TOUCHER (`hover:none`)
              cette zone est permanente, ce qui ajoutait ~36 px par carte et ne
              laissait que ~3 cartes sur un 390×844. Elles remontent ici, sur
              L2 : au toucher la ligne du montant DEVIENT la rangée d'actions
              44×44 (téléphone ET tablette — jamais un seuil de largeur : c'est
              `hover:none` qui décide, donc l'iPad WebKit hérite exactement de
              l'anatomie du téléphone, VX68) ; en pointeur fin elles restent
              révélées au survol / au focus. UN SEUL exemplaire des liens
              tel/WhatsApp dans le DOM (contrat) — jamais un doublon tactile.
              Le RESTE (texte d'action, type, canal/ville, readiness, tags en
              clair) reste derrière le menu ••• et la fiche. ── */}
          <div className="kb-quick" aria-label="Actions rapides">
            {/* LB17 — PII masquée (le serializer nullifie tel/whatsapp sans la
                permission client_pii_voir, `lead.pii_masked`) : à la place des
                actions d'appel, un cadenas tooltipé — plus jamais un blanc muet. */}
            {lead.pii_masked ? (
              <span
                className="kb-quick-lock"
                title="Coordonnées masquées (permission PII)"
                aria-label="Coordonnées masquées (permission PII)"
              >
                <Lock size={12} aria-hidden="true" />
              </span>
            ) : (
              <>
                {tel && (
                  <a
                    className="kb-quick-btn kb-quick-tel"
                    href={tel}
                    title="Appeler"
                    aria-label={`Appeler ${nomComplet}`}
                    onClick={(e) => { e.stopPropagation(); armCallNudge() }}
                    onPointerDown={(e) => e.stopPropagation()}
                    onTouchStart={(e) => e.stopPropagation()}
                  >
                    ☎
                  </a>
                )}
                {wa && (
                  <ExternalLink
                    className="kb-quick-btn kb-quick-wa"
                    href={wa}
                    title="Ouvrir WhatsApp"
                    aria-label={`Ouvrir WhatsApp pour ${nomComplet}`}
                    onClick={(e) => e.stopPropagation()}
                    onPointerDown={(e) => e.stopPropagation()}
                    onTouchStart={(e) => e.stopPropagation()}
                  >
                    💬
                  </ExternalLink>
                )}
              </>
            )}
            {/* ⚡ Devis auto : révélé au survol en pointeur fin, mais MASQUÉ au
                toucher — il double l'item « Devis auto » du menu •••, et la
                ligne tactile ne garde que ce qui n'existe nulle part ailleurs
                (appeler / WhatsApp). */}
            <button
              type="button"
              className="kb-flash kb-quick-btn"
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
            </button>
          </div>
        </div>

        {/* ── L3 / PIED (APX2) : tags en POINTS (3 + n) · pill d'âge · avatar 16.
            Les libellés de tags en clair, le canal/la ville et les micro-icônes
            de readiness ont rejoint la zone révélée — condensés, jamais
            supprimés. ── */}
        <div className="kb-card-foot">
          {tags.length > 0 && (
            <span className="kb-tag-dots" title={nbsp(tags.join(' · '))} aria-label={`Étiquettes : ${tags.join(', ')}`}>
              {tags.slice(0, TAG_DOTS_VISIBLE).map((tag) => (
                <span
                  key={tag}
                  className="kb-tag-dot"
                  style={{ background: tagColor(tag).bg }}
                  aria-hidden="true"
                />
              ))}
              {tags.length > TAG_DOTS_VISIBLE && (
                <span className="kb-tag-dots-more" aria-hidden="true">+{tags.length - TAG_DOTS_VISIBLE}</span>
              )}
            </span>
          )}
          {ageJours != null && (
            <span
              className="kb-age-pill"
              title={nbsp(
                rot === 'danger'
                  ? `Stagne dans cette étape depuis ${ageJours} jours — à relancer`
                  : rot === 'warning'
                    ? `Dans cette étape depuis ${ageJours} jours — commence à traîner`
                    : `Dans cette étape depuis ${ageJours} jour${ageJours > 1 ? 's' : ''}`,
              )}
            >
              {ageJours} j
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
              size={16}
              compact
              disabled={!onReassign}
            />
          </span>
        </div>

        {/* ── ZONE RÉVÉLÉE (APX2) — dépliée par `@media (hover:hover)` au survol
            ET par `:focus-within` (clavier, à TOUTE largeur, jamais par une
            largeur d'écran : l'iPad `hover:none` hérite de l'anatomie tactile
            APX7). Posée APRÈS les trois lignes de repos, donc la carte grandit
            vers le BAS et aucun contrôle révélé n'apparaît sous la position de
            repos du curseur. `:focus-within` DÉPLIE réellement le conteneur
            (max-height + opacity, JAMAIS `visibility: hidden` qui empêcherait
            le focus d'y entrer) : chaque contrôle révélé a une bounding box
            non nulle au moment où il reçoit le focus — l'anti-pattern
            « tabbable invisible » que LB17 a corrigé ne revient pas. ── */}
        <div className="kb-card-reveal">
          {typeLabel && <span className="kb-card-type">{typeLabel}</span>}

        {/* ── UNE ligne d'action — précédence D3 : perdu > relance en retard >
            ☎ rappel > devis expiré > next_activity > SLA premier-contact (NEW)
            > facture manquante > suggestion d'étape. Son ÉTAT est déjà sur L2
            (icône colorée) ; ici vit son TEXTE. ── */}
        {perdu ? (
          <div className="kb-card-actionline kb-actionline-perdu">Perdu</div>
        ) : relanceEnRetard ? (
          <div className="kb-card-actionline kb-actionline-danger" title={nbsp('Relance en retard')}>
            ⚠ Relance en retard — {formatDateFr(lead.relance_date)}
          </div>
        ) : rappelDemande ? (
          <div
            className="kb-card-actionline kb-actionline-info"
            title="Le client a demandé à être rappelé par téléphone"
          >
            ☎ Rappel demandé
          </div>
        ) : dernierDevisExpire ? (
          <div className="kb-card-actionline kb-actionline-warning" title="Le dernier devis du lead est expiré">
            Devis expiré
          </div>
        ) : lead.next_activity ? (
          <div
            className={`kb-card-actionline kb-actionline-activity kb-act-${lead.next_activity.state}`}
            title={nbsp(`Activité ${lead.next_activity.summary} — ${lead.next_activity.due_date}`)}
          >
            ⏰ {lead.next_activity.summary}
          </div>
        ) : minutesNouveau != null ? (
          // QX31 — sur une carte NEW non contactée, la ligne d'action EST le
          // badge SLA premier-contact (amber < 30 min, rouge ≥ 30 min).
          <div
            className={`kb-card-actionline kb-sla ${minutesNouveau >= 30 ? 'kb-actionline-danger' : 'kb-actionline-warning'}`}
            title="Temps écoulé depuis la création du lead — non encore contacté"
          >
            ⏱ À contacter — {formatDepuis(minutesNouveau)}, non contacté
          </div>
        ) : factureManquante ? (
          // VX223 — texte inerte → bouton : ouvre la fiche ET défile jusqu'à
          // « Profil énergétique » (champ bloquant du devis auto).
          <button
            type="button"
            className="kb-card-actionline kb-actionline-link kb-card-facture-manquante"
            title={nbsp(factureManquante)}
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
        ) : action ? (
          action.planifier && onPlanifierRelance ? (
            <button
              type="button"
              className="kb-card-actionline kb-actionline-link"
              onClick={(e) => { e.stopPropagation(); onPlanifierRelance(lead) }}
              onPointerDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
            >
              → {action.label}
            </button>
          ) : (
            <div className="kb-card-actionline kb-actionline-muted">→ {action.label}</div>
          )
        ) : null}

        {/* ── Tags EN CLAIR plafonnés à 2 + « +N » (révélés — les points de L3
            en sont la forme condensée). ── */}
        {tags.length > 0 && (
          <div className="kb-tags">
            {tags.slice(0, TAGS_VISIBLE).map((tag) => {
              const { bg, color } = tagColor(tag)
              return (
                <span key={tag} className="kb-tag" style={{ background: bg, color }}>
                  {tag}
                </span>
              )
            })}
            {tags.length > TAGS_VISIBLE && (
              <span className="kb-tag-more" title={tags.slice(TAGS_VISIBLE).join(', ')}>
                +{tags.length - TAGS_VISIBLE}
              </span>
            )}
          </div>
        )}

        {/* ── MÉTA révélée : canal · ville · readiness ── */}
        <div className="kb-card-meta">
          {(canal || lead.ville) && (
            <span className="kb-foot-meta">
              {[canal, lead.ville].filter(Boolean).join(' · ')}
            </span>
          )}
          {/* QX28 — readiness en micro-icônes 12px tooltipées (jamais un signal
              « manquant » — seule l'absence de l'icône positive). */}
          {(roofReady || factureReady || devisReady) && (
            <span className="kb-readi">
              {roofReady && (
                <span className="kb-readi-icon" title="Un repère GPS de toiture a été capturé (site ou 3D)" aria-label="Toit épinglé (GPS)">
                  <MapPin size={12} aria-hidden="true" />
                </span>
              )}
              {factureReady && (
                <span className="kb-readi-icon" title="Une facture d'électricité a été saisie" aria-label="Facture saisie">
                  <FileText size={12} aria-hidden="true" />
                </span>
              )}
              {devisReady && (
                <span className="kb-readi-icon kb-readi-devis" title="Toutes les données sont réunies pour générer un devis en un clic" aria-label="Prêt à deviser en 1 clic">
                  <Zap size={12} aria-hidden="true" />
                </span>
              )}
            </span>
          )}
        </div>

        </div>{/* /kb-card-reveal (APX2) */}

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
              // EZ1 — la relance déjà posée est TRANSMISE : le popover
              // l'affiche et exige un choix, il ne l'écrase plus en silence.
              relanceActuelle={lead.relance_date ?? null}
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
