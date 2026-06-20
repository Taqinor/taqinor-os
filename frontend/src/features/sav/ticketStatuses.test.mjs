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
  isStatusTransitionAllowed,
  ticketAgeDays,
  slaThresholdDays,
  ticketSlaLevel,
  statusCounts,
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

// ── L296 — garde de transition de statut ─────────────────────────────────────
test('isStatusTransitionAllowed bloque les sauts en avant hors ordre', () => {
  // Saut nouveau → clôturé (3 étapes) bloqué.
  assert.equal(isStatusTransitionAllowed('nouveau', 'cloture'), false)
  // Une seule étape en avant autorisée.
  assert.equal(isStatusTransitionAllowed('nouveau', 'planifie'), true)
  assert.equal(isStatusTransitionAllowed('planifie', 'en_cours'), true)
  // Reculer autorisé.
  assert.equal(isStatusTransitionAllowed('resolu', 'nouveau'), true)
  // Rester / vide / inconnu : permissif.
  assert.equal(isStatusTransitionAllowed('en_cours', 'en_cours'), true)
  assert.equal(isStatusTransitionAllowed('', 'cloture'), true)
  assert.equal(isStatusTransitionAllowed('nouveau', 'inconnu'), true)
})

// ── L298 — âge / SLA ─────────────────────────────────────────────────────────
test('ticketAgeDays compte les jours depuis date_ouverture', () => {
  const now = new Date('2026-06-19T12:00:00')
  assert.equal(ticketAgeDays({ date_ouverture: '2026-06-09' }, now), 10)
  // Repli sur date_creation.
  assert.equal(ticketAgeDays({ date_creation: '2026-06-18T08:00:00' }, now), 1)
  // Aucune date → null.
  assert.equal(ticketAgeDays({}, now), null)
})

test('slaThresholdDays raccourcit pour haute/urgente', () => {
  assert.equal(slaThresholdDays('urgente'), 2)
  assert.equal(slaThresholdDays('haute'), 5)
  assert.equal(slaThresholdDays('normale'), 10)
})

test('ticketSlaLevel escalade les ouverts en retard, ignore les autres', () => {
  const now = new Date('2026-06-19T12:00:00')
  // Urgent ouvert depuis 3 j (seuil 2) → late.
  assert.equal(ticketSlaLevel(
    { statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-06-16' }, now), 'late')
  // Normal ouvert depuis 1 j → ok.
  assert.equal(ticketSlaLevel(
    { statut: 'nouveau', priorite: 'normale', date_ouverture: '2026-06-18' }, now), 'ok')
  // Clôturé : jamais d'escalade.
  assert.equal(ticketSlaLevel(
    { statut: 'cloture', priorite: 'urgente', date_ouverture: '2026-01-01' }, now), 'ok')
  // Annulé : jamais d'escalade.
  assert.equal(ticketSlaLevel(
    { statut: 'nouveau', annule: true, priorite: 'urgente', date_ouverture: '2026-01-01' }, now), 'ok')
})

// ── L304/L305 — filtres annulé & urgent+garantie ─────────────────────────────
test('filterTickets : annule=only/sans et urgent_garantie', () => {
  const rows = [
    { id: 1, statut: 'nouveau', priorite: 'urgente', annule: false, sous_garantie_effectif: 'oui' },
    { id: 2, statut: 'en_cours', priorite: 'normale', annule: true, sous_garantie_effectif: 'oui' },
    { id: 3, statut: 'nouveau', priorite: 'basse', annule: false, sous_garantie_effectif: 'non' },
  ]
  // Annulés seulement.
  assert.deepEqual(
    filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous', annule: 'only' }).map(r => r.id), [2])
  // Sans annulés.
  assert.deepEqual(
    filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous', annule: 'sans' }).map(r => r.id), [1, 3])
  // Urgent & sous garantie.
  assert.deepEqual(
    filterTickets(rows, { ...EMPTY_TICKET_FILTERS, ouvert: 'tous', urgent_garantie: true }).map(r => r.id), [1])
})

// ── L306/L314 — comptes par statut ───────────────────────────────────────────
test('statusCounts retourne les 5 statuts triés funnel', () => {
  const rows = [
    { statut: 'cloture' }, { statut: 'nouveau' }, { statut: 'nouveau' },
    { statut: 'en_cours' }, { statut: 'inconnu' },
  ]
  const c = statusCounts(rows)
  assert.deepEqual(c.map((x) => x.key), TICKET_STATUSES)
  assert.equal(c.find((x) => x.key === 'nouveau').count, 2)
  assert.equal(c.find((x) => x.key === 'en_cours').count, 1)
  assert.equal(c.find((x) => x.key === 'cloture').count, 1)
  assert.equal(c.find((x) => x.key === 'resolu').count, 0)
})
