// WIR230/FG88 — 4e vue « Tournée » de ContratsMaintenance : ordonnancement GPS
// serveur (savApi.getTourneePreventive) + affectation en lot
// (savApi.planifierTournee, body exact {ticket_ids, date_tournee,
// technicien_id}), erreur FR affichée. Vérification de SOURCE (JSX, pas de
// node_modules installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/sav/ContratsMaintenanceTournee.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ContratsMaintenance.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '..', '..', 'api', 'savApi.js'), 'utf8')

test('savApi expose getTourneePreventive et planifierTournee (WIR230)', () => {
  assert.match(API_SRC, /getTourneePreventive: \(params\) =>\s*\n?\s*api\.get\('\/sav\/contrats-maintenance\/tournee\/', \{ params \}\)/)
  assert.match(API_SRC, /planifierTournee: \(body\) =>\s*\n?\s*api\.post\('\/sav\/contrats-maintenance\/planifier-tournee\/', body\)/)
})

test('la vue "tournee" existe dans le segmenté', () => {
  assert.match(SRC, /value: 'tournee', label: 'Tournée'/)
})

test('planifierTournee envoie exactement {ticket_ids, date_tournee, technicien_id}', () => {
  const body = SRC.slice(SRC.indexOf('const planifierTournee = async'), SRC.indexOf('const columns ='))
  assert.match(body, /savApi\.planifierTournee\(\{/)
  assert.match(body, /ticket_ids: tourneeSelection/)
  assert.match(body, /date_tournee: tourneeDate/)
  assert.match(body, /technicien_id: tourneeTechnicien \|\| null/)
})

test("l'ordre serveur n'est jamais retrié côté écran (aucun .sort sur `tournee`)", () => {
  const listBody = SRC.slice(SRC.indexOf("data-testid=\"tournee-liste\""), SRC.indexOf('</ul>'))
  assert.doesNotMatch(listBody, /\.sort\(/)
  assert.match(listBody, /tournee\.map/)
})

test('erreur FR affichée via frenchError, jamais un message générique brut', () => {
  assert.match(SRC, /setTourneeError\(frenchError\(err, 'Impossible de charger la tournée\.'\)\)/)
  assert.match(SRC, /toast\.error\(frenchError\(err, 'Impossible de planifier la tournée\.'\)\)/)
  const errorBlock = SRC.slice(SRC.indexOf('{tourneeError && ('), SRC.indexOf('{tourneeError && (') + 400)
  assert.match(errorBlock, /role="alert"/)
  assert.match(errorBlock, /\{tourneeError\}/)
})

test('le bouton Planifier est désactivé sans sélection ni date', () => {
  const body = SRC.slice(SRC.indexOf('onClick={planifierTournee}'), SRC.indexOf('onClick={planifierTournee}') + 200)
  assert.match(body, /disabled=\{!tourneeSelection\.length \|\| !tourneeDate \|\| tourneePlanifiant\}/)
})
