import test from 'node:test'
import assert from 'node:assert/strict'

import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
  statusOrder,
  statusLabel,
  applyStatutConfig,
  filterInstallations,
  sortInstallations,
  EMPTY_FILTERS,
  canMoveStatus,
  adjacentStatuses,
  isPoseEnRetard,
  nextBestAction,
  upcomingPoses,
  funnelSummary,
  installerLoad,
  capacityBand,
  installYear,
  parcSummary,
  CAPACITY_BANDS,
  PARC_GARANTIE_LABELS,
  DOSSIER_STATUT_LABELS,
  isNewlyAssigned,
} from './statuses.js'

test('les 7 statuts chantier canoniques, dans l\'ordre d\'entonnoir', () => {
  assert.deepEqual(INSTALLATION_STATUSES, [
    'signe', 'materiel_commande', 'planifie', 'en_cours',
    'installe', 'receptionne', 'cloture',
  ])
  for (const s of INSTALLATION_STATUSES) {
    assert.ok(STATUS_LABELS[s], `libellé manquant pour ${s}`)
    assert.ok(STATUS_COLORS[s], `couleur manquante pour ${s}`)
  }
})

test('statusOrder respecte l\'entonnoir, pas l\'alphabet', () => {
  assert.ok(statusOrder('signe') < statusOrder('planifie'))
  assert.ok(statusOrder('receptionne') < statusOrder('cloture'))
  // "installe" (i) doit venir AVANT "receptionne" (r) dans l'entonnoir.
  assert.ok(statusOrder('installe') < statusOrder('receptionne'))
  // Un statut hérité tombe dans sa colonne canonique : mise_en_service →
  // receptionne (donc au même rang que receptionne).
  assert.equal(statusOrder('mise_en_service'), statusOrder('receptionne'))
  assert.equal(statusOrder('inconnu'), INSTALLATION_STATUSES.length)
})

test('sortInstallations trie par statut dans l\'ordre funnel', () => {
  const rows = [
    { id: 1, statut: 'cloture' },
    { id: 2, statut: 'signe' },
    { id: 3, statut: 'installe' },
  ]
  const sorted = sortInstallations(rows, 'statut', 'asc')
  assert.deepEqual(sorted.map((r) => r.id), [2, 3, 1])
})

test('filterInstallations : recherche + drapeau annulé', () => {
  const rows = [
    { id: 1, reference: 'CHT-1', client_nom: 'Alpha', statut: 'pose', annule: false },
    { id: 2, reference: 'CHT-2', client_nom: 'Beta', statut: 'pose', annule: true },
  ]
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, q: 'alpha' }).length, 1)
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, annule: 'sans' }).length, 1)
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, annule: 'seuls' }).length, 1)
  assert.equal(filterInstallations(rows, EMPTY_FILTERS).length, 2)
})

// ── N58 — couche de configuration des libellés/ordre (purement affichage) ──
test('applyStatutConfig surcharge libellé & ordre sans toucher aux clés', () => {
  // Défaut avant config.
  assert.equal(statusLabel('signe'), 'Signé')
  // Surcharge : renomme « signe » et le pousse après « cloture ».
  applyStatutConfig([
    { cle: 'signe', libelle: 'Contrat signé', ordre: 9, actif: true },
    { cle: 'cloture', libelle: 'Terminé', ordre: 0, actif: true },
  ])
  assert.equal(statusLabel('signe'), 'Contrat signé')
  assert.equal(statusLabel('cloture'), 'Terminé')
  // L'ordre d'AFFICHAGE suit la config : cloture (0) avant signe (9).
  assert.ok(statusOrder('cloture') < statusOrder('signe'))
  // Les clés canoniques ne bougent jamais (machine à états intacte).
  assert.deepEqual(INSTALLATION_STATUSES, [
    'signe', 'materiel_commande', 'planifie', 'en_cours',
    'installe', 'receptionne', 'cloture',
  ])
  // Réinitialisation : retour aux défauts byte-identiques.
  applyStatutConfig(null)
  assert.equal(statusLabel('signe'), 'Signé')
  assert.ok(statusOrder('signe') < statusOrder('cloture'))
})

test('applyStatutConfig ignore les clés inconnues', () => {
  applyStatutConfig([{ cle: 'inexistant', libelle: 'X', ordre: 0 }])
  // Aucun effet : on reste sur les défauts.
  assert.equal(statusLabel('signe'), 'Signé')
  applyStatutConfig(null)
})

// ── Gardes de transition (N1/N2) : un seul pas sur l'entonnoir ──
test('canMoveStatus : un seul pas avant/arrière, jamais de saut', () => {
  assert.ok(canMoveStatus('signe', 'materiel_commande')) // +1
  assert.ok(canMoveStatus('planifie', 'materiel_commande')) // −1
  assert.ok(canMoveStatus('signe', 'signe')) // sur place
  assert.equal(canMoveStatus('signe', 'planifie'), false) // saut +2
  assert.equal(canMoveStatus('signe', 'cloture'), false) // saut lointain
  // Un statut hérité (source) se rabat sur sa colonne canonique : mise_en_service
  // → receptionne, donc avancer vers cloture (un pas) est permis.
  assert.ok(canMoveStatus('mise_en_service', 'cloture'))
  // Une cible non canonique est toujours refusée.
  assert.equal(canMoveStatus('receptionne', 'mise_en_service'), false)
})

test('adjacentStatuses : courant ±1, valeur courante incluse', () => {
  const adj = adjacentStatuses('planifie')
  assert.ok(adj.includes('planifie'))
  assert.ok(adj.includes('materiel_commande'))
  assert.ok(adj.includes('en_cours'))
  assert.equal(adj.includes('signe'), false)
  assert.equal(adj.includes('installe'), false)
})

// ── Badge « pose en retard » (calcul à la lecture) ──
test('isPoseEnRetard : prévue passée, réelle vide, pas encore installé', () => {
  const today = new Date('2026-06-19')
  assert.ok(isPoseEnRetard({ statut: 'planifie', date_pose_prevue: '2026-06-10' }, today))
  // Pose réelle saisie → plus en retard.
  assert.equal(isPoseEnRetard(
    { statut: 'planifie', date_pose_prevue: '2026-06-10', date_pose_reelle: '2026-06-15' }, today), false)
  // Déjà installé → plus en retard.
  assert.equal(isPoseEnRetard({ statut: 'installe', date_pose_prevue: '2026-06-10' }, today), false)
  // Annulé → jamais.
  assert.equal(isPoseEnRetard(
    { statut: 'planifie', date_pose_prevue: '2026-06-10', annule: true }, today), false)
  // Date future → pas en retard.
  assert.equal(isPoseEnRetard({ statut: 'planifie', date_pose_prevue: '2026-06-25' }, today), false)
})

test('nextBestAction : action FR par statut', () => {
  assert.equal(nextBestAction({ statut: 'signe' }), 'Commander le matériel')
  assert.equal(nextBestAction({ statut: 'installe' }), 'Planifier la réception')
  assert.equal(nextBestAction({ statut: 'cloture' }), null)
  assert.equal(nextBestAction({ statut: 'signe', annule: true }), null)
})

test('upcomingPoses : planifiés à ≤ J+7', () => {
  const today = new Date('2026-06-19')
  const rows = [
    { id: 1, statut: 'planifie', date_pose_prevue: '2026-06-22' }, // dans la fenêtre
    { id: 2, statut: 'planifie', date_pose_prevue: '2026-07-05' }, // hors fenêtre
    { id: 3, statut: 'signe', date_pose_prevue: '2026-06-21' }, // pas planifié
    { id: 4, statut: 'planifie', date_pose_prevue: '2026-06-22', annule: true }, // annulé
  ]
  assert.deepEqual(upcomingPoses(rows, 7, today).map((r) => r.id), [1])
})

test('installerLoad : compte des poses à venir par installateur', () => {
  const today = new Date('2026-06-19')
  const rows = [
    { statut: 'planifie', date_pose_prevue: '2026-06-22', technicien_nom: 'Ali' },
    { statut: 'planifie', date_pose_prevue: '2026-06-24', technicien_nom: 'Ali' },
    { statut: 'planifie', date_pose_prevue: '2026-06-23', technicien_nom: 'Sara' },
    { statut: 'planifie', date_pose_prevue: '2026-06-23' }, // non assigné
  ]
  const load = installerLoad(rows, 14, today)
  assert.equal(load[0].nom, 'Ali')
  assert.equal(load[0].count, 2)
  assert.ok(load.some((l) => l.nom === 'Non assigné' && l.count === 1))
})

test('funnelSummary : compte par statut + retard', () => {
  const today = new Date('2026-06-19')
  const rows = [
    { statut: 'signe' },
    { statut: 'planifie', date_pose_prevue: '2026-06-10' }, // en retard
    { statut: 'planifie' },
  ]
  const { rows: counts, retard } = funnelSummary(rows, today)
  assert.equal(counts.find((r) => r.key === 'signe').count, 1)
  assert.equal(counts.find((r) => r.key === 'planifie').count, 2)
  assert.equal(retard, 1)
})

// ── Parc installé — helpers ──────────────────────────────────────────────────

test('capacityBand : tranches de puissance', () => {
  assert.equal(capacityBand(0), null)
  assert.equal(capacityBand(-5), null)
  assert.equal(capacityBand(2.9), '< 3 kWc')
  assert.equal(capacityBand(3), '3–10 kWc')
  assert.equal(capacityBand(9.99), '3–10 kWc')
  assert.equal(capacityBand(10), '10–50 kWc')
  assert.equal(capacityBand(49.9), '10–50 kWc')
  assert.equal(capacityBand(50), '≥ 50 kWc')
  // Toutes les tranches produites sont dans la liste publiée.
  for (const v of [1, 5, 20, 100]) {
    assert.ok(CAPACITY_BANDS.includes(capacityBand(v)))
  }
})

test('installYear : réception en priorité, sinon mise en service', () => {
  assert.equal(installYear({ date_reception: '2025-04-01' }), 2025)
  // Système hérité : pas de réception → on utilise la mise en service.
  assert.equal(installYear({ date_mise_en_service: '2022-09-12' }), 2022)
  assert.equal(installYear({
    date_reception: '2026-01-01', date_mise_en_service: '2020-01-01',
  }), 2026)
  assert.equal(installYear({}), null)
  assert.equal(installYear({ date_reception: 'invalide' }), null)
})

test('parcSummary : total kWc + comptes par type et tranche', () => {
  const rows = [
    { puissance_installee_kwc: '5', type_installation: 'residentiel' },
    { puissance_installee_kwc: '12', type_installation: 'industriel' },
    { puissance_installee_kwc: '2', type_installation: 'residentiel' },
    { puissance_installee_kwc: null, type_installation: 'agricole' },
  ]
  const s = parcSummary(rows)
  assert.equal(s.total, 4)
  assert.equal(s.totalKwc, 19)
  assert.equal(s.parType.residentiel, 2)
  assert.equal(s.parType.industriel, 1)
  assert.equal(s.parType.agricole, 1)
  assert.equal(s.parTranche['3–10 kWc'], 1)
  assert.equal(s.parTranche['10–50 kWc'], 1)
  assert.equal(s.parTranche['< 3 kWc'], 1)
  // Une puissance nulle ne crée pas de tranche.
  assert.equal(Object.values(s.parTranche).reduce((a, b) => a + b, 0), 3)
})

test('parcSummary : parc vide', () => {
  const s = parcSummary([])
  assert.equal(s.total, 0)
  assert.equal(s.totalKwc, 0)
  assert.deepEqual(s.parType, {})
  assert.deepEqual(s.parTranche, {})
})

test('libellés de garantie/dossier du parc présents', () => {
  for (const k of ['sous_garantie', 'expire_bientot', 'hors_garantie', 'non_renseignee']) {
    assert.ok(PARC_GARANTIE_LABELS[k]?.label, `libellé garantie manquant : ${k}`)
    assert.ok(PARC_GARANTIE_LABELS[k]?.tone, `ton garantie manquant : ${k}`)
  }
  for (const k of ['non_concerne', 'a_deposer', 'depose', 'approuve', 'compteur_pose']) {
    assert.ok(DOSSIER_STATUT_LABELS[k], `libellé dossier manquant : ${k}`)
  }
})

// VX218 — badge « Nouveau » : un chantier assigné à moi depuis ma dernière
// visite. Jamais fabriqué : pas d'utilisateur / pas assigné à moi / pas de
// date_creation → jamais « nouveau ».
test('isNewlyAssigned : true si assigné à moi et créé après lastSeen', () => {
  const item = { technicien_responsable: 7, date_creation: '2026-07-10T12:00:00Z' }
  assert.equal(isNewlyAssigned(item, 7, '2026-07-09T00:00:00Z'), true)
})

test('isNewlyAssigned : false si créé avant lastSeen', () => {
  const item = { technicien_responsable: 7, date_creation: '2026-07-01T12:00:00Z' }
  assert.equal(isNewlyAssigned(item, 7, '2026-07-09T00:00:00Z'), false)
})

test('isNewlyAssigned : false si assigné à un autre utilisateur', () => {
  const item = { technicien_responsable: 99, date_creation: '2026-07-10T12:00:00Z' }
  assert.equal(isNewlyAssigned(item, 7, '2026-07-09T00:00:00Z'), false)
})

test('isNewlyAssigned : sans lastSeen (première visite), tout ce qui est assigné à moi est nouveau', () => {
  const item = { technicien_responsable: 7, date_creation: '2020-01-01T00:00:00Z' }
  assert.equal(isNewlyAssigned(item, 7, null), true)
})

test('isNewlyAssigned : jamais fabriqué sans userId ni sans date_creation', () => {
  assert.equal(isNewlyAssigned({ technicien_responsable: 7, date_creation: '2026-07-10T12:00:00Z' }, null, null), false)
  assert.equal(isNewlyAssigned({ technicien_responsable: 7 }, 7, null), false)
  assert.equal(isNewlyAssigned(null, 7, null), false)
})
