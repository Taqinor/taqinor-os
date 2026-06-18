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
