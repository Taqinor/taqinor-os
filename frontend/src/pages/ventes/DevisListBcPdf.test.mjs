// FE-ZSAL8 — bouton « Bon de commande (PDF) » dans le menu « ⋯ » d'une ligne
// devis, quand un BC existe (`d.bon_commande_etat.exists`). Le client
// `ventesApi.getBonCommandePdf` existait déjà (jamais appelé côté UI) ;
// endpoint backend GET /ventes/bons-commande/<id>/pdf/ déjà en place — aucun
// nouveau chemin PDF (règle #4, ne concerne que le devis /proposal).
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisListBcPdf.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('ZSAL8 : le menu « ⋯ » propose « Bon de commande (PDF) » quand un BC existe', () => {
  assert.match(SRC, /d\.bon_commande_etat\?\.exists &&\s*\(\s*<DropdownMenuItem onSelect={\(\) => handleBonCommandePdf\(d\)}>\s*Bon de commande \(PDF\)/)
})

test('ZSAL8 : handleBonCommandePdf appelle ventesApi.getBonCommandePdf avec l\'id du BC', () => {
  const start = SRC.indexOf('const handleBonCommandePdf = async (d) => {')
  assert.ok(start > 0, 'handleBonCommandePdf introuvable')
  const block = SRC.slice(start, SRC.indexOf('\n  }', start))
  assert.match(block, /ventesApi\.getBonCommandePdf\(bcId\)/)
  assert.match(block, /openPdfBlob\(/)
})
