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

// APX2 — les micro-icônes restent des MICRO-ICÔNES (jamais des chips), mais
// elles ont quitté la ligne de repos pour la zone révélée (`.kb-card-meta`
// dans `.kb-card-reveal`) : la carte au repos tient en 3 lignes ≤76 px et la
// readiness reste atteignable au survol ET au focus clavier.
test('QX28/APX2 : les micro-icônes readiness vivent dans la zone révélée (kb-readi), pas en gros chips', () => {
  const revealStart = SRC.indexOf('<div className="kb-card-reveal">')
  assert.ok(revealStart > -1, 'kb-card-reveal introuvable')
  const reveal = SRC.slice(revealStart)
  assert.match(reveal, /className="kb-card-meta"/)
  assert.match(reveal, /className="kb-readi"/)
  assert.match(reveal, /kb-readi-icon/)
  // Elles ne sont PLUS dans le pied de repos (L3 = points de tags + âge + avatar).
  const footStart = SRC.indexOf('<div className="kb-card-foot">')
  const footEnd = SRC.indexOf('{/* ── ZONE RÉVÉLÉE', footStart)
  assert.ok(footEnd > footStart, 'fin de pied introuvable')
  assert.doesNotMatch(SRC.slice(footStart, footEnd), /className="kb-readi"/)
  // Les anciens gros chips readiness ont disparu.
  assert.doesNotMatch(SRC, /kb-readiness-chips/)
  assert.doesNotMatch(SRC, /kb-flash-roof-badge/)
})
