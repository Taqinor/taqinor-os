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
  // reste visible sur TOUTES les cartes (primitive stable — défaut false, non
  // câblé par le kanban aujourd'hui : la CSS révèle déjà la checkbox au survol/
  // focus/sélection de la carte elle-même).
  selectionActive = false,
}) {
  const perdu = isPerdu(lead)
  const tags = tagList(lead)
  const nomComplet =
    [lead.nom, lead.prenom].filter(Boolean).join(' ') || lead.societe || '—'
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

  const classes = [
    'kb-card',
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
          transition: 'transform 150ms ease',
          position: 'relative',
        }}
      >
        {/* ── TÊTE : checkbox (révélée) · nom · score · action perdu ── */}
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
          {/* VX24 — ScoreBadge partagé (features/crm) ; VX221 — tooltip top-3 facteurs. */}
          <ScoreBadge lead={lead} />
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

        {/* ── VALEUR : montant (devis sinon estimé) · type d'installation ── */}
        {(valeur || typeLabel) && (
          <div className="kb-card-value">
            {valeur && (
              <span
                className="kb-card-montant num"
                title={valeur.estime ? nbsp('Montant estimé (avant devis)') : nbsp('Total TTC du dernier devis')}
              >
                {valeur.estime ? 'est. ' : ''}{valeur.montant}
              </span>
            )}
            {typeLabel && <span className="kb-card-type">{typeLabel}</span>}
          </div>
        )}

        {/* ── UNE ligne d'action — précédence D3 : perdu > relance en retard >
            ☎ rappel > devis expiré > next_activity > SLA premier-contact (NEW)
            > facture manquante > suggestion d'étape. ── */}
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

        {/* ── Tags plafonnés à 2 + « +N » ── */}
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

        {/* ── PIED : canal · ville · readiness · pill d'âge · avatar ── */}
        <div className="kb-card-foot">
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
              size={24}
              compact
              disabled={!onReassign}
            />
          </span>
        </div>

        {/* ── Actions rapides révélées au survol (permanentes sur (hover:none))
            — tel / WhatsApp / ⚡ Devis auto. Les hrefs tel/wa restent toujours
            présents dans le DOM (contrat). LB15 ajoute ici le menu •••. ── */}
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
