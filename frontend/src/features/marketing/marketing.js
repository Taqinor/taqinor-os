/* ============================================================================
   MARKETING — logique métier PURE (sans JSX, testable au node).
   ----------------------------------------------------------------------------
   XMKT30 — Calendrier marketing unifié : agrège 4 sources company-scoped
   (campagnes planifiee_le / XMKT7, étapes de séquences dues, événements XMKT28,
   relances FG31), filtrable par canal, avec drag-to-reschedule pour les
   campagnes non parties. Miroir du pattern pur de `pages/CalendarPage.jsx`
   (monthGrid/ymd) répliqué ici pour rester indépendant (pas d'import depuis
   pages/ dans features/) et testable isolément.
   ========================================================================== */

// ── Types de source affichés dans le calendrier (5 sources agrégées) ──

export const SOURCE_TYPES = [
  { key: 'campagne', label: 'Campagnes', color: '#2563eb' },
  { key: 'etape_sequence', label: 'Étapes de séquence', color: '#0d9488' },
  { key: 'evenement', label: 'Événements', color: '#7c3aed' },
  { key: 'relance', label: 'Relances', color: '#ea580c' },
  // XMKT35 — posts réseaux sociaux planifiés (publication gated backend).
  { key: 'post_social', label: 'Posts sociaux', color: '#db2777' },
]
export const SOURCE_COLOR = Object.fromEntries(
  SOURCE_TYPES.map(t => [t.key, t.color]))
export const SOURCE_KEYS = SOURCE_TYPES.map(t => t.key)

// ── Canaux (filtre) — valeurs génériques, alignées sur les canaux de Campagne
// et des relances (email/sms/whatsapp/appel...). Une source sans canal connu
// (ex. un événement sans canal renseigné) reste visible tant qu'aucun filtre
// de canal n'est actif ; dès qu'un filtre est actif, seules les entrées dont
// le canal correspond restent affichées.
export const CHANNELS = [
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'appel', label: 'Appel' },
  { key: 'autre', label: 'Autre' },
]

const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTHS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
export { WEEKDAYS, MONTHS }

// Formate une Date en AAAA-MM-JJ (clé de regroupement stable, comparable en
// chaîne — même convention que CalendarPage.jsx).
export const ymd = (d) => {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

// Cases visibles : la grille commence au lundi de la semaine du 1er du mois et
// se termine au dimanche de la semaine du dernier jour (toujours 7 colonnes).
// Retire la dernière semaine si elle déborde entièrement sur le mois suivant.
export function monthGrid(year, month) {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // 0 = lundi
  const start = new Date(year, month, 1 - startOffset)
  const cells = []
  for (let i = 0; i < 42; i++) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    cells.push(d)
  }
  // La 6e semaine (cases 35–41) déborde entièrement sur le mois suivant dès que
  // son premier jour (lundi, case 35) n'est plus dans le mois : on la retire.
  if (cells[35].getMonth() !== month) {
    return cells.slice(0, 35)
  }
  return cells
}

// ── Normalisation de la réponse agrégée ──
//
// Forme attendue de la réponse (endpoint agrégé, à venir — voir comptaApi.js) :
//   { events: [
//       { id, source, date, title, channel, editable, link_type, link_id, ... }
//   ] }
// où `source` ∈ SOURCE_KEYS ('campagne' | 'etape_sequence' | 'evenement' |
// 'relance'), `date` est AAAA-MM-JJ, `editable` n'est vrai que pour les
// campagnes non parties (drag-to-reschedule).
export function normalizeEvents(raw) {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : (raw.events || [])
  return list.filter(Boolean)
}

// Regroupe les évènements par jour (AAAA-MM-JJ), après application des
// filtres de source masquée et de canal sélectionné.
export function groupByDay(events, { hiddenSources, channel } = {}) {
  const hidden = hiddenSources instanceof Set ? hiddenSources : new Set(hiddenSources || [])
  const map = {}
  for (const ev of events || []) {
    if (hidden.has(ev.source)) continue
    if (channel && ev.channel && ev.channel !== channel) continue
    if (channel && !ev.channel) continue
    ;(map[ev.date] = map[ev.date] || []).push(ev)
  }
  return map
}

// Filtre à plat (sans regroupement par jour) — utile pour les compteurs/tests.
export function filterEvents(events, { hiddenSources, channel } = {}) {
  const hidden = hiddenSources instanceof Set ? hiddenSources : new Set(hiddenSources || [])
  return (events || []).filter(ev => {
    if (hidden.has(ev.source)) return false
    if (channel && ev.channel !== channel) return false
    return true
  })
}

// Résout la route d'ouverture d'un objet cliqué (clic → ouvre l'objet).
const ROUTE_BY_LINK_TYPE = {
  campagne: '/comptabilite',
  etape_sequence: '/comptabilite',
  evenement: '/comptabilite',
  relance: '/crm',
  // XMKT35 — pas d'écran d'édition dédié aux posts : reste sur le calendrier.
  post_social: '/marketing/calendrier',
}

export function routeForEvent(ev) {
  if (!ev) return null
  return ROUTE_BY_LINK_TYPE[ev.link_type || ev.source] || null
}

// Un évènement n'est déplaçable que s'il est marqué éditable ET de source
// « campagne » (seules les campagnes non parties se replanifient par
// glisser-déposer ; étapes de séquence / événements / relances restent fixes).
export function isDraggable(ev) {
  return !!(ev && ev.editable && ev.source === 'campagne')
}

// Construit le payload de replanification pour l'API (drag-and-drop natif
// HTML5, comme CalendarPage.jsx — pas de lib externe).
export function buildReschedulePayload(ev, targetDate) {
  return { source: ev.source, id: ev.obj_id ?? ev.id, date: targetDate }
}
