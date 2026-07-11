// QX28 — same readiness chips as LeadCard.jsx, rendered in LeadForm's header
// (edit mode) so the seller sees them the moment the record opens, plus a
// "📍" badge on the "Concevoir la toiture (3D)" shortcut when roof data
// exists. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormReadinessChips.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('QX28 : roofReady/factureReady dérivés de liveLead (devisReady réutilise la variable existante)', () => {
  assert.match(SRC, /const roofReady = !!liveLead\?\.roof_point/)
  assert.match(SRC, /const factureReady = liveLead\?\.facture_hiver != null && liveLead\.facture_hiver !== ''/)
  // devisReady existait déjà (verrouillage du bouton devis auto) — pas de doublon.
  const matches = SRC.match(/const devisReady = /g) ?? []
  assert.equal(matches.length, 1)
})

test('QX28 : les chips sont rendus dans l\'en-tête, uniquement en édition', () => {
  assert.match(SRC, /\{isEdit && \(roofReady \|\| factureReady \|\| devisReady\) && \(/)
  assert.match(SRC, /Toit épinglé \(GPS\)/)
  assert.match(SRC, /Facture saisie/)
  assert.match(SRC, /Prêt à deviser en 1 clic/)
})

test('QX28 : le raccourci 3D (dédupliqué en une seule occurrence par VX143) est badgé quand roofReady', () => {
  // VX143 a dédupliqué le bouton « Concevoir la toiture (3D) » à UNE seule
  // occurrence (subbar, toujours visible) ; elle reste badgée 📍 quand roofReady.
  const occurrences = [...SRC.matchAll(/Concevoir la toiture \(3D\)\{roofReady \? ' 📍' : ''\}/g)]
  assert.equal(occurrences.length, 1)
})
