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
}

export function filterTickets(items, filters) {
  const f = { ...EMPTY_TICKET_FILTERS, ...(filters ?? {}) }
  const q = f.q.trim().toLowerCase()
  return (items ?? []).filter((it) => {
    if (f.ouvert === 'ouverts'
        && (!TICKET_OPEN_STATUSES.includes(it.statut) || it.annule)) return false
    if (f.statut && it.statut !== f.statut) return false
    if (f.type && it.type !== f.type) return false
    if (f.priorite && it.priorite !== f.priorite) return false
    if (f.technicien && (it.technicien_nom ?? '') !== f.technicien) return false
    if (f.sous_garantie && (it.sous_garantie_effectif ?? '') !== f.sous_garantie) return false
    if (!q) return true
    return (
      (it.reference ?? '').toLowerCase().includes(q) ||
      (it.client_nom ?? '').toLowerCase().includes(q) ||
      (it.installation_reference ?? '').toLowerCase().includes(q) ||
      (it.description ?? '').toLowerCase().includes(q)
    )
  })
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
