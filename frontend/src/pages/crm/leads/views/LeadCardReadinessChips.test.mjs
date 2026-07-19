// QX28 — Lead readiness signals: the seller cannot tell a lead has a GPS roof
// pin / entered bill / auto-quote-ready without opening the record. LB13 —
// blueprint D3 : les 3 signaux dérivent des mêmes champs EXISTANTS
// (roof_point, facture_hiver, devis_auto.pret) mais sont désormais des
// micro-icônes 12px tooltipées dans le PIED (lucide MapPin / FileText / Zap),
// jamais un gros chip et jamais un signal « manquant » (seule l'absence de la
// micro-icône positive). Verified against SOURCE (no node_modules in this
// worktree/lane).
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

test('QX28 : les 3 micro-icônes readiness sont rendues conditionnellement (tooltip FR)', () => {
  assert.match(SRC, /\{roofReady && \(/)
  assert.match(SRC, /aria-label="Toit épinglé \(GPS\)"/)
  assert.match(SRC, /\{factureReady && \(/)
  assert.match(SRC, /aria-label="Facture saisie"/)
  assert.match(SRC, /\{devisReady && \(/)
  assert.match(SRC, /aria-label="Prêt à deviser en 1 clic"/)
})

test('QX28 : aucune icône ne s\'affiche pour un signal absent (jamais de signal "manquant")', () => {
  assert.match(SRC, /\{\(roofReady \|\| factureReady \|\| devisReady\) && \(/)
})

test('QX28 : les micro-icônes readiness vivent dans le pied de carte (kb-readi), pas en gros chips', () => {
  const footStart = SRC.indexOf('<div className="kb-card-foot">')
  assert.ok(footStart > -1, 'kb-card-foot introuvable')
  const footEnd = SRC.indexOf('{/* ── Actions rapides', footStart)
  const foot = SRC.slice(footStart, footEnd)
  assert.match(foot, /className="kb-readi"/)
  assert.match(foot, /kb-readi-icon/)
  // Les anciens gros chips readiness ont disparu.
  assert.doesNotMatch(SRC, /kb-readiness-chips/)
  assert.doesNotMatch(SRC, /kb-flash-roof-badge/)
})
