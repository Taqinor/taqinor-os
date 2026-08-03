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

test('AOF28/AOF62 — les variantes pointent `variantes-calepinage`, et l’échelle est `marches`', () => {
  const body = aoApiBody()
  assert.match(body, /\.\.\.crud\('variantes-calepinage'\)/)
  assert.doesNotMatch(sansCommentaires(src), /crud\('variantes'\)/)
  // `decomposition` n'a jamais été routé : la vraie action est `marches`, sur
  // le viewset d'actions de calepinage.
  assert.match(body, /decomposition:\s*\(id\)\s*=>\s*api\.get\(`\/ao\/calepinage\/variantes\/\$\{id\}\/marches\/`\)/)
  assert.doesNotMatch(sansCommentaires(src), /\/ao\/variantes\/\$\{id\}\/decomposition\//)
  // `retenir` est une ACTION (elle dé-retient la précédente) — pas un PATCH.
  assert.match(body, /retenir:\s*\(id\)\s*=>\s*api\.post\(`\/ao\/variantes-calepinage\/\$\{id\}\/retenir\/`\)/)
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

test('les actions non-CRUD nommées par AOF11 sont toutes déclarées', () => {
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

test('AOF61/AOF62 — le calepinage expose les VRAIES routes (calcul SANS ÉTAT, actions sur la VARIANTE)', () => {
  const body = aoApiBody()
  assert.match(body, /calculer:\s*\(corps\)\s*=>\s*api\.post\('\/ao\/calepinage\/calculer\/', corps\)/)
  assert.match(body, /lancer:\s*\(corps\)\s*=>\s*api\.post\('\/ao\/calepinage\/lancer\/', corps\)/)
  assert.match(body, /resultat:\s*\(jobId\)\s*=>\s*api\.get\(`\/ao\/calepinage\/resultat\/\$\{jobId\}\/`\)/)
  for (const action of ['retenir', 'sensibilites', 'marches', 'comparer']) {
    assert.ok(body.includes(`/ao/calepinage/variantes/`), 'actions de variante absentes')
    assert.ok(body.includes(`${action}:`), `action de variante manquante : ${action}`)
  }
})

test('un endpoint NON CONSTRUIT échoue avec son MOTIF, sans émettre de requête', async () => {
  // Le contraire du bug d'origine : plus jamais un 404 anonyme sur une URL
  // devinée. Le rejet est au format d'erreur axios, donc les écrans affichent
  // la raison exacte sans être modifiés.
  const { endpointNonConstruit } = await import('./endpointNonConstruit.js')
  const appel = endpointNonConstruit('/ao/equipements/', 'ni ViewSet ni route')
  await assert.rejects(appel(), (erreur) => {
    assert.equal(erreur.message,
      'Endpoint non construit — /ao/equipements/ : ni ViewSet ni route')
    assert.equal(erreur.response.status, 501)
    assert.equal(erreur.response.data.detail, erreur.message)
    return true
  })
})

test('les surfaces sans endpoint utilisent le rejet NOMMÉ, jamais un chemin deviné', () => {
  const body = aoApiBody()
  // `calepinages` (atelier non recâblé) et `equipements` (modèle sans route)
  // ne doivent produire AUCUN `api.get/post/patch` : chacun de leurs membres
  // passe par `nonConstruit`.
  for (const bloc of ['calepinages', 'equipements']) {
    const debut = body.indexOf(`  ${bloc}: {`)
    assert.ok(debut > -1, `bloc introuvable : ${bloc}`)
    const corps = body.slice(debut, body.indexOf('\n  },', debut))
    assert.doesNotMatch(corps, /api\.(get|post|patch|delete)\(/,
      `${bloc} émet encore une requête vers une route inexistante`)
    assert.match(corps, /nonConstruit\(/)
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

/* ============================================================================
   LA GARDE PRINCIPALE — un chemin de ce fichier est RELU dans le routeur.
   ----------------------------------------------------------------------------
   C'est la garde qui manquait le 03/08/2026 : neuf chemins étaient appelés
   sans qu'aucune route ne les serve, et rien ne le disait. Elle mord dans les
   DEUX SENS : un chemin nouveau doit exister côté serveur, et un endpoint
   listé comme manquant doit encore l'être (sinon la dette est réglée et la
   liste doit maigrir).
   ========================================================================== */

// Chemins CITÉS par `aoApi.js` alors qu'AUCUNE route ne les sert. Ils ne sont
// jamais appelés (ils passent par `nonConstruit`) : ils sont ici pour que la
// dette soit COMPTÉE, pas pour être tolérée.
const MANQUANTS_CONNUS = {
  calepinages: "aucun modèle Calepinage : l'atelier attend un recâblage sur "
    + 'le calcul sans état (/ao/calepinage/…) ou un modèle à construire',
  equipements: 'EquipementAO existe en modèle, sans sérialiseur ni ViewSet ni '
    + 'route, et services.basculer_equipement (AOF141) n’est pas écrit',
}

function cheminsUtilises() {
  const code = sansCommentaires(src)
  const utilises = new Set()
  for (const m of code.matchAll(/crud\('([^']+)'\)/g)) utilises.add(m[1].split('/')[0])
  for (const m of code.matchAll(/\/ao\/([^/`'$]+)\//g)) utilises.add(m[1])
  return utilises
}

test('GARDE — chaque chemin appelé par aoApi existe dans le routeur serveur', async () => {
  const { prefixesRoutesAo } = await import('../test/contratServeur.js')
  const routes = prefixesRoutesAo()
  const inconnus = [...cheminsUtilises()].filter(
    (prefixe) => !routes.has(prefixe) && !(prefixe in MANQUANTS_CONNUS))
  assert.deepEqual(inconnus, [],
    `chemins sans route serveur (apps/ao/urls.py) : ${inconnus.join(', ')}`)
})

test('GARDE — un endpoint listé comme MANQUANT doit encore l’être', async () => {
  const { prefixesRoutesAo } = await import('../test/contratServeur.js')
  const routes = prefixesRoutesAo()
  for (const [prefixe, raison] of Object.entries(MANQUANTS_CONNUS)) {
    assert.ok(!routes.has(prefixe),
      `/ao/${prefixe}/ est désormais routé : câbler l'écran et retirer cette `
      + `entrée (raison enregistrée : ${raison})`)
  }
})

test('GARDE — la LECTURE de la rentabilité cible la ressource RÉELLE `economie` (AOF161 tranché)', async () => {
  // La cible a été tranchée, comme l'exigeait le test d'hier : le routeur
  // publie `economie`/`lignes-cout-revient`/`cibles-financieres`, jamais
  // `/ao/<id>/rentabilite/`. Le préfixe est RELU dans `apps/ao/urls.py`, pas
  // supposé ici. (Le TÉLÉCHARGEMENT est traité à part : voir plus bas.)
  const { prefixesRoutesAo } = await import('../test/contratServeur.js')
  assert.ok(prefixesRoutesAo().has('economie'),
    'le routeur AO ne publie plus `economie` : la cible est à re-trancher')
  assert.doesNotMatch(sansCommentaires(src), /\/ao\/\$\{affaireId\}\/rentabilite\//)
})

test('AOF161 — le classeur directeur passe par un JOB, jamais un rendu synchrone', () => {
  // `telecharger` est une @action du VRAI ViewSet (`EconomieAOViewSet`), lue
  // dans la source serveur : POST = production, GET = suivi, GET+fichier =
  // retrait des octets.
  assert.match(src, /produireClasseur:\s*\(economieId\)\s*=>\s*api\.post\(`\/ao\/economie\/\$\{economieId\}\/telecharger\/`\)/)
  assert.match(src, /statutClasseur:\s*\(economieId,\s*jobId\)\s*=>\s*api\.get\(`\/ao\/economie\/\$\{economieId\}\/telecharger\/`/)
  assert.match(src, /download:\s*\(economieId,\s*jobId\)\s*=>\s*api\.get\(`\/ao\/economie\/\$\{economieId\}\/telecharger\/`/)
  // Les octets sont binaires : sans `blob`, axios corromprait le classeur.
  assert.match(src, /responseType:\s*'blob'/)
})

test('AOF161 — l’action `telecharger` existe RÉELLEMENT sur EconomieAOViewSet', async () => {
  const { readFileSync } = await import('node:fs')
  const { fichierAo } = await import('../test/contratServeur.js')
  const serveur = readFileSync(fichierAo('views_directeur.py'), 'utf8')
  assert.match(serveur, /class EconomieAOViewSet\(/)
  assert.match(serveur, /@action\(detail=True, methods=\['get', 'post'\], url_path='telecharger'\)/)
})

test('ISOLEMENT — le corps de `aoApi` ne mentionne JAMAIS "rentabilite" (aucun chemin réseau mêlé)', () => {
  const body = aoApiBody()
  assert.doesNotMatch(body, /rentabilite/i)
})

test('aoRentabiliteApi est un export SÉPARÉ (jamais une clé de aoApi), avec parAffaire/get/update/download', () => {
  assert.match(src, /export const aoRentabiliteApi = \{/)
  // L'écran d'affaire ne connaît que l'id d'AO : il passe par le filtre
  // `?appel_offre=` RÉELLEMENT implémenté par `EconomieAOViewSet`.
  assert.match(src, /parAffaire:\s*\(affaireId\)\s*=>\s*api\.get\('\/ao\/economie\/',\s*\{\s*params:\s*\{\s*appel_offre:\s*affaireId\s*\}\s*\}\)/)
  assert.match(src, /get:\s*\(economieId\)\s*=>\s*api\.get\(`\/ao\/economie\/\$\{economieId\}\/`\)/)
  assert.match(src, /update:\s*\(economieId,\s*data\)\s*=>\s*api\.patch\(`\/ao\/economie\/\$\{economieId\}\/`,\s*data\)/)
  assert.match(src, /download:\s*\(economieId,\s*jobId\)\s*=>/)
})

test('aoApi et aoRentabiliteApi sont bien DEUX exports distincts (default + const nommée)', () => {
  assert.match(src, /export default aoApi/)
  const defaultIdx = src.indexOf('export default aoApi')
  const namedIdx = src.indexOf('export const aoRentabiliteApi')
  assert.ok(namedIdx > -1 && namedIdx < defaultIdx, 'aoRentabiliteApi doit être déclaré avant le default export')
})
