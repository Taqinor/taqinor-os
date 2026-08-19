// PVORD (fondateur 19/08/2026) — réordonnancement manuel des lignes de devis
// dans l'éditeur (monter/descendre). DevisLineRow.jsx/DevisGenerator.jsx sont
// du JSX non exécutable par `node --test` sans node_modules (React, dnd) :
// ce test lit donc le SOURCE, même patron que LeadDevisPanel.wiring.test.mjs.
//
// Verrouille :
//  1. DevisGenerator.jsx expose un `moveLine` qui mute l'ORDRE du tableau
//     `lines` (jamais son contenu), et passe l'index de rendu (i) au tableau
//     pour calculer canMoveUp/canMoveDown.
//  2. DevisLineRow reçoit/rend les boutons monter/descendre, désactivés en
//     butée (baseline accessible : boutons natifs, pas de drag requis).
//  3. `areEqual` (memo) inclut les nouvelles props — sinon une ligne
//     déplacée garderait des boutons monter/descendre PÉRIMÉS.
//
// Run : node --test src/pages/ventes/DevisLineRowReorder.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const DG = read('DevisGenerator.jsx')
const ROW = read('DevisLineRow.jsx')

test('DevisGenerator : moveLine mute l\'ordre du tableau lines (splice, jamais un id backend)', () => {
  assert.match(DG, /const moveLine = useCallback\(\(key, delta\) => setLines\(ls => \{/)
  assert.match(DG, /copy\.splice\(idx, 1\)/)
  assert.match(DG, /copy\.splice\(target, 0, item\)/)
})

test('DevisGenerator : lines.map reçoit l\'index de rendu pour canMoveUp/canMoveDown', () => {
  assert.match(DG, /lines\.map\(\(l, i\) => \(/)
  assert.match(DG, /canMoveUp=\{i > 0\}/)
  assert.match(DG, /canMoveDown=\{i < lines\.length - 1\}/)
})

test('DevisGenerator : DevisLineRow reçoit onMoveUp/onMoveDown', () => {
  assert.match(DG, /onMoveUp=\{moveLineUp\}/)
  assert.match(DG, /onMoveDown=\{moveLineDown\}/)
})

test('DevisGenerator : la table porte une colonne Ordre (thead)', () => {
  assert.match(DG, /<th className="col-ordre"/)
})

test('DevisLineRow : les props canMoveUp/canMoveDown/onMoveUp/onMoveDown sont déclarées', () => {
  assert.match(ROW, /canMoveUp,\s*\n\s*canMoveDown,\s*\n\s*onMoveUp,\s*\n\s*onMoveDown,/)
})

test('DevisLineRow : les DEUX boutons (monter ET descendre) sont rendus, désactivés en butée', () => {
  assert.match(ROW, /label="Monter la ligne"[\s\S]{0,60}disabled=\{!canMoveUp\}/)
  assert.match(ROW, /label="Descendre la ligne"[\s\S]{0,60}disabled=\{!canMoveDown\}/)
})

test('DevisLineRow : les boutons appellent onMoveUp/onMoveDown avec la CLÉ de ligne (pas la ligne entière)', () => {
  assert.match(ROW, /onClick=\{\(\) => onMoveUp\(l\._key\)\}/)
  assert.match(ROW, /onClick=\{\(\) => onMoveDown\(l\._key\)\}/)
})

test('DevisLineRow : les boutons de réordonnancement sont rendus pour la ligne PRODUIT et la ligne SECTION/NOTE', () => {
  const occurrences = ROW.match(/\{reorderButtons\}/g) || []
  assert.equal(occurrences.length, 2,
    'reorderButtons doit être rendu deux fois : branche section/note ET branche produit')
})

test('DevisLineRow : areEqual (memo) compare bien les 4 nouvelles props (sinon memo périmé après déplacement)', () => {
  const areEqualBlock = ROW.slice(ROW.indexOf('function areEqual'))
  assert.match(areEqualBlock, /prev\.canMoveUp === next\.canMoveUp/)
  assert.match(areEqualBlock, /prev\.canMoveDown === next\.canMoveDown/)
  assert.match(areEqualBlock, /prev\.onMoveUp === next\.onMoveUp/)
  assert.match(areEqualBlock, /prev\.onMoveDown === next\.onMoveDown/)
})

test('DevisLineRow : ChevronUp/ChevronDown importés de lucide-react', () => {
  assert.match(ROW, /import\s*\{\s*Trash2,\s*ChevronUp,\s*ChevronDown\s*\}\s*from\s*'lucide-react'/)
})
