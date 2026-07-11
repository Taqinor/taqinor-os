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

// Position CANONIQUE dans l'entonnoir chantier (−1 si inconnu/non canonique).
// Sert aux gardes de transition : on raisonne TOUJOURS sur le statut canonique
// pour couvrir les statuts hérités (mise_en_service → receptionne, etc.).
export function canonicalRank(key) {
  return INSTALLATION_STATUSES.indexOf(canonicalStatus(key))
}

// Un mouvement de statut est-il AUTORISÉ ? On n'autorise qu'un pas en avant ou
// en arrière sur l'entonnoir canonique (|Δrang| ≤ 1). Rester sur place est
// toujours permis. Un statut hérité déjà stocké (rang −1) ne peut pas être la
// CIBLE d'un mouvement, mais peut en être la source (il se rabat sur sa colonne
// canonique). Miroir conceptuel de Installation.STATUT_ORDER côté backend.
export function canMoveStatus(from, to) {
  if (from === to) return true
  // La CIBLE doit être un statut canonique direct (jamais un statut hérité).
  const b = INSTALLATION_STATUSES.indexOf(to)
  if (b === -1) return false
  const a = canonicalRank(from)
  if (a === -1) return false // source hors entonnoir : pas de saut direct
  return Math.abs(a - b) <= 1
}

// Statuts canoniques accessibles depuis `from` (courant ±1), pour alimenter un
// sélecteur restreint. La valeur courante est toujours incluse.
export function adjacentStatuses(from) {
  return INSTALLATION_STATUSES.filter((s) => canMoveStatus(from, s) || s === from)
}

// Un chantier est « en retard » de pose quand la date prévue est passée, que la
// pose réelle n'est pas saisie, et qu'il n'a pas encore atteint « Installé »
// (donc ni installé/réceptionné/clôturé) et n'est pas annulé. Calcul à la
// lecture (aucune donnée serveur supplémentaire).
export function isPoseEnRetard(item, today = new Date()) {
  if (!item || item.annule) return false
  if (item.date_pose_reelle) return false
  const prevue = item.date_pose_prevue
  if (!prevue || typeof prevue !== 'string') return false
  const rank = canonicalRank(item.statut)
  const installeRank = INSTALLATION_STATUSES.indexOf('installe')
  if (rank >= installeRank && rank !== -1) return false
  const t = new Date(today)
  const todayStr = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  return prevue < todayStr
}

// Prochaine action recommandée selon le statut canonique. Retourne un libellé FR
// court, ou null si aucune action évidente.
export function nextBestAction(item) {
  if (!item || item.annule) return null
  const canon = canonicalStatus(item.statut)
  if (canon === 'signe') return 'Commander le matériel'
  if (canon === 'materiel_commande') return 'Planifier la pose'
  if (canon === 'planifie') return 'Démarrer le chantier'
  if (canon === 'en_cours') return 'Marquer la pose installée'
  if (canon === 'installe') return 'Planifier la réception'
  if (canon === 'receptionne') return 'Clôturer le chantier'
  return null
}

// N13 — poses « à venir » : chantiers PLANIFIÉ (canonique) dont la date prévue
// tombe entre aujourd'hui et J+`days` inclus, non annulés. Calcul à la lecture.
export function upcomingPoses(items, days = 7, today = new Date()) {
  const t = new Date(today)
  const start = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`
  const end = new Date(t)
  end.setDate(end.getDate() + days)
  const endStr = `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`
  return (items ?? []).filter((it) => {
    if (!it || it.annule) return false
    if (canonicalStatus(it.statut) !== 'planifie') return false
    const p = it.date_pose_prevue
    if (!p || typeof p !== 'string') return false
    return p >= start && p <= endStr
  })
}

// N14 — charge par installateur : nb de poses À VENIR (≤ `days` j) par
// technicien responsable. Renvoie [{ nom, count }] trié décroissant.
export function installerLoad(items, days = 14, today = new Date()) {
  const counts = new Map()
  for (const it of upcomingPoses(items, days, today)) {
    const nom = it.technicien_nom || 'Non assigné'
    counts.set(nom, (counts.get(nom) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([nom, count]) => ({ nom, count }))
    .sort((a, b) => b.count - a.count)
}

// N14 — synthèse funnel : compte des chantiers par statut canonique + total en
// retard. Renvoie { rows: [{ key, label, count }], retard }.
export function funnelSummary(items, today = new Date()) {
  const counts = Object.fromEntries(INSTALLATION_STATUSES.map((s) => [s, 0]))
  let retard = 0
  for (const it of items ?? []) {
    if (!it) continue
    const canon = canonicalStatus(it.statut)
    if (counts[canon] != null) counts[canon] += 1
    if (isPoseEnRetard(it, today)) retard += 1
  }
  const rows = INSTALLATION_STATUSES.map((s) => ({
    key: s, label: STATUS_LABELS[s], count: counts[s],
  }))
  return { rows, retard }
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

// ── F3 — statut PROPRE de l'intervention (sortie chantier) ───────────────────
// Machine à états TOTALEMENT distincte de l'entonnoir chantier
// (INSTALLATION_STATUSES) et du contrat STAGES.py — un kanban à part entière.
export const INTERVENTION_STATUSES = [
  'a_preparer',
  'prete',
  'en_route',
  'sur_site',
  'terminee',
  'validee',
]

export const INTERVENTION_STATUS_LABELS = {
  a_preparer: 'À préparer',
  prete: 'Prête',
  en_route: 'En route',
  sur_site: 'Sur site',
  terminee: 'Terminée',
  validee: 'Validée',
}

export const INTERVENTION_STATUS_COLORS = {
  a_preparer: '#64748b',
  prete: '#3b82f6',
  en_route: '#a855f7',
  sur_site: '#f59e0b',
  terminee: '#16a34a',
  validee: '#15803d',
}

export function interventionStatusLabel(key) {
  return INTERVENTION_STATUS_LABELS[key] ?? key ?? '—'
}

export function interventionStatusColor(key) {
  return INTERVENTION_STATUS_COLORS[key] ?? '#64748b'
}

// Position dans la machine à états — pour ORDONNER les colonnes / bloquer un
// recul côté UI (miroir de Intervention.STATUT_ORDER côté backend).
export function interventionStatusRank(key) {
  const i = INTERVENTION_STATUSES.indexOf(key)
  return i === -1 ? INTERVENTION_STATUSES.length : i
}

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

// Statut du dossier réglementaire loi 82-21 (miroir de
// Installation.DossierStatut côté backend) — sert au filtre Parc N41.
export const DOSSIER_STATUT_LABELS = {
  non_concerne: 'Non concerné',
  a_deposer: 'À déposer',
  depose: 'Déposé',
  approuve: 'Approuvé',
  compteur_pose: 'Compteur posé',
}

// ── Parc installé — helpers PURS (logique testable, sans React) ──────────────

// Tranche de puissance d'un système (kWc) → libellé FR, ou null si ≤ 0.
export function capacityBand(kwc) {
  const v = Number(kwc) || 0
  if (v <= 0) return null
  if (v < 3) return '< 3 kWc'
  if (v < 10) return '3–10 kWc'
  if (v < 50) return '10–50 kWc'
  return '≥ 50 kWc'
}

export const CAPACITY_BANDS = ['< 3 kWc', '3–10 kWc', '10–50 kWc', '≥ 50 kWc']

// Année d'installation : date de réception en priorité, sinon mise en service
// (les systèmes hérités sont stockés en « mise_en_service »). null si inconnue.
export function installYear(it) {
  const iso = it?.date_reception || it?.date_mise_en_service
  if (!iso) return null
  const y = parseInt(String(iso).slice(0, 4), 10)
  return Number.isNaN(y) ? null : y
}

// Synthèse du parc : total kWc installé + comptes par type d'installation et par
// tranche de puissance. Calcul à la lecture (aucun appel serveur en plus).
export function parcSummary(items) {
  let totalKwc = 0
  const parType = {}
  const parTranche = {}
  for (const it of items ?? []) {
    if (!it) continue
    totalKwc += Number(it.puissance_installee_kwc) || 0
    const type = it.type_installation || 'autre'
    parType[type] = (parType[type] ?? 0) + 1
    const band = capacityBand(it.puissance_installee_kwc)
    if (band) parTranche[band] = (parTranche[band] ?? 0) + 1
  }
  return {
    total: (items ?? []).length,
    totalKwc: Math.round(totalKwc * 100) / 100,
    parType,
    parTranche,
  }
}

// Libellés/couleurs de l'état de garantie AGRÉGÉ d'un système (parc_garantie_etat
// renvoyé par le serializer). null = aucun équipement enregistré → pas de badge.
export const PARC_GARANTIE_LABELS = {
  sous_garantie: { label: 'Sous garantie', tone: 'success' },
  expire_bientot: { label: 'Garantie expire bientôt', tone: 'warning' },
  hors_garantie: { label: 'Hors garantie', tone: 'danger' },
  non_renseignee: { label: 'Garantie non renseignée', tone: 'neutral' },
}

export const EMPTY_FILTERS = {
  q: '',
  statut: '',
  technicien: '',
  type_installation: '',
  regime: '',
  art33: '', // '' | 'seuls'
  annule: 'avec', // 'avec' | 'sans' | 'seuls'
  mine: '', // '' | 'only' (filtre SERVEUR « Mes chantiers »)
  nouveaux: false, // VX218 — filtre CLIENT « Mes nouveaux chantiers »
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
      (it.site_ville ?? '').toLowerCase().includes(q) ||
      (it.devis_reference ?? '').toLowerCase().includes(q) ||
      (it.technicien_nom ?? '').toLowerCase().includes(q)
    )
  })
}

// VX218 — un chantier est « nouveau pour moi » quand il m'est assigné
// (technicien_responsable = mon id) et que sa `date_creation` est postérieure
// à ma dernière visite de l'écran (`lastSeen`, timestamp ISO ou null = tout
// est nouveau). Aucun champ de date de RÉASSIGNATION n'existe côté modèle
// aujourd'hui (VX213 non construit) : `date_creation` est le seul horodatage
// réel disponible — jamais de fabrication d'un champ absent.
export function isNewlyAssigned(item, userId, lastSeen) {
  if (!item || !userId) return false
  if (item.technicien_responsable !== userId) return false
  if (!item.date_creation) return false
  if (!lastSeen) return true
  return new Date(item.date_creation).getTime() > new Date(lastSeen).getTime()
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
