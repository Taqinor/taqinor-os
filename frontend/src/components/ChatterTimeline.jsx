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
import { Pencil, Paperclip } from 'lucide-react'

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

function ActivityLine({ a }) {
  if (a.kind === 'note') {
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
 */
export default function ChatterTimeline({ entries, attachments, emptyLabel = 'Aucune activité pour le moment.' }) {
  const feed = buildFeed(entries, attachments)
  if (feed.length === 0) {
    return <p className="gen-hint chatter-empty">{emptyLabel}</p>
  }
  const groups = groupByDay(feed)

  return (
    <div className="chatter-timeline chatter-timeline-grouped">
      {groups.map((group) => (
        <div key={group.label} className="chatter-day-group">
          <div className="chatter-day-label">{group.label}</div>
          {group.items.map((item) => {
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
            const classes = [
              'chatter-item',
              `chatter-${item.kind}`,
              isNote ? 'chatter-item-note' : '',
              isAutoLog ? 'chatter-item-autolog' : '',
            ].filter(Boolean).join(' ')
            return (
              <div key={item.id} className={classes}>
                <Avatar name={item.user_nom} size={24} />
                <div className="chatter-item-body">
                  {isAutoLog && <Pencil size={11} className="chatter-autolog-icon" aria-hidden="true" />}
                  <ActivityLine a={item} />
                  {item.bulk && <span className="chatter-bulk">en masse</span>}
                  <span className="chatter-meta">
                    — par {item.user_nom ?? '?'} · {timeAgo(item.__at)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
