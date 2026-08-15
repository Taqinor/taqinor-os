// WIR233 — SAV finitions : (a) « Facturer maintenant » depuis
// ContratsMaintenance (contrats facturation_active, sort du cul-de-sac de la
// file d'exceptions XCTR5) et (b) section « Instructions » du ticket éditable
// (PATCH instructions) avec « Suggestions KB » (insertion sans écriture auto).
// Vérification de SOURCE (JSX, pas de node_modules installés dans ce lane —
// cf. SigneDialog.test.mjs).
//   node --test src/pages/sav/Wir233FinitionsSav.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CONTRATS_SRC = readFileSync(join(HERE, 'ContratsMaintenance.jsx'), 'utf8')
const TICKETS_SRC = readFileSync(join(HERE, 'TicketsPage.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '..', '..', 'api', 'savApi.js'), 'utf8')

test('savApi expose facturerContrat (WIR233)', () => {
  assert.match(API_SRC, /facturerContrat: \(id\) => api\.post\(`\/sav\/contrats-maintenance\/\$\{id\}\/facturer\/`\)/)
})

test('« Facturer maintenant » n\'apparaît que pour facturation_active et affiche la reference renvoyee', () => {
  assert.match(CONTRATS_SRC, /row\.facturation_active && \(/)
  assert.match(CONTRATS_SRC, /onClick=\{\(\) => facturerMaintenant\(row\)\}/)
  const body = CONTRATS_SRC.slice(
    CONTRATS_SRC.indexOf('const facturerMaintenant = async'),
    CONTRATS_SRC.indexOf('const columns ='),
  )
  assert.match(body, /savApi\.facturerContrat\(row\.id\)/)
  assert.match(body, /toast\.success\(`Facture \$\{data\.facture_reference\} émise\.`\)/)
  assert.match(body, /setDernieresFactures/)
})

test('la section Instructions PATCH `instructions` via updateTicket (jamais un endpoint dédié inventé)', () => {
  const body = TICKETS_SRC.slice(
    TICKETS_SRC.indexOf('const saveInstructions = async'),
    TICKETS_SRC.indexOf('const chargerSuggestionsKb'),
  )
  assert.match(body, /savApi\.updateTicket\(id, \{ instructions: instructionsText \}\)/)
})

test('les suggestions KB appellent getInstructionsSuggestions (existant, ZMFG5)', () => {
  const body = TICKETS_SRC.slice(
    TICKETS_SRC.indexOf('const chargerSuggestionsKb = async'),
    TICKETS_SRC.indexOf('const insererSuggestion'),
  )
  assert.match(body, /savApi\.getInstructionsSuggestions\(id\)/)
})

test('insérer une suggestion NE PATCH JAMAIS automatiquement (insertion pure, écran seulement)', () => {
  const body = TICKETS_SRC.slice(
    TICKETS_SRC.indexOf('const insererSuggestion = (article)'),
    TICKETS_SRC.indexOf('const insererSuggestion = (article)') + 300,
  )
  assert.doesNotMatch(body, /savApi\.updateTicket/)
  assert.match(body, /setInstructionsText/)
})

test('le bouton Insérer est câblé sur insererSuggestion dans la liste rendue', () => {
  assert.match(TICKETS_SRC, /data-testid="kb-suggestions-liste"/)
  assert.match(TICKETS_SRC, /onClick=\{\(\) => insererSuggestion\(a\)\}/)
})
