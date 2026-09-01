// WIR261 — cycle « complément d'information » (ZCTR8) enfin atteignable depuis
// l'onglet « Demandes ad-hoc » : les demandes `info_requested` restaient
// invisibles (seul `status=pending` était chargé), et automationApi exposait
// `demandeInfoApprovalRequest`/`resoumettreApprovalRequest`/
// `deleteApprovalRequestType` sans AUCUN appelant applicatif (dead code,
// couvert seulement par le test de SOURCE demandes-adhoc-wir62.test.mjs).
// Vérification de SOURCE (JSX, pas de node_modules dans ce lane — cf.
// demandes-adhoc-wir62.test.mjs).
//   node --test src/pages/approbations/demandes-adhoc-wir261.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE = readFileSync(join(HERE, 'ApprobationsPage.jsx'), 'utf8')

test('charge aussi les demandes info_requested (pas seulement pending)', () => {
  assert.match(PAGE, /getApprovalRequests\(\{ status: 'pending' \}\)/)
  assert.match(PAGE, /getApprovalRequests\(\{ status: 'info_requested' \}\)/)
  // Les deux listes sont fusionnées, jamais l'une au détriment de l'autre.
  assert.match(PAGE, /setDemandes\(\[\.\.\.pending, \.\.\.infoRequested\]\)/)
})

// « tests des 3 appels » (Done WIR261) : demander un complément, resoumettre,
// supprimer un type — les 3 appelants applicatifs manquants.
test('appel 1/3 — bouton « Demander un complément » (motif obligatoire)', () => {
  assert.match(PAGE, /const demanderComplement = async \(id\) => \{/)
  assert.match(PAGE, /automationApi\.demandeInfoApprovalRequest\(id, motif\.trim\(\)\)/)
  assert.match(PAGE, /Demander un complément/)
})

test('appel 2/3 — « Resoumettre » réservé au demandeur original, payload corrigé', () => {
  assert.match(PAGE, /const confirmResoumettre = async \(\) => \{/)
  assert.match(
    PAGE,
    /automationApi\.resoumettreApprovalRequest\(\s*resoumettreState\.demande\.id, resoumettreState\.values\)/,
  )
  // Visible SEULEMENT pour le demandeur original (jamais un tiers) — le
  // serveur refuserait de toute façon, mais le bouton ne doit pas être
  // proposé à qui ne peut pas s'en servir.
  assert.match(PAGE, /const mine = currentUserId != null && d\.demandeur === currentUserId/)
  assert.match(PAGE, /\{mine && \(/)
})

test('appel 3/3 — suppression d’un type (403 FR toléré, jamais un crash)', () => {
  assert.match(PAGE, /const supprimerType = async \(type\) => \{/)
  assert.match(PAGE, /automationApi\.deleteApprovalRequestType\(type\.id\)/)
  assert.match(
    PAGE,
    /toast\.error\(err\?\.response\?\.data\?\.detail \|\| 'Suppression impossible \(réservé admin \?\)\.'\)/,
  )
})

test('une demande info_requested reste visible et affiche son motif', () => {
  assert.match(PAGE, /const infoRequested = d\.status === 'info_requested'/)
  assert.match(PAGE, /Motif du complément : \{d\.decision_note\}/)
})
