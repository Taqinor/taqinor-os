// ZSAL3 — Admin CRUD des équipes commerciales (Paramètres → CRM). Vérification
// de SOURCE (JSX, pas de node_modules installés dans ce lane).
//   node --test src/pages/parametres/EquipesCommercialesSection.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'EquipesCommercialesSection.jsx'), 'utf8')
const LEADS_SRC = readFileSync(join(HERE, 'LeadsSection.jsx'), 'utf8')
const CRMAPI_SRC = readFileSync(
  join(HERE, '..', '..', 'api', 'crmApi.js'), 'utf8')

test('crmApi expose getEquipes / saveEquipe / deleteEquipe (CRUD complet)', () => {
  assert.match(CRMAPI_SRC, /getEquipes: \(params\) => api\.get\('\/crm\/equipes\/', \{ params \}\)/)
  assert.match(CRMAPI_SRC, /saveEquipe: \(id, data\) =>/)
  assert.match(CRMAPI_SRC, /deleteEquipe: \(id\) => api\.delete\(`\/crm\/equipes\/\$\{id\}\/`\)/)
})

test('création : crmApi.saveEquipe(null, {nom}) — pas de company envoyée par le front', () => {
  const addBody = SRC.slice(SRC.indexOf('const addEquipe ='), SRC.indexOf('const renameEquipe ='))
  assert.match(addBody, /crmApi\.saveEquipe\(null, \{ nom: newNom\.trim\(\) \}\)/)
  assert.doesNotMatch(addBody, /company/)
})

test('archivage bascule actif sans supprimer (distinct de la suppression définitive)', () => {
  assert.match(SRC, /crmApi\.saveEquipe\(equipe\.id, \{ actif: !equipe\.actif \}\)/)
  assert.match(SRC, /crmApi\.deleteEquipe\(equipe\.id\)/)
})

test('suppression définitive demande confirmation (jamais silencieuse)', () => {
  const delBody = SRC.slice(SRC.indexOf('const delEquipe ='), SRC.indexOf('return ('))
  assert.match(delBody, /window\.confirm\(/)
})

test('LeadsSection monte EquipesCommercialesSection avec les assignables déjà chargés', () => {
  assert.match(LEADS_SRC, /import EquipesCommercialesSection from '\.\/EquipesCommercialesSection'/)
  assert.match(LEADS_SRC, /<EquipesCommercialesSection assignables=\{assignables\} \/>/)
})
