// QX28 — Lead readiness chips: the seller cannot tell a lead has a GPS
// roof pin / entered bill / auto-quote-ready without opening the record.
// LeadCard.jsx (kanban) gets three chips derived from EXISTING fields
// (roof_point, facture_hiver, devis_auto.pret), and the ⚡ auto-quote button
// is badged when roof data exists. Verified against SOURCE (no node_modules
// in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardReadinessChips.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('QX28 : les 3 signaux dérivent de champs EXISTANTS (aucun nouveau champ serveur)', () => {
  assert.match(SRC, /const roofReady = !!lead\.roof_point/)
  assert.match(SRC, /const factureReady = lead\.facture_hiver != null && lead\.facture_hiver !== ''/)
  assert.match(SRC, /const devisReady = !!lead\.devis_auto\?\.pret/)
})

test('QX28 : les 3 chips FR attendus sont rendus conditionnellement', () => {
  assert.match(SRC, /\{roofReady && \(/)
  assert.match(SRC, /Toit épinglé \(GPS\)/)
  assert.match(SRC, /\{factureReady && \(/)
  assert.match(SRC, /Facture saisie/)
  assert.match(SRC, /\{devisReady && \(/)
  assert.match(SRC, /Prêt à deviser en 1 clic/)
})

test('QX28 : aucun chip ne s\'affiche pour un signal absent (jamais de chip "manquant")', () => {
  assert.match(SRC, /\{\(roofReady \|\| factureReady \|\| devisReady\) && \(/)
})

test('QX28 : le bouton ⚡ (devis auto) est badgé quand un repère toit existe', () => {
  const start = SRC.indexOf("className=\"kb-flash\"")
  const block = SRC.slice(start, start + 1400)
  assert.match(block, /roofReady \? 'Devis auto — repère toit disponible'/)
  assert.match(block, /\{roofReady && \(/)
  assert.match(block, /kb-flash-roof-badge/)
})
