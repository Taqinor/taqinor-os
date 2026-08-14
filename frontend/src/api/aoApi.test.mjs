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
    'obstacles', 'chaines', 'zones', 'variantes',
    'seriesQR', 'exigencesCps', 'dossiers', 'pieces',
    'bibliotheque', 'equipements',
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
  // PACT76 — `plansSources` porte désormais aussi l'action `upload` : le CRUD
  // de base reste `crud('plans-source')`, étalé (spread) dans l'objet.
  assert.match(body, /plansSources:\s*\{\s*\n\s*\.\.\.crud\('plans-source'\)/)
  assert.match(body, /chaines:\s*crud\('chaines-cotes'\)/)
  assert.doesNotMatch(sansCommentaires(src), /crud\('plans-sources'\)/)
  assert.doesNotMatch(sansCommentaires(src), /crud\('chaines'\)/)
})

test('PACT76 — plansSources.upload publie l’action MULTIPART réelle (PlanSourceViewSet.upload)', () => {
  const body = aoApiBody()
  assert.match(body, /upload:\s*\(id,\s*fichier\)\s*=>\s*\{/)
  assert.match(body, /api\.post\(`\/ao\/plans-source\/\$\{id\}\/upload\/`,\s*fd\)/)
})

test('PV54/PV56 — `zones` EST publiée : ZoneAO existe et sa route est `zones`', () => {
  // Republié depuis que le modèle et la route serveur existent
  // (`apps/ao/urls.py` : `router.register(r'zones', ZoneAOViewSet, …)`) —
  // le moteur lit désormais les vraies zones (`calepinage_io.zones_vers_document`,
  // PV55), plus une liste vide en dur.
  const body = aoApiBody()
  assert.match(body, /\bzones:\s*crud\('zones'\)/)
})

test('les actions non-CRUD nommées par AOF11 sont toutes déclarées', () => {
  const body = aoApiBody()
  const actions = [
    'calculer:', 'sensibilites:', 'decomposition:',
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

test('PV67 — genererVariantes() poste sur /ao/calepinage/variantes/<id>/generer-variantes/', () => {
  const body = aoApiBody()
  assert.match(body, /genererVariantes:\s*\(id\)\s*=>\s*api\.post\(`\/ao\/calepinage\/variantes\/\$\{id\}\/generer-variantes\/`\)/)
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
  // `calepinages` (atelier non recâblé) ne doit produire AUCUN
  // `api.get/post/patch` : chacun de ses membres passe par `nonConstruit`.
  // (`equipements` a QUITTÉ cette liste le 03/08/2026 : sa route existe.)
  for (const bloc of ['calepinages']) {
    const debut = body.indexOf(`  ${bloc}: {`)
    assert.ok(debut > -1, `bloc introuvable : ${bloc}`)
    const corps = body.slice(debut, body.indexOf('\n  },', debut))
    assert.doesNotMatch(corps, /api\.(get|post|patch|delete)\(/,
      `${bloc} émet encore une requête vers une route inexistante`)
    assert.match(corps, /nonConstruit\(/)
  }
})

// PACT16 (2026-08-03) — `dossiers` NE pointe PLUS sur `dossiers-soumission`.
// Les deux tables coexistent et ont des ESPACES D'IDENTIFIANTS DISTINCTS :
// `dossiers-soumission` est la checklist administrative héritée (FG225), sans
// statut de contrôle ni visibilité de pièce ; `dossiers-ao` (AOF115) porte les
// données que l'écran affiche réellement. Viser la mauvaise table faisait donc
// désigner DEUX dossiers différents avec le même numéro — plus dangereux qu'un
// 404 parce que silencieux. L'épingle vise désormais la bonne table et
// interdit explicitement le retour en arrière.
test('affaires/pieces pointent sur les ViewSets legacy ODX11, dossiers sur dossiers-ao (PACT16)', () => {
  const body = aoApiBody()
  assert.match(body, /affaires:\s*\{[\s\S]*?\.\.\.crud\('appels-offres'\)/)
  assert.match(body, /pieces:\s*crud\('pieces-soumission'\)/)
  assert.match(body, /\.\.\.crud\('dossiers-ao'\)/)
  assert.doesNotMatch(body, /crud\('dossiers-soumission'\)/,
    "régression PACT16 : `dossiers` vise la checklist héritée, dont les identifiants "
    + 'désignent un AUTRE enregistrement que celui que l’écran affiche')
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
  // `equipements` a été RETIRÉ le 03/08/2026 : la dette est réglée (AOF118 +
  // AOF141 — sérialiseur, ViewSet `equipements`, action `bascule`). La garde
  // ci-dessous mord donc désormais dessus dans l'autre sens : si elle le
  // signale « sans route serveur », c'est que la lane BACKEND jumelle n'est
  // pas encore repliée dans cet arbre — le seul état transitoire attendu.
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
    `chemins sans route serveur (apps/ao/urls.py) : ${inconnus.join(', ')}`
    + ' — si « equipements » figure ici, la lane BACKEND jumelle (sérialiseur'
    + ' + ViewSet + route AOF118/AOF141) n’est pas encore repliée dans cet'
    + ' arbre ; c’est le SEUL manque attendu, tout autre nom est un chemin'
    + ' inventé à corriger.')
})

test('AOF118/AOF141 — les équipements passent par la factory CRUD et une ACTION `bascule`', () => {
  const body = aoApiBody()
  assert.match(body, /equipements:\s*\{\s*\n\s*\.\.\.crud\('equipements'\)/)
  assert.match(body, /bascule:\s*\(id,\s*corps\)\s*=>\s*api\.post\(`\/ao\/equipements\/\$\{id\}\/bascule\/`,\s*corps\)/)
  // La bascule est ATOMIQUE : une ACTION, jamais un PATCH de ressource.
  assert.doesNotMatch(body, /api\.patch\(`\/ao\/equipements\/\$\{id\}\/bascule\//)
  // Aucune donnée de coût ne peut être citée par le client d'API.
  const debut = body.indexOf('  equipements: {')
  const corps = body.slice(debut, body.indexOf('\n  },', debut))
  assert.doesNotMatch(corps, /prix_achat|marge|cout|coût/i)
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
