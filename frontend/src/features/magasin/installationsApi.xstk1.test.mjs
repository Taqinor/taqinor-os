import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// XSTK1 — verrouille le CONTRAT REST des endpoints Magasin (bin-locations,
// bin-affectations, putaways, pick-lists, pick-list-lignes, colis,
// colis-lignes) câblés dans `installationsApi.js`. Chaque route a été vérifiée
// comme EXISTANTE côté backend (apps/installations/urls.py + views/
// bin_location.py, putaway.py, picklist.py, colisage.py). Toute dérive d'URL
// casse ce test. On relit la source (pas de mock ESM — le module importe
// `./axios` avec effets de bord) et on verrouille le contrat textuel.

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, '..', '..', 'api', 'installationsApi.js'), 'utf8')

test('getBinLocations -> GET /installations/bin-locations/', () => {
  assert.match(src, /getBinLocations:[\s\S]*?api\.get\('\/installations\/bin-locations\/'/)
})

test('createBinLocation -> POST /installations/bin-locations/', () => {
  assert.match(src, /createBinLocation:[\s\S]*?api\.post\('\/installations\/bin-locations\/'/)
})

test('getBinAffectations -> GET /installations/bin-affectations/', () => {
  assert.match(src, /getBinAffectations:[\s\S]*?api\.get\('\/installations\/bin-affectations\/'/)
})

test('getPutAways -> GET /installations/putaways/', () => {
  assert.match(src, /getPutAways:[\s\S]*?api\.get\('\/installations\/putaways\/'/)
})

test('createPutAway -> POST /installations/putaways/', () => {
  assert.match(src, /createPutAway:[\s\S]*?api\.post\('\/installations\/putaways\/'/)
})

test('rangerPutAway -> POST putaways/<id>/ranger/ (bin optionnel)', () => {
  assert.match(src, /rangerPutAway:[\s\S]*?api\.post\(`\/installations\/putaways\/\$\{id\}\/ranger\/`/)
})

test('getPickLists -> GET /installations/pick-lists/', () => {
  assert.match(src, /getPickLists:[\s\S]*?api\.get\('\/installations\/pick-lists\/'/)
})

test('demarrerPickList -> POST pick-lists/<id>/demarrer/', () => {
  assert.match(src, /demarrerPickList:[\s\S]*?api\.post\(`\/installations\/pick-lists\/\$\{id\}\/demarrer\/`/)
})

test('terminerPickList -> POST pick-lists/<id>/terminer/', () => {
  assert.match(src, /terminerPickList:[\s\S]*?api\.post\(`\/installations\/pick-lists\/\$\{id\}\/terminer\/`/)
})

test('updatePickListLigne -> PATCH pick-list-lignes/<id>/', () => {
  assert.match(src, /updatePickListLigne:[\s\S]*?api\.patch\(`\/installations\/pick-list-lignes\/\$\{id\}\/`/)
})

test('getColisList -> GET /installations/colis/', () => {
  assert.match(src, /getColisList:[\s\S]*?api\.get\('\/installations\/colis\/'/)
})

test('controlerColis -> POST colis/<id>/controler/', () => {
  assert.match(src, /controlerColis:[\s\S]*?api\.post\(`\/installations\/colis\/\$\{id\}\/controler\/`/)
})

test('expedierColis -> POST colis/<id>/expedier/', () => {
  assert.match(src, /expedierColis:[\s\S]*?api\.post\(`\/installations\/colis\/\$\{id\}\/expedier\/`/)
})

test('getColisLignes -> GET /installations/colis-lignes/', () => {
  assert.match(src, /getColisLignes:[\s\S]*?api\.get\('\/installations\/colis-lignes\/'/)
})

test('createColisLigne -> POST /installations/colis-lignes/', () => {
  assert.match(src, /createColisLigne:[\s\S]*?api\.post\('\/installations\/colis-lignes\/'/)
})

test('aucune fuite prix d’achat / marge côté client dans les chemins Magasin', () => {
  assert.doesNotMatch(src, /prix[-_]achat/)
})
