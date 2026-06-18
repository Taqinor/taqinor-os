// Statuts du chantier (réalisation physique) — couche INDÉPENDANTE de
// l'entonnoir lead (STAGES.py) et des statuts de document devis/facture.
// Liste FERMÉE, en ordre d'entonnoir. « annulé » est un drapeau, pas une étape.

// Entonnoir CANONIQUE du chantier (N1), dans l'ordre d'exécution.
export const INSTALLATION_STATUSES = [
  'signe',
  'materiel_commande',
  'planifie',
  'en_cours',
  'installe',
  'receptionne',
  'cloture',
]

export const STATUS_LABELS = {
  signe: 'Signé',
  materiel_commande: 'Matériel commandé',
  planifie: 'Planifié',
  en_cours: 'En cours',
  installe: 'Installé',
  receptionne: 'Réceptionné',
  cloture: 'Clôturé',
  // Statuts hérités (chantiers d'avant le funnel N1) — encore affichables.
  a_planifier: 'À planifier',
  pose_en_cours: 'Pose en cours',
  pose: 'Posé',
  raccordement_onee: 'Raccordement ONEE',
  mise_en_service: 'Mise en service',
}

export const STATUS_COLORS = {
  signe: '#64748b',
  materiel_commande: '#a855f7',
  planifie: '#3b82f6',
  en_cours: '#f59e0b',
  installe: '#8b5cf6',
  receptionne: '#16a34a',
  cloture: '#15803d',
  // Hérités → reprennent la teinte de leur colonne canonique.
  a_planifier: '#64748b',
  pose_en_cours: '#f59e0b',
  pose: '#8b5cf6',
  raccordement_onee: '#f59e0b',
  mise_en_service: '#16a34a',
}

// Rabat un statut hérité sur sa colonne canonique (kanban/parc) — miroir du
// backend Installation.LEGACY_STATUT_MAP.
export const LEGACY_STATUT_MAP = {
  a_planifier: 'signe',
  pose_en_cours: 'en_cours',
  pose: 'installe',
  raccordement_onee: 'en_cours',
  mise_en_service: 'receptionne',
}

export function canonicalStatus(key) {
  return LEGACY_STATUT_MAP[key] ?? key
}

export const TYPE_LABELS = {
  residentiel: 'Résidentiel',
  industriel: 'Industriel / Commercial',
  agricole: 'Agricole (pompage)',
}

export const RACCORDEMENT_LABELS = {
  monophase: 'Monophasé',
  triphase: 'Triphasé',
}

export const INTERVENTION_TYPES = [
  { value: 'pose', label: 'Pose' },
  { value: 'raccordement', label: 'Raccordement' },
  { value: 'mise_en_service', label: 'Mise en service' },
  { value: 'controle', label: 'Contrôle' },
  { value: 'depannage', label: 'Dépannage' },
]

// ── Couche de configuration N58 (libellé/ordre/visibilité, par société) ──────
// PUREMENT COSMÉTIQUE : surcharge le libellé affiché et l'ordre d'affichage,
// JAMAIS les clés canoniques ni la machine à états. Tant qu'aucune config n'est
// chargée, tout retombe sur les défauts codés en dur ci-dessus (comportement
// byte-identique). `canonicalStatus` / `INSTALLATION_STATUSES` (utilisés par
// les gardes de transition / le kanban) ne sont JAMAIS modifiés.
let _configLabels = null // { cle: libelle }
let _configOrder = null // { cle: ordre }

// Applique la liste effective renvoyée par l'API
// (parametresApi.getStatutsEffective('chantier')). `null`/`[]` = réinitialise
// sur les défauts. Seules les clés canoniques connues sont prises en compte.
export function applyStatutConfig(rows) {
  if (!rows || !rows.length) { _configLabels = null; _configOrder = null; return }
  const labels = {}
  const order = {}
  for (const r of rows) {
    if (!r || !INSTALLATION_STATUSES.includes(r.cle)) continue
    if (r.libelle) labels[r.cle] = r.libelle
    if (typeof r.ordre === 'number') order[r.cle] = r.ordre
  }
  _configLabels = Object.keys(labels).length ? labels : null
  _configOrder = Object.keys(order).length ? order : null
}

export function statusLabel(key) {
  if (_configLabels && _configLabels[key]) return _configLabels[key]
  // Un statut hérité hérite du libellé configuré de sa colonne canonique.
  const canon = canonicalStatus(key)
  if (_configLabels && _configLabels[canon] && canon !== key && !STATUS_LABELS[key]) {
    return _configLabels[canon]
  }
  return STATUS_LABELS[key] ?? key ?? '—'
}

export function statusColor(key) {
  return STATUS_COLORS[key] ?? '#64748b'
}

// Position dans l'entonnoir — pour TRIER les statuts dans l'ordre du funnel,
// jamais alphabétiquement. Les inconnus vont en fin. L'ordre configuré (N58)
// surcharge l'ordre canonique pour l'AFFICHAGE uniquement.
export function statusOrder(key) {
  const canon = canonicalStatus(key)
  if (_configOrder && typeof _configOrder[canon] === 'number') return _configOrder[canon]
  const i = INSTALLATION_STATUSES.indexOf(canon)
  return i === -1 ? INSTALLATION_STATUSES.length : i
}

export const REGIME_8221_LABELS = {
  non_concerne: 'Non concerné',
  declaration_bt: 'Déclaration (< 11 kW, BT)',
  accord_raccordement: 'Accord de raccordement',
  autorisation_anre: 'Autorisation ANRE (> 1 MW)',
}

export const EMPTY_FILTERS = {
  q: '',
  statut: '',
  technicien: '',
  type_installation: '',
  regime: '',
  art33: '', // '' | 'seuls'
  annule: 'avec', // 'avec' | 'sans' | 'seuls'
}

export function filterInstallations(items, filters) {
  const f = { ...EMPTY_FILTERS, ...(filters ?? {}) }
  const q = f.q.trim().toLowerCase()
  return (items ?? []).filter((it) => {
    if (f.statut && it.statut !== f.statut) return false
    if (f.type_installation && it.type_installation !== f.type_installation) return false
    if (f.technicien && (it.technicien_nom ?? '') !== f.technicien) return false
    if (f.regime && (it.regime_8221 ?? '') !== f.regime) return false
    if (f.art33 === 'seuls' && !it.art33_regularisation) return false
    if (f.annule === 'sans' && it.annule) return false
    if (f.annule === 'seuls' && !it.annule) return false
    if (!q) return true
    return (
      (it.reference ?? '').toLowerCase().includes(q) ||
      (it.client_nom ?? '').toLowerCase().includes(q) ||
      (it.site_ville ?? '').toLowerCase().includes(q)
    )
  })
}

// Tri funnel-aware : par défaut on trie par statut (ordre d'entonnoir) puis
// par date de pose prévue. Sinon par la clé demandée.
export function sortInstallations(items, key, dir) {
  const sign = dir === 'asc' ? 1 : -1
  const arr = [...(items ?? [])]
  arr.sort((a, b) => {
    let va
    let vb
    if (key === 'statut') {
      va = statusOrder(a.statut)
      vb = statusOrder(b.statut)
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
