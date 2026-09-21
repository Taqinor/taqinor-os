// WIR180 — télédéclarations DGI invisibles (SIMPL-TVA, SIMPL-IS, loi 69-21).
// Test SOURCE (comme FiscalitePage.vx158.test.mjs) : vérifie le câblage des 3
// wrappers blob + leurs points d'entrée écran, sans monter React (évite la
// dépendance au harnais de rendu / mocks lourds de comptaApi).
//   node --test src/features/compta/wir180.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const API_SRC = readFileSync(join(HERE, '../../api/comptaApi.js'), 'utf8')
const FISCALITE_SRC = readFileSync(join(HERE, 'pages/FiscalitePage.jsx'), 'utf8')
const ETATS_SRC = readFileSync(join(HERE, 'pages/EtatsPage.jsx'), 'utf8')

test('comptaApi : declarationsTva.exportSimpl télécharge le XML SIMPL-TVA par déclaration', () => {
  assert.match(API_SRC, /exportSimpl: \(id\) =>/)
  assert.match(API_SRC, /\/compta\/declarations-tva\/\$\{id\}\/export-simpl\//)
})

test('comptaApi : etats.exportSimplIs télécharge le XML SIMPL-IS d’un exercice', () => {
  assert.match(API_SRC, /exportSimplIs: \(params\) =>/)
  assert.match(API_SRC, /\/compta\/etats\/export-simpl-is\//)
})

test('comptaApi : etats.loi6921 lit le rapport loi 69-21 (export CSV générique)', () => {
  assert.match(API_SRC, /loi6921: \(params\) => api\.get\('\/compta\/etats\/loi-69-21\/'/)
})

test('FiscalitePage : action de ligne SIMPL-TVA sur l’onglet Déclarations TVA', () => {
  assert.match(FISCALITE_SRC, /id: 'simpl-tva'/)
  assert.match(FISCALITE_SRC, /comptaApi\.declarationsTva\.exportSimpl\(row\.id\)/)
})

test('FiscalitePage : export SIMPL-IS dans le bloc Exports (exercice requis, avec hint)', () => {
  const exportsBlock = FISCALITE_SRC.match(/const EXPORTS = \[([\s\S]*?)\n\]/)[1]
  assert.match(exportsBlock, /key: 'exportSimplIs'/)
  assert.match(exportsBlock, /fn: comptaApi\.etats\.exportSimplIs/)
  assert.match(exportsBlock, /needsExercice: true/)
  // La même entrée doit porter son `hint` (garde VX158(b) déjà existante).
  const entryStart = exportsBlock.indexOf("key: 'exportSimplIs'")
  const entrySlice = exportsBlock.slice(entryStart, entryStart + 300)
  assert.match(entrySlice, /hint: '[^']+'/)
})

test('EtatsPage : entrée loi-69-21 dans le sélecteur ETATS', () => {
  assert.match(ETATS_SRC, /value: 'loi-69-21'/)
  assert.match(ETATS_SRC, /fetch: comptaApi\.etats\.loi6921/)
})
