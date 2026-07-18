// LW2 — Perte de données #1 : le raccourci d'étape 1-4 « blanchissait » les
// éditions non sauvées. `quickChangeStage` PATCHe seulement `{stage}` côté
// serveur mais posait `setCleanFieldsJSON(JSON.stringify({...fields, stage}))`
// — l'instantané « propre » absorbait TOUTES les éditions en cours sur les
// AUTRES champs → isDirty devenait faux → fermeture/J-K sans avertissement,
// éditions perdues (le flux rafale exact que servent les touches 1-4).
// Fix : fusionner UNIQUEMENT `stage` dans l'instantané propre EXISTANT.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormLW2QuickStageNoDataLoss.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
// Le repo est en CRLF (Windows) : normaliser pour que les découpages par
// motif restent fiables indépendamment de la fin de ligne.
const FORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8').replace(/\r\n/g, '\n')

function extractFn(src, name) {
  const start = src.indexOf(`const ${name} = async (newStage) => {`)
  assert.ok(start >= 0, `${name} introuvable`)
  // Coupe au prochain "  }\n\n" (fin de fonction top-level, 2 espaces d'indent).
  const end = src.indexOf('\n  }\n', start)
  assert.ok(end >= 0, `fin de ${name} introuvable`)
  return src.slice(start, end + 5)
}

test('LW2 : quickChangeStage ne blanchit plus l\'instantané propre avec `{...fields, stage}`', () => {
  const fn = extractFn(FORM_SRC, 'quickChangeStage')
  // L'ancien bug : setCleanFieldsJSON(JSON.stringify({...fields, stage: ...})).
  assert.doesNotMatch(fn, /setCleanFieldsJSON\(JSON\.stringify\(\{\s*\.\.\.fields,\s*stage/)
})

test('LW2 : quickChangeStage fusionne UNIQUEMENT `stage` dans l\'instantané propre EXISTANT (JSON.parse(cleanFieldsJSON))', () => {
  const fn = extractFn(FORM_SRC, 'quickChangeStage')
  assert.match(fn, /const clean = JSON\.parse\(cleanFieldsJSON\)/)
  assert.match(fn, /setCleanFieldsJSON\(JSON\.stringify\(\{\s*\.\.\.clean,\s*stage:\s*resolvedStage\s*\}\)\)/)
})

test('LW2 : fields.stage n\'est mis à jour que si le champ stage n\'était pas déjà en édition (fields.stage === clean.stage)', () => {
  const fn = extractFn(FORM_SRC, 'quickChangeStage')
  assert.match(fn, /if \(fields\.stage === clean\.stage\)\s*\{/)
  assert.match(fn, /setFields\(\{\s*\.\.\.fields,\s*stage:\s*resolvedStage\s*\}\)/)
})
