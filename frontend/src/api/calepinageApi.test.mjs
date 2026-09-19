import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

/* ============================================================================
   CAL33 — le contrat d'URL de `calepinageApi.js`, RELU À SA SOURCE.
   ----------------------------------------------------------------------------
   Même patron que `aoApi.test.mjs` : lecture de SOURCE, parce que `./axios`
   porte des effets de bord (baseURL, intercepteurs) qu'un test de contrat n'a
   aucune raison de déclencher. Zéro appel réseau, zéro mock du graphe ESM —
   ce qui prouve du même coup l'exigence « aucun appel réseau n'est déclenché à
   l'import du module ».

   LA GARDE QUI COMPTE (dernier test du fichier) : chaque chemin appelé par le
   client est comparé aux routes RÉELLEMENT enregistrées. Tant que
   `apps/calepinage/urls.py` n'existe pas (les lanes backend CAL4/CAL16… courent
   en parallèle), la référence est la clé `endpoint` des échantillons de contrat
   committés AVANT toute lane (PACT10) ; le jour où le routeur naît, il devient
   la référence AUTORITAIRE sans qu'une ligne d'ici ne change, et une divergence
   rougit. C'est l'exact contraire du 03/08/2026, où la moitié frontend avait
   INVENTÉ le contrat et l'avait désigné comme obligation pour une lane backend
   qui ne l'a jamais reçu.
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'calepinageApi.js'), 'utf8')

function racineDepot() {
  let dossier = resolve(here)
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du depot introuvable depuis ${here}`)
}

const DOSSIER_CONTRATS = join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples',
)
const URLS_SERVEUR = join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'urls.py',
)

// Les commentaires de `calepinageApi.js` CITENT des chemins et des incidents
// pour expliquer les décisions : ils ne doivent jamais être lus comme du code.
function sansCommentaires(texte) {
  return texte.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

const code = sansCommentaires(src)

/* `pivot(id)` est la racine écrite UNE fois (`/calepinage/calepinages/${id}/`).
   On la ré-inline pour que chaque action redevienne un chemin COMPLET et
   comparable — sans cela, une action écrite `${pivot(id)}layout/` échapperait
   entièrement à la garde, ce qui est exactement le trou du 03/08/2026. */
const RACINE_PIVOT = (() => {
  const m = code.match(/const pivot = \(id\) => `([^`]+)`/)
  assert.ok(m, 'la racine `pivot` est introuvable dans calepinageApi.js')
  return m[1]
})()
const codeInline = code.replaceAll('${pivot(id)}', RACINE_PIVOT)

/* ── Normalisation d'un chemin en SIGNATURE comparable ─────────────────────
   Les deux côtés écrivent le même chemin avec des notations différentes :
   `${id}` côté frontend, `<int:pk>` ou `<pk>` côté contrat/routeur. On réduit
   tout segment dynamique au même joker, et on retire le préfixe de montage
   `/api/django` que le client axios pose déjà via sa `baseURL`. */
function signature(chemin) {
  return chemin
    .replace(/^\/api\/django/, '')
    .replace(/\$\{[^}]*\}/g, '<>')
    .replace(/<[^>]*>/g, '<>')
    .replace(/\/+$/, '/')
}

/** Les chemins `/calepinage/...` littéralement appelés par le client. */
function cheminsAppeles() {
  const trouves = new Set()
  for (const m of codeInline.matchAll(/`(\/calepinage\/[^`]*)`/g)) trouves.add(signature(m[1]))
  for (const m of codeInline.matchAll(/'(\/calepinage\/[^']*)'/g)) trouves.add(signature(m[1]))
  // Les ressources passées à la factory partagée deviennent
  // `/calepinage/<ressource>/` (liste) et `/calepinage/<ressource>/<pk>/`.
  for (const m of codeInline.matchAll(/crud\('([^']+)'\)/g)) {
    trouves.add(signature(`/calepinage/${m[1]}/`))
    trouves.add(signature(`/calepinage/${m[1]}/<>/`))
  }
  return trouves
}

/** Les chemins déclarés par les échantillons de contrat committés (PACT10). */
function cheminsContractuels() {
  const declares = new Map()
  for (const fichier of readdirSync(DOSSIER_CONTRATS).filter((f) => f.endsWith('.json'))) {
    const doc = JSON.parse(readFileSync(join(DOSSIER_CONTRATS, fichier), 'utf8'))
    if (typeof doc.endpoint !== 'string') continue
    const [, chemin] = doc.endpoint.split(/\s+/)
    if (chemin) declares.set(signature(chemin), fichier)
  }
  return declares
}

/* ── Chemins appelés que AUCUN échantillon ne couvre ────────────────────────
   Ils ne sont pas devinés : chacun est RECOPIÉ du texte de la tâche PLAN2 qui
   expose la route, nommée ici pour que la provenance soit vérifiable en revue.
   Cette table ne peut que MAIGRIR : le jour où une de ces routes gagne son
   échantillon de contrat, elle sort d'ici. */
const SANS_ECHANTILLON = {
  '/calepinage/calepinages/': 'CAL16 — liste filtrable + création (lead XOR client)',
  '/calepinage/calepinages/<>/roof-image/': 'CAL19 — image de toit, stockage ventes réutilisé',
  '/calepinage/calepinages/<>/versions/': 'CAL20 — historique, ordre antichronologique',
  '/calepinage/calepinages/<>/versions/<>/restaurer/': 'CAL20 — rejoue une version en en créant une NOUVELLE',
  '/calepinage/calepinages/<>/variantes/': 'CAL21 — CRUD de variante',
  '/calepinage/calepinages/<>/variantes/<>/retenir/': 'CAL21 — action, jamais un PATCH',
  '/calepinage/calepinages/<>/design-context/': 'CAL231 — contexte de conception (pin/contour/ville)',
  '/calepinage/calepinages/<>/importer-contour-ao/': 'CAL240 — import du contour AO',
  '/calepinage/calepinages/<>/generer-devis/': 'CAL24 — appelle build_devis_from_layout, aucun PDF',
  '/calepinage/calepinages/<>/sync-devis/': 'CAL25 — appelle sync_devis_from_layout, 409 propagé tel quel',
  '/calepinage/moteur/resultat/<>/': 'CAL23 — suivi du job de fond (kind calepinage)',
  '/calepinage/parametres/': 'CAL45 — réglages société, singleton GET/PUT',
}

test('CAL33 — la factory partagée est utilisée (ARC44), jamais un axios.get direct', () => {
  assert.match(src, /import \{ makeResourceFactory \} from '\.\/resource'/)
  assert.match(src, /const crud = makeResourceFactory\(api, '\/calepinage'\)/)
})

test("CAL33 — aucun appel réseau n'est déclenché à l'import du module", () => {
  // Un appel au niveau module serait une ligne `api.get(...)` / `api.post(...)`
  // qui n'est PAS le corps d'une fonction fléchée. Toutes les déclarations de
  // ce fichier sont des `(args) => api.verbe(...)` (ou des entrées de factory) :
  // rien ne s'exécute tant qu'un écran n'appelle pas.
  for (const m of code.matchAll(/api\.(get|post|put|patch|delete)\(/g)) {
    const avant = code.slice(0, m.index)
    const derniereFleche = avant.lastIndexOf('=>')
    const derniereFinLigne = avant.lastIndexOf('\n')
    assert.ok(
      derniereFleche > derniereFinLigne
        || /=>\s*$/.test(avant.trimEnd())
        || avant.trimEnd().endsWith('=>'),
      `appel \`api.${m[1]}\` hors d'une fonction (exécuté à l'import) : `
      + code.slice(Math.max(0, m.index - 80), m.index + 40),
    )
  }
})

test('CAL33 — une SEULE forme d’URL : tout passe par /calepinage/…', () => {
  for (const chemin of cheminsAppeles()) {
    assert.ok(chemin.startsWith('/calepinage/'),
      `chemin hors du préfixe du module : ${chemin}`)
  }
  // Décision de structure n°3 du Groupe CAL : le pivot est `calepinages`, les
  // sous-ressources sont des `@action` dessus — jamais un second préfixe plat
  // du style `/calepinage/variantes/<pk>/`.
  assert.doesNotMatch(code, /\/calepinage\/variantes\//)
  assert.doesNotMatch(code, /\/calepinage\/versions\//)
})

test('CAL33 — les neuf actions exigées par la tâche sont déclarées', () => {
  const attendues = {
    layout: /layout: \(id\) => api\.get\(`\$\{pivot\(id\)\}layout\/`\)/,
    image: /envoyerImage: \(id, corps\) => api\.post\(`\$\{pivot\(id\)\}roof-image\/`, corps\)/,
    versions: /versions: \(id\) => api\.get\(`\$\{pivot\(id\)\}versions\/`\)/,
    variantes: /variantes: \(id\) => api\.get\(`\$\{pivot\(id\)\}variantes\/`\)/,
    retenir: /retenirVariante: \(id, varianteId\) =>\s*\n?\s*api\.post\(`\$\{pivot\(id\)\}variantes\/\$\{varianteId\}\/retenir\/`\)/,
    comparer: /comparer: \(id\) => api\.get\(`\$\{pivot\(id\)\}comparer\/`\)/,
    moteur: /calculer: \(corps\) => api\.post\('\/calepinage\/moteur\/calculer\/', corps\)/,
    'generer-devis': /genererDevis: \(id, corps\) => api\.post\(`\$\{pivot\(id\)\}generer-devis\/`, corps\)/,
    'sync-devis': /syncDevis: \(id, corps\) => api\.post\(`\$\{pivot\(id\)\}sync-devis\/`, corps\)/,
  }
  for (const [nom, motif] of Object.entries(attendues)) {
    assert.match(code, motif, `action manquante ou mal écrite : ${nom}`)
  }
})

test('CAL33 — `retenir` est une ACTION POST, jamais un PATCH de ressource', () => {
  assert.doesNotMatch(code, /api\.patch\(`\$\{pivot\(id\)\}variantes/)
})

test('CAL33 — RÈGLE #4 : le client ne connaît aucun chemin de PDF de devis', () => {
  assert.doesNotMatch(code, /generer-pdf|proposal|prix_achat|marge/i)
})

test('CAL33 — chaque échantillon de contrat consommé pointe le chemin EXACT qu’il déclare', () => {
  const appeles = cheminsAppeles()
  const contrats = cheminsContractuels()
  assert.ok(contrats.size > 0, 'aucun échantillon de contrat lu — dossier introuvable ?')

  // Les échantillons que ce client consomme réellement. `roof_layout_v2` est
  // le schéma du DOCUMENT servi par `layout/` : il porte le même chemin.
  const consommes = [
    'calepinage_detail.json', 'variantes_comparer.json', 'calepinage_resultat.json',
    'moteur_calculer.json', 'pose.json', 'dossiers_reglementaires.json',
    'roof_layout_v2.schema.json',
  ]
  for (const [chemin, fichier] of contrats) {
    if (!consommes.includes(fichier)) continue
    assert.ok(appeles.has(chemin),
      `le contrat ${fichier} déclare ${chemin}, qu'aucun appel de `
      + `calepinageApi.js ne cible. Chemins appelés : ${[...appeles].sort().join(', ')}`)
  }
})

test('GARDE — chaque chemin appelé existe dans une source SERVEUR (routeur, sinon contrat)', () => {
  const appeles = [...cheminsAppeles()]
  const contrats = cheminsContractuels()

  if (existsSync(URLS_SERVEUR)) {
    /* Le routeur EXISTE : il devient la référence autoritaire. On compare les
       PREMIERS SEGMENTS servis (`calepinages`, `moteur`, `parametres`) —
       exactement ce que fait `prefixesRoutesAo()` côté AO — parce qu'un
       `@action` n'est pas écrit dans `urls.py` mais sur le ViewSet. La forme
       fine des sous-routes reste gardée par `scripts/check_api_contract.py`,
       qui, lui, développe les ViewSets. */
    const source = readFileSync(URLS_SERVEUR, 'utf8')
    const prefixes = new Set()
    for (const m of source.matchAll(/router\.register\(\s*r?'([^']+)'/g)) {
      prefixes.add(m[1].split('/')[0])
    }
    for (const m of source.matchAll(/\bpath\(\s*'([^']*)'/g)) {
      const premier = m[1].split('/')[0]
      if (premier) prefixes.add(premier)
    }
    const inconnus = appeles
      .map((chemin) => chemin.split('/')[2])
      .filter((premier, i, tous) => tous.indexOf(premier) === i)
      .filter((premier) => !prefixes.has(premier))
    assert.deepEqual(inconnus, [],
      `chemins sans route serveur (apps/calepinage/urls.py) : ${inconnus.join(', ')}`)
    return
  }

  /* Le routeur N'EXISTE PAS ENCORE — état TRANSITOIRE attendu et DIT, jamais
     masqué : `apps/calepinage/` ne porte que `contract_samples/` et les lanes
     backend (CAL4 monte le préfixe, CAL16-CAL25 les vues) courent en parallèle.
     La référence est alors le contrat committé AVANT toute lane, complété par
     la table `SANS_ECHANTILLON` dont chaque entrée NOMME sa tâche source. */
  const inconnus = appeles.filter(
    (chemin) => !contrats.has(chemin) && !(chemin in SANS_ECHANTILLON))
  assert.deepEqual(inconnus, [],
    'chemins qui ne viennent NI d’un échantillon de contrat NI d’une tâche '
    + `nommée : ${inconnus.join(', ')} — un chemin deviné est exactement le `
    + 'défaut du 03/08/2026. Recopier la route depuis sa source, ou l’inscrire '
    + 'dans SANS_ECHANTILLON avec la tâche PLAN2 qui l’expose.')
})

test('GARDE — la table SANS_ECHANTILLON ne peut que MAIGRIR', () => {
  const contrats = cheminsContractuels()
  const appeles = cheminsAppeles()
  for (const [chemin, raison] of Object.entries(SANS_ECHANTILLON)) {
    assert.ok(!contrats.has(chemin),
      `${chemin} a désormais son échantillon de contrat : retirer cette entrée `
      + `(raison enregistrée : ${raison})`)
    assert.ok(appeles.has(chemin),
      `${chemin} n'est plus appelé par calepinageApi.js : retirer cette entrée`)
  }
})
