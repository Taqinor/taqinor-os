import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// AOF11 — verrouille le contrat de `aoApi.js` par lecture de SOURCE (même
// patron que `ventesApi.xsal3.test.mjs`) : `./axios` porte des effets de bord
// (baseURL/intercepteurs) qu'on ne veut pas déclencher pour un simple test de
// contrat URL/forme. Zéro appel réseau, zéro mock du graphe ESM.

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'aoApi.js'), 'utf8')

// Isole le corps de `const aoApi = { ... }` (avant l'export séparé de
// rentabilité) pour les assertions d'isolement ci-dessous.
function aoApiBody() {
  const start = src.indexOf('const aoApi = {')
  assert.ok(start > -1, 'const aoApi = { introuvable')
  const rentabiliteCommentIdx = src.indexOf('Export ISOLÉ de la rentabilité', start)
  assert.ok(rentabiliteCommentIdx > start, 'commentaire de séparation introuvable')
  return src.slice(start, rentabiliteCommentIdx)
}

test('aoApi utilise la factory partagée (ARC44), jamais un axios.get direct au niveau module', () => {
  assert.match(src, /import \{ makeResourceFactory \} from '\.\/resource'/)
  assert.match(src, /const crud = makeResourceFactory\(api, '\/ao'\)/)
})

test('les ressources CRUD nommées par AOF11 sont toutes déclarées', () => {
  const body = aoApiBody()
  const resources = [
    'affaires', 'batiments', 'toitures', 'plansSources', 'releves',
    'obstacles', 'zones', 'chaines', 'calepinages', 'variantes',
    'seriesQR', 'equipements', 'exigencesCps', 'dossiers', 'pieces',
    'bibliotheque',
  ]
  for (const key of resources) {
    assert.match(body, new RegExp(`\\b${key}:`), `ressource manquante : ${key}`)
  }
})

test('les actions non-CRUD nommées (calculer/suggestions/sensibilités/décomposition/allée-gratuite/générer-pièce/statut-de-job/zip/contrôles-avant-dépôt/bascule) sont toutes déclarées', () => {
  const body = aoApiBody()
  const actions = [
    'calculer:', 'suggestions:', 'sensibilites:', 'decomposition:',
    'alleeGratuite:', 'genererPiece:', 'statutJob:', 'zip:',
    'controlesAvantDepot:', 'bascule:',
  ]
  for (const action of actions) {
    assert.ok(body.includes(action), `action manquante : ${action}`)
  }
})

test('affaires/pieces/dossiers pointent sur les ViewSets legacy ODX11 (appels-offres/pieces-soumission/dossiers-soumission)', () => {
  const body = aoApiBody()
  assert.match(body, /affaires:\s*\{[\s\S]*?\.\.\.crud\('appels-offres'\)/)
  assert.match(body, /pieces:\s*crud\('pieces-soumission'\)/)
  assert.match(body, /\.\.\.crud\('dossiers-soumission'\)/)
})

test('AOF170 — affaires.dupliquer() existe (action de ligne « dupliquer », AOF130)', () => {
  const body = aoApiBody()
  assert.match(body, /dupliquer:\s*\(id\)\s*=>\s*api\.post\(`\/ao\/appels-offres\/\$\{id\}\/dupliquer\/`\)/)
})

test('AOF172 — tableauMarches() appelle GET /ao/tableau-marches/ (endpoint AOF166, un seul appel agrégé)', () => {
  const body = aoApiBody()
  assert.match(body, /tableauMarches:\s*\(\)\s*=>\s*api\.get\('\/ao\/tableau-marches\/'\)/)
})

test('ISOLEMENT — le corps de `aoApi` ne mentionne JAMAIS "rentabilite" (aucun chemin réseau mêlé)', () => {
  const body = aoApiBody()
  assert.doesNotMatch(body, /rentabilite/i)
})

test('aoRentabiliteApi est un export SÉPARÉ (jamais une clé de aoApi), avec get/update/download', () => {
  assert.match(src, /export const aoRentabiliteApi = \{/)
  assert.match(src, /get:\s*\(affaireId\)\s*=>\s*api\.get\(`\/ao\/\$\{affaireId\}\/rentabilite\/`\)/)
  assert.match(src, /update:\s*\(affaireId,\s*data\)\s*=>\s*api\.patch\(`\/ao\/\$\{affaireId\}\/rentabilite\/`,\s*data\)/)
  assert.match(src, /download:\s*\(affaireId\)\s*=>/)
})

test('aoApi et aoRentabiliteApi sont bien DEUX exports distincts (default + const nommée)', () => {
  assert.match(src, /export default aoApi/)
  const defaultIdx = src.indexOf('export default aoApi')
  const namedIdx = src.indexOf('export const aoRentabiliteApi')
  assert.ok(namedIdx > -1 && namedIdx < defaultIdx, 'aoRentabiliteApi doit être déclaré avant le default export')
})
