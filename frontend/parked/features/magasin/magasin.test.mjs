// Run: node --test src/features/magasin/magasin.test.mjs
//
// Correction adversariale (revue orchestrateur) : ce fichier importait
// `describe/it/expect` depuis `'vitest'` et `./magasin` SANS extension — deux
// erreurs sous `node --test`/ESM strict (vitest exclut `*.test.mjs` de son
// propre glob `include`, et Node exige l'extension explicite sur un import
// relatif). Le fichier ne s'exécutait donc JAMAIS ni sous vitest ni sous
// node --test. Convention correcte alignée sur
// `frontend/src/features/messaging/mentions.test.mjs` : `node:test` +
// `node:assert/strict` + import `./magasin.js` explicite.
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  optionsFrom, buildBinTree, countBinsInTree, sortPickListLignesByBin,
  pickListProgress, colisProgress, PUTAWAY_STATUTS,
} from './magasin.js'

/* Tests purs du module Magasin (XSTK1) : arborescence des casiers, tri des
   lignes de prélèvement par casier, progressions pick-list/colis. Aucune
   dépendance React — vérifie la logique en isolation du rendu. */

test('optionsFrom : transforme un map de statuts en options {value,label}', () => {
  assert.deepEqual(
    optionsFrom(PUTAWAY_STATUTS).find((o) => o.value === 'range'),
    { value: 'range', label: 'Rangé' },
  )
})

const bins = [
  { id: 1, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '01', code: 'A-01-01', archived: false },
  { id: 2, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '02', code: 'A-01-02', archived: false },
  { id: 3, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'B', allee: '01', casier: '01', code: 'B-01-01', archived: false },
  { id: 4, emplacement: 20, emplacement_nom: 'Camionnette 1', zone: null, allee: null, casier: null, code: 'CAM1', archived: false },
  { id: 5, emplacement: 10, emplacement_nom: 'Dépôt central', zone: 'A', allee: '01', casier: '03', code: 'A-01-03', archived: true },
]

test('buildBinTree : regroupe emplacement -> zone -> allée -> casiers', () => {
  const tree = buildBinTree(bins)
  assert.equal(tree.length, 2)
  const depot = tree.find((e) => e.label === 'Dépôt central')
  assert.equal(depot.zones.length, 2)
  const zoneA = depot.zones.find((z) => z.label === 'A')
  assert.equal(zoneA.allees.length, 1)
  assert.equal(zoneA.allees[0].bins.length, 2) // A-01-01, A-01-02 (archivé exclu)
})

test('buildBinTree : exclut les casiers archivés par défaut', () => {
  const tree = buildBinTree(bins)
  assert.equal(countBinsInTree(tree), 4)
})

test('buildBinTree : inclut les casiers archivés avec includeArchived', () => {
  const tree = buildBinTree(bins, { includeArchived: true })
  assert.equal(countBinsInTree(tree), 5)
})

test('buildBinTree : tolère une liste vide/undefined', () => {
  assert.deepEqual(buildBinTree(), [])
  assert.deepEqual(buildBinTree(null), [])
  assert.equal(countBinsInTree(undefined), 0)
})

test('buildBinTree : gère les casiers sans zone/allée (regroupement "Sans zone"/"Sans allée")', () => {
  const tree = buildBinTree(bins)
  const camionnette = tree.find((e) => e.label === 'Camionnette 1')
  assert.equal(camionnette.zones[0].label, 'Sans zone')
  assert.equal(camionnette.zones[0].allees[0].label, 'Sans allée')
})

test('sortPickListLignesByBin : trie par ordre croissant, les lignes sans ordre en dernier', () => {
  const lignes = [
    { id: 3, ordre: undefined },
    { id: 1, ordre: 5 },
    { id: 2, ordre: 1 },
  ]
  const sorted = sortPickListLignesByBin(lignes)
  assert.deepEqual(sorted.map((l) => l.id), [2, 1, 3])
})

test('sortPickListLignesByBin : ne mute pas le tableau original', () => {
  const lignes = [{ id: 1, ordre: 2 }, { id: 2, ordre: 1 }]
  const copy = [...lignes]
  sortPickListLignesByBin(lignes)
  assert.deepEqual(lignes, copy)
})

test('sortPickListLignesByBin : tolère undefined', () => {
  assert.deepEqual(sortPickListLignesByBin(), [])
})

test('pickListProgress : compte les lignes prélevées', () => {
  const lignes = [{ preleve: true }, { preleve: false }, { preleve: true }]
  assert.deepEqual(pickListProgress(lignes), { done: 2, total: 3, pct: 67 })
})

test('pickListProgress : renvoie 0% pour une liste vide', () => {
  assert.deepEqual(pickListProgress([]), { done: 0, total: 0, pct: 0 })
  assert.deepEqual(pickListProgress(), { done: 0, total: 0, pct: 0 })
})

test('colisProgress : compte les lignes contrôlées', () => {
  const lignes = [{ controle_ok: true }, { controle_ok: true }]
  assert.deepEqual(colisProgress(lignes), { done: 2, total: 2, pct: 100 })
})

test('colisProgress : tolère undefined', () => {
  assert.deepEqual(colisProgress(), { done: 0, total: 0, pct: 0 })
})
