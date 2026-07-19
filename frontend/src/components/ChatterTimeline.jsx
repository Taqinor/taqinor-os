/* VX23 — ChatterTimeline : battre le chatter d'Odoo, pas le sous-imiter.
   ----------------------------------------------------------------------------
   Remplace le journal texte plat historique de `LeadForm.jsx` (~1188-1206) par
   un composant réutilisable : regroupement par jour (« Aujourd'hui »/« Hier »/
   date), Avatar par entrée, notes manuelles visuellement distinctes (fond
   plein) des logs auto de champ (texte discret + icône crayon), pièces
   jointes récentes injectées dans le fil au lieu d'un onglet séparé.

   Présentation pure : aucune mutation, aucun appel réseau — tout vient des
   props (mêmes shapes que `historique` côté LeadForm et `AttachmentsPanel`).
   `entries` = tableau d'activités serveur (`crm.LeadActivity` et assimilés,
   même shape que l'endpoint `/crm/leads/<id>/historique/`).
   `attachments` (optionnel) = pièces jointes récentes (même shape que
   `recordsApi.getAttachments`) injectées dans le fil, triées avec le reste
   par date — pas un onglet séparé. */
import Avatar from './Avatar'
import { Pencil, Paperclip, Megaphone, Pin, PinOff } from 'lucide-react'

// FG30/QX27 — libellés FR du résultat d'un appel/e-mail journalisé (miroir de
// LeadActivity.OUTCOMES côté serveur, apps/crm/models.py). Rapatrié ici
// (déplacé hors de LeadForm.jsx) : ChatterTimeline est désormais la seule
// source de rendu du chatter.
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé (dev HMR only)
export const OUTCOME_LABELS = {
  '': null, joint: 'Joint', non_joint: 'Non joint', rappel: 'À rappeler',
  refuse: 'Refus', interesse: 'Intéressé',
}

// Logs automatiques de champ ('creation'/'modification') vs notes manuelles
// et événements métier — sert à la distinction visuelle discrète/pleine.
const AUTO_LOG_KINDS = new Set(['creation', 'modification'])

// NTMKT11 — Touches marketing (XMKT16, `crm.services.noter_touche_marketing`)
// s'écrivent en `kind='note'` — il n'existe PAS de `kind` dédié côté backend
// ni de FK vers la campagne/séquence sur `LeadActivity` (contrainte connue,
// suivie séparément). Le SEUL signal fiable et STABLE côté serveur est le
// format du texte, identique sur tous les points d'écriture
// (`apps/compta/services.py` : `f'Campagne « {campagne.nom} » envoyée'` /
// `... ouverte` / `... cliquée`, `f'Séquence « {sequence.nom} » ...'`) —
// jamais un heuristique inventé ici, une lecture directe du format réel.
const MARKETING_TOUCH_RE = /^(Campagne|Séquence) « (.+?) » /

// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé (testable au node)
export function parseMarketingTouch(body) {
  const m = body ? MARKETING_TOUCH_RE.exec(body) : null
  if (!m) return null
  return { type: m[1] === 'Campagne' ? 'campagne' : 'sequence', nom: m[2] }
}

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return new Date(iso).toLocaleDateString('fr-FR')
}

// Libellé de groupe jour : « Aujourd'hui » / « Hier » / date FR complète.
function dayLabel(iso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Date inconnue'
  const startOf = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const day = startOf(d)
  const today = startOf(new Date())
  const yesterday = startOf(new Date(today.getTime() - 86400000))
  if (day.getTime() === today.getTime()) return "Aujourd'hui"
  if (day.getTime() === yesterday.getTime()) return 'Hier'
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

// Fusionne activités + pièces jointes en une seule chronologie triée
// décroissante (la plus récente en premier), chacune taguée `__feedKind`.
function buildFeed(entries, attachments) {
  const acts = (entries ?? []).map((a) => ({ ...a, __feedKind: 'activity', __at: a.created_at }))
  const atts = (attachments ?? []).map((a) => ({ ...a, __feedKind: 'attachment', __at: a.created_at }))
  return [...acts, ...atts].sort((x, y) => new Date(y.__at) - new Date(x.__at))
}

// Regroupe une chronologie triée en sections { label, items[] } par jour,
// dans l'ordre déjà trié (aucun tri supplémentaire ici).
function groupByDay(feed) {
  const groups = []
  let current = null
  for (const item of feed) {
    const label = dayLabel(item.__at)
    if (!current || current.label !== label) {
      current = { label, items: [] }
      groups.push(current)
    }
    current.items.push(item)
  }
  return groups
}

function ActivityLine({ a, resolveMarketingLink }) {
  if (a.kind === 'note') {
    // NTMKT11 — touche marketing (campagne/séquence) : icône dédiée + lien
    // cliquable vers l'écran source quand résolu (voir `resolveMarketingLink`,
    // fourni par `LeadForm.jsx` depuis la liste marketing déjà chargée —
    // aucun appel réseau ici, présentation pure inchangée).
    const touche = parseMarketingTouch(a.body)
    if (touche) {
      const href = resolveMarketingLink?.(touche.type, touche.nom)
      return (
        <span>
          <Megaphone size={12} className="chatter-marketing-icon" aria-hidden="true" />
          {' '}<strong>Marketing&nbsp;:</strong> {a.body}
          {href && (
            <>
              {' '}
              <a href={href} className="chatter-marketing-link">
                Voir {touche.type === 'campagne' ? 'la campagne' : 'la séquence'}
              </a>
            </>
          )}
        </span>
      )
    }
    return (
      <span>
        📝 <strong>Note&nbsp;:</strong> {a.body}
        {/* VX111 — pièce jointe attachée à CETTE note (photo prise depuis
            mobile pendant une visite, ex.) — même proxy Django que
            AttachmentsPanel, jamais un lien MinIO direct. */}
        {a.attachment_url && (
          <>
            {' '}
            <a
              href={a.attachment_url}
              target="_blank"
              rel="noopener noreferrer"
              className="chatter-note-attachment-link"
            >
              <Paperclip size={12} aria-hidden="true" /> {a.attachment_filename || 'Pièce jointe'}
            </a>
          </>
        )}
      </span>
    )
  }
  if (a.kind === 'creation') {
    return <span>✨ {a.body}</span>
  }
  if (a.kind === 'modification') {
    return (
      <span>
        <strong>{a.field_label}&nbsp;:</strong>{' '}
        {a.old_value} → <strong>{a.new_value}</strong>
      </span>
    )
  }
  // FG30/QX27 — appel/e-mail journalisés.
  if (a.kind === 'appel') {
    return (
      <span>
        📞 <strong>Appel</strong>
        {OUTCOME_LABELS[a.outcome] && <> — <strong>{OUTCOME_LABELS[a.outcome]}</strong></>}
        {a.body ? <>&nbsp;: {a.body}</> : null}
      </span>
    )
  }
  if (a.kind === 'email') {
    return (
      <span>
        ✉️ <strong>E-mail</strong>
        {OUTCOME_LABELS[a.outcome] && <> — <strong>{OUTCOME_LABELS[a.outcome]}</strong></>}
        {a.body ? <>&nbsp;: {a.body}</> : null}
      </span>
    )
  }
  // QX32 — timeline unifiée : cycle de vie devis + engagement proposition.
  if (a.kind === 'devis_sent') {
    return <span>📤 <strong>Devis envoyé</strong>{a.body ? <>&nbsp;: {a.body}</> : null}</span>
  }
  if (a.kind === 'devis_opened') {
    return <span>👁️ <strong>Proposition ouverte</strong>{a.body ? <>&nbsp;: {a.body}</> : null}</span>
  }
  if (a.kind === 'devis_signed') {
    return <span>✅ <strong>Devis signé</strong>{a.body ? <>&nbsp;: {a.body}</> : null}</span>
  }
  if (a.kind === 'devis_refused') {
    return <span>❌ <strong>Devis refusé</strong>{a.body ? <>&nbsp;: {a.body}</> : null}</span>
  }
  if (a.kind === 'devis_engagement') {
    return <span>📊 <strong>Engagement proposition</strong>{a.body ? <>&nbsp;: {a.body}</> : null}</span>
  }
  return <span>{a.body}</span>
}

/**
 * @param {Array} entries      Activités serveur (shape `crm.LeadActivity` /
 *                              endpoint `historique/`) — note/creation/
 *                              modification/appel/email/devis_*.
 * @param {Array} [attachments] Pièces jointes récentes (shape
 *                              `recordsApi.getAttachments`) injectées dans le
 *                              fil au lieu d'un onglet séparé.
 * @param {string} [emptyLabel] Message si le fil est vide.
 * @param {Function} [resolveMarketingLink] NTMKT11 — `(type, nom) => url|null`
 *                              résout le lien cliquable d'une touche marketing
 *                              (campagne/séquence) reconnue dans une note —
 *                              non fourni = pas de lien (comportement actuel
 *                              inchangé pour tout autre appelant).
 * @param {boolean} [pinned]   LW20 — additif, défaut false. Active l'affichage
 *                              « épinglé » : les entrées `item.pinned` (backend
 *                              LW28) sortent de la chronologie et remontent en
 *                              tête (icône 📌), hors des groupes jour. Sans ce
 *                              prop, comportement STRICTEMENT inchangé pour les
 *                              appelants existants (DevisList/FactureList/
 *                              LeadForm) qui n'ont pas de notion d'épinglage.
 * @param {Function} [onTogglePin] LW20 — additif, `(item) => void` appelé au
 *                              clic sur le bouton épingler/désépingler (révélé
 *                              au survol/focus d'une entrée). Absent = pas de
 *                              bouton rendu, même si `pinned` est actif.
 */
export default function ChatterTimeline({
  entries, attachments, emptyLabel = 'Aucune activité pour le moment.',
  resolveMarketingLink, pinned = false, onTogglePin,
}) {
  const feed = buildFeed(entries, attachments)
  if (feed.length === 0) {
    return <p className="gen-hint chatter-empty">{emptyLabel}</p>
  }
  // LW20 — quand `pinned` est actif, les notes épinglées sortent de la
  // chronologie normale (hors groupes jour) et remontent dans une section
  // dédiée en tête. Un item de pièce jointe (`__feedKind === 'attachment'`)
  // n'est jamais une `LeadActivity` et ne porte donc jamais `pinned`.
  const pinnedItems = pinned
    ? feed.filter((item) => item.__feedKind === 'activity' && item.pinned)
    : []
  const restFeed = pinned
    ? feed.filter((item) => !(item.__feedKind === 'activity' && item.pinned))
    : feed
  const groups = groupByDay(restFeed)

  const renderItem = (item) => {
    if (item.__feedKind === 'attachment') {
      return (
        <div key={`att-${item.id}`} className="chatter-item chatter-attachment">
          <Avatar name={item.uploaded_by_nom} size={24} />
          <div className="chatter-item-body">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="chatter-attachment-link"
            >
              <Paperclip size={13} aria-hidden="true" /> {item.filename}
            </a>
            <span className="chatter-meta">
              — par {item.uploaded_by_nom ?? '?'} · {timeAgo(item.__at)}
            </span>
          </div>
        </div>
      )
    }
    const isNote = item.kind === 'note'
    const isAutoLog = AUTO_LOG_KINDS.has(item.kind)
    const isMarketing = isNote && !!parseMarketingTouch(item.body)
    const classes = [
      'chatter-item',
      `chatter-${item.kind}`,
      isNote ? 'chatter-item-note' : '',
      isAutoLog ? 'chatter-item-autolog' : '',
      isMarketing ? 'chatter-item-marketing' : '',
    ].filter(Boolean).join(' ')
    return (
      <div key={item.id} className={classes}>
        <Avatar name={item.user_nom} size={24} />
        <div className="chatter-item-body">
          {isAutoLog && <Pencil size={11} className="chatter-autolog-icon" aria-hidden="true" />}
          {pinned && item.pinned && (
            <span className="lw-context-pin-badge" title="Épinglée">📌</span>
          )}
          <ActivityLine a={item} resolveMarketingLink={resolveMarketingLink} />
          {item.bulk && <span className="chatter-bulk">en masse</span>}
          <span className="chatter-meta">
            — par {item.user_nom ?? '?'} · {timeAgo(item.__at)}
          </span>
        </div>
        {onTogglePin && (
          <button
            type="button"
            className="lw-context-pin-toggle"
            onClick={() => onTogglePin(item)}
            aria-label={item.pinned ? 'Désépingler cette note' : 'Épingler cette note'}
            title={item.pinned ? 'Désépingler' : 'Épingler en tête'}
          >
            {item.pinned ? <PinOff size={13} aria-hidden="true" /> : <Pin size={13} aria-hidden="true" />}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="chatter-timeline chatter-timeline-grouped">
      {pinnedItems.length > 0 && (
        <div className="lw-context-chatter-pinned">
          {pinnedItems.map(renderItem)}
        </div>
      )}
      {groups.map((group) => (
        <div key={group.label} className="chatter-day-group">
          <div className="chatter-day-label">{group.label}</div>
          {group.items.map(renderItem)}
        </div>
      ))}
    </div>
  )
}
