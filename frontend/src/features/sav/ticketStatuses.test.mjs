import test from 'node:test'
import assert from 'node:assert/strict'

import {
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_STATUS_COLORS,
  statusOrder,
  statusLabel,
  applyTicketStatutConfig,
  filterTickets,
  sortTickets,
  EMPTY_TICKET_FILTERS,
} from './ticketStatuses.js'

test("les 5 statuts ticket, dans l'ordre d'entonnoir", () => {
  assert.deepEqual(TICKET_STATUSES, [
    'nouveau', 'planifie', 'en_cours', 'resolu', 'cloture',
  ])
  for (const s of TICKET_STATUSES) {
    assert.ok(TICKET_STATUS_LABELS[s], `libellé manquant pour ${s}`)
    assert.ok(TICKET_STATUS_COLORS[s], `couleur manquante pour ${s}`)
  }
})

test("statusOrder respecte l'entonnoir, pas l'alphabet", () => {
  assert.ok(statusOrder('nouveau') < statusOrder('planifie'))
  // « resolu » (r) vient AVANT « cloture » (c) dans l'entonnoir — l'inverse
  // de l'ordre alphabétique.
  assert.ok(statusOrder('resolu') < statusOrder('cloture'))
  assert.equal(statusOrder('inconnu'), TICKET_STATUSES.length)
})

test('sortTickets trie par statut dans l\'ordre funnel', () => {
  const rows = [
    { id: 1, statut: 'cloture' },
    { id: 2, statut: 'nouveau' },
    { id: 3, statut: 'en_cours' },
  ]
  assert.deepEqual(sortTickets(rows, 'statut', 'asc').map(r => r.id), [2, 3, 1])
})

test('filterTickets : ouverts par défaut, statut, sous-garantie, recherche', () => {
  const rows = [
    { id: 1, reference: 'SAV-1', statut: 'nouveau', type: 'correctif', annule: false, sous_garantie_effectif: 'oui' },
    { id: 2, reference: 'SAV-2', statut: 'cloture', type: 'preventif', annule: false, sous_garantie_effectif: 'non' },
    { id: 3, reference: 'SAV-3', statut: 'en_cours', type: 'correctif', annule: true, sous_garantie_effectif: 'oui' },
  ]
  // Par défaut : ouverts et non annulés → 1 seulement (3 est annulé, 2 clôturé).
  assert.deepEqual(filterTickets(rows, EMPTY_TICKET_FILTERS).map(r => r.id), [1])
  // Tous.
  assert.equal(filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous' }).length, 3)
  // Par sous-garantie effective.
  assert.deepEqual(
    filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous', sous_garantie: 'non' }).map(r => r.id), [2])
  // Recherche.
  assert.deepEqual(
    filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous', q: 'sav-2' }).map(r => r.id), [2])
})

// ── N58 — couche de configuration des libellés/ordre (purement affichage) ──
test('applyTicketStatutConfig surcharge libellé & ordre sans toucher aux clés', () => {
  assert.equal(statusLabel('nouveau'), 'Nouveau')
  applyTicketStatutConfig([
    { cle: 'nouveau', libelle: 'À traiter', ordre: 9, actif: true },
    { cle: 'cloture', libelle: 'Fermé', ordre: 0, actif: true },
  ])
  assert.equal(statusLabel('nouveau'), 'À traiter')
  assert.equal(statusLabel('cloture'), 'Fermé')
  assert.ok(statusOrder('cloture') < statusOrder('nouveau'))
  // Clés canoniques figées (machine à états intacte).
  assert.deepEqual(TICKET_STATUSES, [
    'nouveau', 'planifie', 'en_cours', 'resolu', 'cloture',
  ])
  // Réinitialisation → défauts byte-identiques.
  applyTicketStatutConfig(null)
  assert.equal(statusLabel('nouveau'), 'Nouveau')
  assert.ok(statusOrder('nouveau') < statusOrder('cloture'))
})
