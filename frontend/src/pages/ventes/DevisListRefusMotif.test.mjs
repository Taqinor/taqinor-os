// QX26 — Structured loss reasons: refusal reason moves from an OPTIONAL
// window.prompt free-text to a MANDATORY modal with a MotifPerte select
// (company-scoped endpoint) + optional detail note. Verified against SOURCE
// (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisListRefusMotif.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('QX26 : plus aucun window.prompt pour le motif de refus', () => {
  assert.doesNotMatch(SRC, /window\.prompt\('Motif du refus/)
})

test('QX26 : crmApi.getMotifsPerte alimente la liste des motifs (taxonomie partagée)', () => {
  assert.match(SRC, /import crmApi from '\.\.\/\.\.\/api\/crmApi'/)
  assert.match(SRC, /crmApi\.getMotifsPerte\(\)/)
})

test('QX26 : le bouton de confirmation reste désactivé sans motif sélectionné', () => {
  const start = SRC.indexOf('open={!!refusTarget}')
  assert.ok(start > 0, 'modale de refus introuvable')
  const modalBlock = SRC.slice(start, start + 1200)
  assert.match(modalBlock, /disabled=\{!refusMotifId\}/)
})

test('QX26 : submitRefus bloque sans refusMotifId (mandatory — jamais un refus silencieux)', () => {
  const body = SRC.slice(SRC.indexOf('const submitRefus = async'), SRC.indexOf('const submitRefus = async') + 500)
  assert.match(body, /if \(!d \|\| !refusMotifId\) return/)
  assert.match(body, /motif_perte: refusMotifId/)
})

test('QX26 : le bouton « Refuser » de la ligne ouvre la modale (openRefusModal), plus de handleRefuser direct', () => {
  assert.doesNotMatch(SRC, /onClick=\{\(\) => handleRefuser\(d\)\}/)
  assert.match(SRC, /onClick=\{\(\) => openRefusModal\(d\)\}/)
})
