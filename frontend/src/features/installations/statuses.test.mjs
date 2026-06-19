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
