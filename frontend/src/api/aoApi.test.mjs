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
// Les commentaires de ce fichier CITENT les mauvais chemins d'hier pour
// expliquer la réparation : ils ne doivent pas être lus comme du code.
function sansCommentaires(texte) {
  return texte.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

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

test('les ressources CRUD dont la route SERVEUR existe sont toutes déclarées', () => {
  const body = aoApiBody()
  const resources = [
    'affaires', 'batiments', 'toitures', 'plansSources', 'releves',
    'obstacles', 'chaines', 'variantes',
    'seriesQR', 'exigencesCps', 'dossiers', 'pieces',
    'bibliotheque',
  ]
  for (const key of resources) {
    assert.match(body, new RegExp(`\\b${key}:`), `ressource manquante : ${key}`)
  }
})

test('les ressources de relevé pointent le NOM SERVEUR (plans-source au singulier, chaines-cotes)', () => {
  const body = aoApiBody()
  assert.match(body, /plansSources:\s*crud\('plans-source'\)/)
  assert.match(body, /chaines:\s*crud\('chaines-cotes'\)/)
  assert.doesNotMatch(sansCommentaires(src), /crud\('plans-sources'\)/)
  assert.doesNotMatch(sansCommentaires(src), /crud\('chaines'\)/)
})

test('AOF89 — `zones` n’est PAS publiée : aucun modèle ni route ne persiste les zones', () => {
  // Le moteur reçoit `'zones': []` en dur (`calepinage_io.document_entree`).
  // Republier `crud('zones')` ferait croire à un stockage inexistant.
  assert.doesNotMatch(sansCommentaires(src), /\bzones:\s*crud\(/)
  assert.doesNotMatch(sansCommentaires(src), /'\/ao\/zones\//)
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

test('AOF173 — la bibliothèque est une FAÇADE sur 4 ressources routées, plus jamais /ao/bibliotheque/', () => {
  // Le bug de production du 03/08/2026 : `crud('bibliotheque')` appelait une
  // route jamais enregistrée. Aucun chemin `/ao/bibliotheque/` ne doit revenir.
  assert.doesNotMatch(sansCommentaires(src), /\/ao\/bibliotheque\//)
  assert.doesNotMatch(sansCommentaires(src), /crud\('bibliotheque'\)/)
  assert.match(src, /export const BIBLIOTHEQUE_RESSOURCES = \{/)
  for (const chemin of ['kits-calepinage', 'presets-calepinage', 'modeles-pack',
    'sections-memoire']) {
    assert.ok(src.includes(`'${chemin}'`), `catégorie non câblée : ${chemin}`)
  }
  const body = aoApiBody()
  assert.match(body, /dossiersImpactes:\s*\(id\)\s*=>\s*api\.get\(`\/ao\/sections-memoire\/\$\{id\}\/dossiers-impactes\/`\)/)
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
