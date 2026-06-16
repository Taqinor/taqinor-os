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

export function statusLabel(key) {
  return STATUS_LABELS[key] ?? key ?? '—'
}

export function statusColor(key) {
  return STATUS_COLORS[key] ?? '#64748b'
}

// Position dans l'entonnoir — pour TRIER les statuts dans l'ordre du funnel,
// jamais alphabétiquement. Les inconnus vont en fin.
export function statusOrder(key) {
  const i = INSTALLATION_STATUSES.indexOf(canonicalStatus(key))
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
