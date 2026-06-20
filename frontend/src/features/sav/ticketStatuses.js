// Cycle de vie des tickets SAV — couche INDÉPENDANTE de l'entonnoir lead
// (STAGES.py) et des statuts de document devis/facture. Liste FERMÉE, en ordre
// d'entonnoir. « annulé » est un drapeau (avec motif), pas une étape.

export const TICKET_STATUSES = [
  'nouveau',
  'planifie',
  'en_cours',
  'resolu',
  'cloture',
]

export const TICKET_STATUS_LABELS = {
  nouveau: 'Nouveau',
  planifie: 'Planifié',
  en_cours: 'En cours',
  resolu: 'Résolu',
  cloture: 'Clôturé',
}

export const TICKET_STATUS_COLORS = {
  nouveau: '#64748b',
  planifie: '#3b82f6',
  en_cours: '#f59e0b',
  resolu: '#16a34a',
  cloture: '#15803d',
}

export const TICKET_OPEN_STATUSES = ['nouveau', 'planifie', 'en_cours']

export const TICKET_TYPES = [
  { value: 'correctif', label: 'Correctif' },
  { value: 'preventif', label: 'Préventif' },
]
export const TICKET_TYPE_LABELS = { correctif: 'Correctif', preventif: 'Préventif' }

export const TICKET_PRIORITES = [
  { value: 'basse', label: 'Basse' },
  { value: 'normale', label: 'Normale' },
  { value: 'haute', label: 'Haute' },
  { value: 'urgente', label: 'Urgente' },
]
export const TICKET_PRIORITE_LABELS = {
  basse: 'Basse', normale: 'Normale', haute: 'Haute', urgente: 'Urgente',
}
const PRIO_RANK = { basse: 0, normale: 1, haute: 2, urgente: 3 }

export const SOUS_GARANTIE_OPTIONS = [
  { value: 'oui', label: 'Oui' },
  { value: 'non', label: 'Non' },
  { value: 'a_determiner', label: 'À déterminer' },
]
export const SOUS_GARANTIE_LABELS = {
  oui: 'Oui', non: 'Non', a_determiner: 'À déterminer',
}

// ── Couche de configuration N58 (libellé/ordre/visibilité, par société) ──────
// PUREMENT COSMÉTIQUE : surcharge le libellé affiché et l'ordre d'affichage,
// JAMAIS les clés canoniques (`TICKET_STATUSES`) ni la machine à états. Tant
// qu'aucune config n'est chargée, tout retombe sur les défauts codés en dur.
let _configLabels = null // { cle: libelle }
let _configOrder = null // { cle: ordre }

// Applique la liste effective renvoyée par l'API
// (parametresApi.getStatutsEffective('sav')). `null`/`[]` = réinitialise.
export function applyTicketStatutConfig(rows) {
  if (!rows || !rows.length) { _configLabels = null; _configOrder = null; return }
  const labels = {}
  const order = {}
  for (const r of rows) {
    if (!r || !TICKET_STATUSES.includes(r.cle)) continue
    if (r.libelle) labels[r.cle] = r.libelle
    if (typeof r.ordre === 'number') order[r.cle] = r.ordre
  }
  _configLabels = Object.keys(labels).length ? labels : null
  _configOrder = Object.keys(order).length ? order : null
}

export function statusLabel(key) {
  if (_configLabels && _configLabels[key]) return _configLabels[key]
  return TICKET_STATUS_LABELS[key] ?? key ?? '—'
}
export function statusColor(key) {
  return TICKET_STATUS_COLORS[key] ?? '#64748b'
}

// Position dans l'entonnoir — pour TRIER les statuts dans l'ordre du funnel,
// jamais alphabétiquement. Les inconnus vont en fin. L'ordre configuré (N58)
// surcharge l'ordre canonique pour l'AFFICHAGE uniquement.
export function statusOrder(key) {
  if (_configOrder && typeof _configOrder[key] === 'number') return _configOrder[key]
  const i = TICKET_STATUSES.indexOf(key)
  return i === -1 ? TICKET_STATUSES.length : i
}

export const EMPTY_TICKET_FILTERS = {
  q: '',
  statut: '',
  type: '',
  priorite: '',
  technicien: '',
  sous_garantie: '',
  ouvert: 'ouverts', // 'ouverts' | 'tous'
  annule: '', // '' (sans annulés en mode ouvert) | 'only' | 'sans'
  urgent_garantie: false, // puce « urgent & sous garantie »
}

export function filterTickets(items, filters) {
  const f = { ...EMPTY_TICKET_FILTERS, ...(filters ?? {}) }
  const q = f.q.trim().toLowerCase()
  return (items ?? []).filter((it) => {
    // Filtre d'annulation explicite (le backend supporte ?annule=only|sans).
    if (f.annule === 'only' && !it.annule) return false
    if (f.annule === 'sans' && it.annule) return false
    if (f.ouvert === 'ouverts'
        && (!TICKET_OPEN_STATUSES.includes(it.statut)
            || (it.annule && f.annule !== 'only'))) return false
    if (f.statut && it.statut !== f.statut) return false
    if (f.type && it.type !== f.type) return false
    if (f.priorite && it.priorite !== f.priorite) return false
    if (f.technicien && (it.technicien_nom ?? '') !== f.technicien) return false
    if (f.sous_garantie && (it.sous_garantie_effectif ?? '') !== f.sous_garantie) return false
    // Puce rapide « urgent & sous garantie » : priorité haute/urgente ET
    // garantie effective = oui.
    if (f.urgent_garantie
        && !(['haute', 'urgente'].includes(it.priorite)
             && (it.sous_garantie_effectif ?? '') === 'oui')) return false
    if (!q) return true
    return (
      (it.reference ?? '').toLowerCase().includes(q) ||
      (it.client_nom ?? '').toLowerCase().includes(q) ||
      (it.installation_reference ?? '').toLowerCase().includes(q) ||
      (it.description ?? '').toLowerCase().includes(q)
    )
  })
}

// ── L296 — garde de transition de statut (machine à états entonnoir) ──────────
// Bloque uniquement les SAUTS EN AVANT qui sautent une étape (ex. nouveau →
// clôturé sans en_cours). Reculer ou rester est toujours permis. Retourne true
// si le passage `from → to` est autorisé. Statuts inconnus : permissif.
export function isStatusTransitionAllowed(from, to) {
  if (!from || !to || from === to) return true
  const fi = TICKET_STATUSES.indexOf(from)
  const ti = TICKET_STATUSES.indexOf(to)
  if (fi === -1 || ti === -1) return true
  // Recul autorisé ; avancée d'une seule étape autorisée ; saut > 1 bloqué.
  return ti <= fi || ti - fi === 1
}

// ── L298 — âge / SLA d'un ticket (calculé à la lecture, sans planificateur) ──
// Jours écoulés depuis date_ouverture (ou date_creation en repli). Null si
// aucune date exploitable. Le seuil d'escalade dépend de la priorité.
export function ticketAgeDays(ticket, now = new Date()) {
  const raw = ticket?.date_ouverture || ticket?.date_creation
  if (!raw) return null
  const d = new Date(`${String(raw).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  const days = Math.floor((now - d) / 86400000)
  return days < 0 ? 0 : days
}

// Seuil d'alerte (jours) au-delà duquel un ticket ouvert est « en retard ».
// Plus court pour les priorités hautes/urgentes.
export function slaThresholdDays(priorite) {
  if (priorite === 'urgente') return 2
  if (priorite === 'haute') return 5
  return 10
}

// Niveau d'escalade visuel : 'ok' | 'warn' | 'late' selon l'âge vs seuil.
// Seuls les tickets OUVERTS non annulés sont concernés.
export function ticketSlaLevel(ticket, now = new Date()) {
  if (!ticket || ticket.annule
      || !TICKET_OPEN_STATUSES.includes(ticket.statut)) return 'ok'
  const age = ticketAgeDays(ticket, now)
  if (age == null) return 'ok'
  const seuil = slaThresholdDays(ticket.priorite)
  if (age >= seuil) return 'late'
  if (age >= seuil - Math.max(1, Math.round(seuil / 3))) return 'warn'
  return 'ok'
}

// ── L306/L314 — comptes par statut (ordre d'entonnoir respecté) ──────────────
// Retourne [{ key, label, count }] pour les 5 statuts canoniques, triés funnel.
export function statusCounts(items) {
  const counts = {}
  for (const k of TICKET_STATUSES) counts[k] = 0
  for (const it of items ?? []) {
    if (it && Object.prototype.hasOwnProperty.call(counts, it.statut)) {
      counts[it.statut] += 1
    }
  }
  return [...TICKET_STATUSES]
    .sort((a, b) => statusOrder(a) - statusOrder(b))
    .map((key) => ({ key, label: statusLabel(key), count: counts[key] }))
}

// Tri funnel-aware : par statut (ordre d'entonnoir) ou par priorité, sinon clé.
export function sortTickets(items, key, dir) {
  const sign = dir === 'asc' ? 1 : -1
  const arr = [...(items ?? [])]
  arr.sort((a, b) => {
    let va
    let vb
    if (key === 'statut') {
      va = statusOrder(a.statut)
      vb = statusOrder(b.statut)
    } else if (key === 'priorite') {
      va = PRIO_RANK[a.priorite] ?? 1
      vb = PRIO_RANK[b.priorite] ?? 1
    } else {
      va = a[key] ?? ''
      vb = b[key] ?? ''
    }
    if (va < vb) return -1 * sign
    if (va > vb) return 1 * sign
    return 0
  })
  return arr
}
