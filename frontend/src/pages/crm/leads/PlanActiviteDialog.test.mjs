// ZSAL2 — « Appliquer un plan » : sélection + application au lead ouvert.
// Vérification de SOURCE (JSX non importable par node:test directement, pas
// de node_modules installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/crm/leads/PlanActiviteDialog.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'PlanActiviteDialog.jsx'), 'utf8')
const LEADFORM_SRC = readFileSync(
  join(HERE, '..', 'LeadForm.jsx'), 'utf8')

test('charge les plans ACTIFS via crmApi.getPlansActivite', () => {
  assert.match(SRC, /crmApi\.getPlansActivite\(\)/)
  assert.match(SRC, /actifs = \(all \?\? \[\]\)\.filter\(\(p\) => p\.actif !== false\)/)
})

test('applique le plan choisi via crmApi.appliquerPlanActivite(leadId, planId)', () => {
  assert.match(SRC, /crmApi\.appliquerPlanActivite\(lead\.id, selected\.id\)/)
})

test('affiche le nombre d\'activités créées après application (pas de succès muet)', () => {
  assert.match(SRC, /setDone\(activites\.length\)/)
  assert.match(SRC, /activité\(s\) planifiée\(s\)/)
})

test('LeadForm : le bouton « Appliquer un plan » ouvre PlanActiviteDialog', () => {
  assert.match(LEADFORM_SRC, /import PlanActiviteDialog from '\.\/leads\/PlanActiviteDialog'/)
  assert.match(LEADFORM_SRC, /onClick=\{\(\) => setPlanOpen\(true\)\}/)
  assert.match(LEADFORM_SRC, /isEdit && planOpen && \(/)
})
