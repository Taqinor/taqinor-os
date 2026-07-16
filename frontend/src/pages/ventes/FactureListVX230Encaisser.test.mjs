// VX230 — Encaisser LÀ où on chasse l'impayé + total « reste à encaisser ».
// La modale de paiement est extraite en PaiementDialog PARTAGÉ, montée depuis
// FactureList ET RelancesPage ; une carte « Reste à encaisser (onglet) » dérive
// de `filtered` (zéro appel réseau). Test SOURCE (aucun node_modules ici).
//   node --test src/pages/ventes/FactureListVX230Encaisser.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIALOG = readFileSync(join(HERE, 'PaiementDialog.jsx'), 'utf8')
const FACTURE_LIST = readFileSync(join(HERE, 'FactureList.jsx'), 'utf8')
const RELANCES = readFileSync(join(HERE, 'RelancesPage.jsx'), 'utf8')

test('VX230 : PaiementDialog est un composant PARTAGÉ (props facture / onOpenChange / onSaved)', () => {
  assert.match(DIALOG, /export default function PaiementDialog\(\{ facture, onOpenChange, onSaved \}\)/)
  // Le flux d'enregistrement + le rafraîchissement parent + l'arrondi ZFAC11
  // ont bien suivi la modale.
  assert.match(DIALOG, /ventesApi\.enregistrerPaiement\(facture\.id/)
  assert.match(DIALOG, /onSaved\?\.\(\)/)
  assert.match(DIALOG, /ventesApi\.arrondiCaisseFacture\(facture\.id, 'especes'\)/)
})

test('VX230 : PaiementDialog se (ré)initialise à chaque nouvelle facture ciblée', () => {
  assert.match(DIALOG, /useEffect\(\(\) => \{\s*if \(!facture\) return/)
  assert.match(DIALOG, /\}, \[facture\?\.id\]\)/)
})

test('VX230 : FactureList monte le PaiementDialog partagé et rafraîchit la liste au save', () => {
  assert.match(FACTURE_LIST, /import PaiementDialog from '\.\/PaiementDialog'/)
  assert.match(FACTURE_LIST, /<PaiementDialog[\s\S]{0,160}facture=\{payTarget\}/)
  assert.match(FACTURE_LIST, /onSaved=\{\(\) => dispatch\(fetchFactures\(\)\)\}/)
  // La modale locale (et ses constantes) ne vit plus ici.
  assert.doesNotMatch(FACTURE_LIST, /const handleEnregistrerPaiement/)
  assert.doesNotMatch(FACTURE_LIST, /const MODES_PAIEMENT/)
})

test('VX230 : carte « Reste à encaisser (onglet) » dérivée de `filtered` (zéro réseau)', () => {
  assert.match(FACTURE_LIST, /const resteAEncaisserOnglet = useMemo\(\s*\(\) => filtered\.reduce/)
  assert.match(FACTURE_LIST, /Reste à encaisser \(onglet\)/)
})

test('VX230 : RelancesPage propose « Encaisser » et monte la MÊME modale, rechargée au save', () => {
  assert.match(RELANCES, /import PaiementDialog from '\.\/PaiementDialog'/)
  assert.match(RELANCES, /onClick=\{\(\) => setPayTarget\(r\)\}/)
  assert.match(RELANCES, /Encaisser/)
  assert.match(RELANCES, /<PaiementDialog[\s\S]{0,160}facture=\{payTarget\}[\s\S]{0,120}onSaved=\{load\}/)
})
