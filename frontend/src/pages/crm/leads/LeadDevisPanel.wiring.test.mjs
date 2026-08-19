// Garde de non-régression — CI run 32200473257 (PR #538, devis.spec.js E4).
// `LeadDevisPanel.jsx` (et `DevisGenerator.jsx`, même bug) appelaient
// `stockApi.getProduits()` SANS paramètre pour charger le catalogue avant un
// devis automatique — page 1 SEULE (`StandardPagination.page_size = 50`,
// `ProduitViewSet.ordering = ['nom']`). La trace réseau du run rouge le
// prouve : `{"count":101,"next":".../produits/?page=2", ...}`, les DEUX
// « Panneau … » tombant en page 2 — invisibles à `autoFillLines`, d'où
// « Devis auto impossible : aucun panneau du stock ne correspond ». Le
// correctif utilise `fetchAllPages` (VX54, déjà le chemin de
// `stockSlice.js`). Ce test lit le SOURCE (JSX non exécutable ici sans
// node_modules) pour verrouiller que le fil ne régresse pas vers l'appel nu.
//
// Run : node --test src/pages/crm/leads/LeadDevisPanel.wiring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

// Ne garde que le CODE : une ligne de commentaire (// …) peut légitimement
// NOMMER l'ancien appel nu pour mémoire (voir les deux fichiers) sans que ce
// soit une régression — seul le code réel doit être absent.
const codeSansCommentaires = (src) => src
  .split('\n')
  .filter((ligne) => !ligne.trim().startsWith('//'))
  .join('\n')

const LDP = read('LeadDevisPanel.jsx')
const DG = read('../../ventes/DevisGenerator.jsx')
const LDP_CODE = codeSansCommentaires(LDP)
const DG_CODE = codeSansCommentaires(DG)

test('LeadDevisPanel importe fetchAllPages (VX54)', () => {
  assert.match(LDP, /import\s*\{\s*fetchAllPages\s*\}\s*from\s*'\.\.\/\.\.\/\.\.\/utils\/fetchAllPages'/)
})

test('LeadDevisPanel ne rappelle plus stockApi.getProduits() SANS paramètre (code réel, hors commentaires)', () => {
  // On tolère `stockApi.getProduits({ page })` (celui que fetchAllPages
  // construit) — seul l'appel NU (sans argument) est banni.
  assert.doesNotMatch(LDP_CODE, /stockApi\.getProduits\(\)/)
  assert.match(LDP_CODE, /fetchAllPages\(\s*\n?\s*\(page\)\s*=>\s*stockApi\.getProduits\(\{\s*page\s*\}\)/)
})

test('DevisGenerator importe fetchAllPages (VX54) — même bug, même correctif', () => {
  assert.match(DG, /import\s*\{\s*fetchAllPages\s*\}\s*from\s*'\.\.\/\.\.\/utils\/fetchAllPages'/)
})

test('DevisGenerator ne rappelle plus stockApi.getProduits() SANS paramètre (code réel, hors commentaires)', () => {
  assert.doesNotMatch(DG_CODE, /stockApi\.getProduits\(\)/)
  assert.match(DG_CODE, /fetchAllPages\(\(page\)\s*=>\s*stockApi\.getProduits\(\{\s*page\s*\}\)/)
})
