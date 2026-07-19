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
// LW37 — « Appliquer un plan » a migré de LeadForm vers le rail contexte
// (ContextRail, bouton → onAction('plan')) + le shell LeadWorkspace (montage).
const CONTEXTRAIL_SRC = readFileSync(
  join(HERE, '..', '..', '..', 'features', 'crm', 'workspace', 'ContextRail.jsx'), 'utf8')
const WORKSPACE_SRC = readFileSync(
  join(HERE, '..', '..', '..', 'features', 'crm', 'workspace', 'LeadWorkspace.jsx'), 'utf8')

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

test('ContextRail : le bouton « Appliquer un plan » déclenche onAction(\'plan\')', () => {
  assert.match(CONTEXTRAIL_SRC, /Appliquer un plan/)
  assert.match(CONTEXTRAIL_SRC, /onClick=\{\(\) => onAction\?\.\('plan'\)\}/)
})

test('LeadWorkspace : onAction(\'plan\') ouvre PlanActiviteDialog', () => {
  assert.match(WORKSPACE_SRC, /import PlanActiviteDialog from '\.\.\/\.\.\/\.\.\/pages\/crm\/leads\/PlanActiviteDialog'/)
  assert.match(WORKSPACE_SRC, /case 'plan': return setPlanOpen\(true\)/)
  assert.match(WORKSPACE_SRC, /\{planOpen && \(/)
})
