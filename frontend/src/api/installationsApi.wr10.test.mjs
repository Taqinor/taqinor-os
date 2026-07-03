import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// WR10 — verrouille le CONTRAT REST des endpoints de planification/logistique
// installations câblés par cette lane. Chaque chemin a été vérifié comme
// EXISTANT côté backend (apps/installations : InstallationViewSet /
// InterventionViewSet @action + selectors). Toute dérive d'URL (ou un retour à
// un endpoint inventé) casse ce test. On relit la source de l'API et on vérifie
// les chaînes d'URL exactes — le module importe `./axios` (effets de bord), on
// ne mocke donc pas le graphe ESM, on verrouille le contrat textuel.

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'installationsApi.js'), 'utf8')

test('FG74 — getGanttChantiers → GET /installations/chantiers/gantt/', () => {
  assert.match(src, /getGanttChantiers:[\s\S]*?api\.get\('\/installations\/chantiers\/gantt\/'\)/)
})

test('N43 — getRegimeSuggestion → GET /installations/chantiers/regime-suggestion/ ?kwc=', () => {
  assert.match(src, /getRegimeSuggestion:[\s\S]*?'\/installations\/chantiers\/regime-suggestion\/'/)
  assert.match(src, /getRegimeSuggestion:[\s\S]*?params:\s*\{\s*kwc\s*\}/)
})

test('FG79 — creerInterventionsStandard → POST chantiers/<id>/creer-interventions-standard/', () => {
  assert.match(src, /creerInterventionsStandard:[\s\S]*?api\.post\(`\/installations\/chantiers\/\$\{id\}\/creer-interventions-standard\/`/)
})

test('FG71 — getChantierCout → GET chantiers/<id>/cout/ (tarif_jour optionnel)', () => {
  assert.match(src, /getChantierCout:[\s\S]*?api\.get\(`\/installations\/chantiers\/\$\{id\}\/cout\/`/)
  assert.match(src, /getChantierCout:[\s\S]*?tarif_jour: tarifJour/)
})

test('FG68 — getCalendrierInterventions → GET interventions/calendrier/ ?date_from&date_to', () => {
  assert.match(src, /getCalendrierInterventions:[\s\S]*?'\/installations\/interventions\/calendrier\/'/)
  assert.match(src, /date_from: dateFrom, date_to: dateTo/)
})

test('FG73 — getMaTournee → GET interventions/ma-tournee/ ?date', () => {
  assert.match(src, /getMaTournee:[\s\S]*?'\/installations\/interventions\/ma-tournee\/'/)
})

test('FG299 — getPlanDeCharge → GET interventions/plan-de-charge/', () => {
  assert.match(src, /getPlanDeCharge:[\s\S]*?'\/installations\/interventions\/plan-de-charge\/'/)
})

test('FG300 — getConflitsAffectation → GET interventions/conflits-affectation/', () => {
  assert.match(src, /getConflitsAffectation:[\s\S]*?'\/installations\/interventions\/conflits-affectation\/'/)
})

test('FG301 — getNivellementCharge → GET interventions/nivellement-charge/', () => {
  assert.match(src, /getNivellementCharge:[\s\S]*?'\/installations\/interventions\/nivellement-charge\/'/)
})

test('FG303 — getPlanningCamionnettes → GET interventions/planning-camionnettes/', () => {
  assert.match(src, /getPlanningCamionnettes:[\s\S]*?'\/installations\/interventions\/planning-camionnettes\/'/)
})

test('aucune fuite prix d’achat / marge côté client dans les chemins WR10', () => {
  // Le seul endpoint qui touche à la marge (cout) est admin-only côté backend ;
  // aucune URL de ce module ne doit exposer un endpoint « prix-achat ».
  assert.doesNotMatch(src, /prix[-_]achat/)
})
