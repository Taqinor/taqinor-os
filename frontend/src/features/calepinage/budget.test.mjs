import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

/* ============================================================================
   CAL224 — BUDGET DE PERFORMANCE DU MODULE CALEPINAGE (chunks, MESURÉS).
   ----------------------------------------------------------------------------
   Constat de la tâche : le chunk `roof-tool` a déjà son garde de nommage
   (`build-tools/roof_tool_chunk_naming.test.mjs`) et le dépôt a un plafond de
   chunks global (`scripts/check_bundle_budget.mjs`, `MAX_CHUNK_COUNT`) — mais
   RIEN ne borne spécifiquement les écrans que ce module a ajoutés.

   POURQUOI PAS UN SIMPLE AJOUT À `check_bundle_budget.mjs` : ce script tourne
   APRÈS `npm run build` (`.github/workflows/ci.yml`, job `frontend-static`,
   étape « Check bundle budget ») ; les fichiers `.test.mjs` sont eux
   découverts et exécutés AVANT ce build (étape « Frontend unit tests »,
   `node --test` sur tout `src/.../.test.mjs`). Ce fichier réutilise donc la MÊME
   fonction mesurée (`checkBundleBudget`, exportée par ce script) : si
   `dist/` n'existe pas encore (le cas normal en CI à cet endroit du job), il
   se tait — SILENCIEUX, jamais un FAUX rouge sur un artefact qui n'a pas
   encore de raison d'exister ; s'il existe (un `vite build` local, ou un
   futur réordonnancement du job), il devient un VRAI gate. Le garde STATIQUE
   ci-dessous (aucun `dist/` requis) reste, lui, TOUJOURS actif.

   CALX398 — RE-MESURE APRÈS LE LOT (rail + onglets de l'atelier, CALX1 et
   suivants). `npx vite build` (2026-09-24) donne **69,96 Ko** gzip pour
   VINGT-SEPT chunks lazy désormais suivis :
     - LES ONZE déjà suivis (routes de `module.config.jsx`) : `CalepinageList`,
       `CalepinageNouveau`, `VariantesCompare`, `FichesIncompletes`,
       `PompagePanel`, `PlanImporteCalage`, `PhotoSiteCalage`, `SaisiePente`,
       `SchemaUnifilairePanel`, `Bibliotheque`, `BadgePerime` ;
     - SEIZE chunks NEUFS, déclarés UNIQUEMENT dans le registre
       `atelier/onglets.js` (CALX1 et les onglets posés depuis) — AUCUN autre
       n'a de site d'appel dans `module.config.jsx` : `PanneauDocuments`,
       `PanneauPertes`, `PanneauReleve`, `PanneauActivite`, `PanneauVersions`,
       `PanneauMasseLestage`, `PanneauSeries`, `PanneauBatterie`,
       `EquipementsElectriques`, `CheminementCables`, `Raccordement`,
       `OngletCoupeRangees`, `VerdictElectrique`, `PanneauEconomie`, `Projet`
       (CALX371), `DiffVersions` (CALX346).
   Les TREIZE autres onglets du registre (`pente`, `terrain`, `ombriere`,
   `horizon`, `course-soleil`, `fiches`, `affectation`, `schema`, `pompage`,
   `production`, `pertes`, `dossiers`, `documents`… soit `PlanImporteCalage`,
   `SaisiePente`, `ModeTerrain`, `Ombriere`, `HorizonPanel`, `CourseSoleil`,
   `FichesIncompletes`, `AffectationChaines`, `SchemaUnifilairePanel`,
   `PompagePanel`, `PanneauProduction`, `DiagrammePertes`,
   `DossiersReglementaires`) sont les TREIZE routes profondes HISTORIQUES,
   DÉJÀ importées par `module.config.jsx` (mêmes chunks, dédupliqués par
   Rollup — AUCUN poids neuf) : cinq d'entre elles étaient déjà suivies
   ci-dessus, les huit autres restent HORS PÉRIMÈTRE de cette tâche (des
   routes préexistantes, sans lien avec l'ajout du rail).
   [Remplacé le 27/11 : voir MODULE_BUDGET_KB.] L'ancien budget (73 Ko) était le PALIER IMMÉDIATEMENT au-dessus de la
   mesure (~3 Ko de marge, jamais élargi « pour respirer ») — à RELEVER PAR
   PALIER documenté le jour où un onglet légitime le dépasse, même convention
   que `check_bundle_budget.mjs`.
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))

function racineFrontend() {
  let dossier = here
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'vite.config.js'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine frontend introuvable depuis ${here}`)
}

const FRONTEND_ROOT = racineFrontend()
const DIST_ASSETS = join(FRONTEND_ROOT, 'dist', 'assets')
const DIST_INDEX = join(FRONTEND_ROOT, 'dist', 'index.html')

//: DÉCISION FONDATEUR 27/11 : plafond GELÉ au poids que la CI mesure
//: aujourd'hui ; il ne peut QUE BAISSER (cliquet), une tâche distincte devant
//: alléger le module roof-layout. Mesure du relecteur sur un build de cette
//: voie : 124,36 Ko gzip (27 chunks, `Projet` désambiguïsé) ; le palier (le
//: Ko entier) au-dessus est 125. L'orchestrateur le CONFIRME sur le run CI et
//: l'abaisse à la valeur réellement imprimée si elle est plus basse. Jamais relevé.
const MODULE_BUDGET_KB = 125

//: Les composants du module RÉELLEMENT lazy-chargés par `module.config.jsx`
//: (préfixe de chunk = nom du fichier source, convention Vite/Rollup par
//: défaut de ce dépôt — vérifié à chaque build).
const CHUNKS_MODULE_CONFIG = [
  'CalepinageList', 'CalepinageNouveau', 'Bibliotheque',
  'BadgePerime',
]

//: ACAL407/ACAL409 — les panneaux des routes profondes historiques ne sont
//: plus importés par `module.config.jsx` (leurs routes redirigent vers
//: `?onglet=` via `RedirectionOnglet`) : ils sont chargés UNIQUEMENT par le
//: rail `atelier/onglets.js`, où leur `lazy()` est vérifié ci-dessous.
const CHUNKS_ROUTES_DEVENUES_ONGLETS = [
  'VariantesCompare', 'FichesIncompletes', 'PompagePanel', 'PlanImporteCalage',
  'PhotoSiteCalage', 'SaisiePente', 'SchemaUnifilairePanel',
]

//: CALX398 — les onglets NEUFS de `atelier/onglets.js` (CALX1 et suivants) qui
//: n'ont AUCUN site d'appel dans `module.config.jsx` : leur chunk existe
//: UNIQUEMENT parce que le rail les charge. Un onglet qui reprend un
//: composant DÉJÀ dans `CHUNKS_MODULE_CONFIG` n'a PAS sa place ici — Rollup
//: déduplique le même module, il
//: n'ajoute aucun poids neuf.
const CHUNKS_ATELIER_ONGLETS = [
  ...CHUNKS_ROUTES_DEVENUES_ONGLETS,
  'PanneauDocuments', 'PanneauPertes', 'PanneauReleve', 'PanneauActivite',
  'PanneauVersions', 'PanneauMasseLestage', 'PanneauSeries', 'PanneauBatterie',
  'EquipementsElectriques', 'CheminementCables', 'Raccordement',
  'OngletCoupeRangees', 'VerdictElectrique', 'PanneauEconomie', 'PanneauProjet',
  'DiffVersions',
]

const CHUNKS_DU_MODULE = [...CHUNKS_MODULE_CONFIG, ...CHUNKS_ATELIER_ONGLETS]

// ACAL2046 (revue) — EXACTEMENT un chunk par préfixe, sinon on échoue en nommant
// le préfixe : `find` prenait « le premier » (ordre dépendant du hash) et
// `filter(Boolean)` taisait un préfixe disparu. Le préfixe `Projet` a ainsi
// compté la page des tâches (15,4 Ko) au lieu de l'onglet calepinage (2,56 Ko) ;
// l'onglet s'appelle désormais `PanneauProjet` (aucune collision).
export function fichiersParPrefixe(fichiers, prefixes) {
  return prefixes.map((prefixe) => {
    const trouves = fichiers.filter((f) => f.endsWith('.js') && f.startsWith(`${prefixe}-`))
    if (trouves.length !== 1) {
      throw new Error(
        `préfixe de chunk « ${prefixe} » : ${trouves.length} fichier(s) dans dist/assets `
        + `(attendu : exactement 1)${trouves.length ? ` — ${trouves.join(', ')}` : ''}`)
    }
    return trouves[0]
  })
}

function fichiersDuModule() {
  return fichiersParPrefixe(readdirSync(DIST_ASSETS), CHUNKS_DU_MODULE)
}

// ── 1. GARDE STATIQUE (toujours actif, aucun `dist/` requis) ──────────────

test('CAL224 — chaque écran-route du module est LAZY (jamais un import statique)', () => {
  const config = readFileSync(
    join(FRONTEND_ROOT, 'src', 'features', 'calepinage', 'module.config.jsx'),
    'utf8')
  for (const nom of CHUNKS_MODULE_CONFIG) {
    if (nom === 'BadgePerime') continue // composant partagé, pas une route.
    const motif = new RegExp(
      `const ${nom} = lazy\\(\\(\\) => import\\('\\./[\\w/]*${nom}'\\)\\)`)
    assert.match(config, motif,
      `${nom} doit être importé via lazy(() => import(...)) dans `
      + 'module.config.jsx — un import statique ferait grossir le chunk '
      + 'd\u2019entrée pour un écran contextuel.')
  }
})

// CALX398 — le garde statique COUVRE aussi les onglets NEUFS de l'atelier
// (`atelier/onglets.js`, distinct de `module.config.jsx` ci-dessus) : un
// onglet qui perdrait son `lazy()` grossirait le chunk d'entrée de l'atelier
// pour un panneau que la plupart des sessions n'ouvrent jamais.
test('CAL224 — chaque onglet NEUF de l’atelier est LAZY dans le registre `onglets.js`', () => {
  const registre = readFileSync(
    join(FRONTEND_ROOT, 'src', 'features', 'calepinage', 'atelier', 'onglets.js'),
    'utf8')
  for (const nom of CHUNKS_ATELIER_ONGLETS) {
    const motif = new RegExp(
      `composant: lazy\\(\\(\\) => import\\('[./\\w-]*${nom}'\\)\\)`)
    assert.match(registre, motif,
      `${nom} doit être déclaré \`composant: lazy(() => import(...))\` dans `
      + 'atelier/onglets.js — un import statique grossirait le chunk du '
      + 'rail pour un onglet que la session n\u2019a pas ouvert.')
  }
})

// ACAL2046 — le garde mesuré ne sert à rien s'il se tait en CI : le workflow doit le jouer APRÈS le build.
test('ACAL2046 — ci.yml joue budget.test.mjs après « Build frontend » (sur un vrai dist/)', () => {
  const ci = readFileSync(join(FRONTEND_ROOT, '..', '.github', 'workflows', 'ci.yml'), 'utf8')
  const build = ci.search(/- name: Build frontend\r?\n/)
  const garde = ci.indexOf('src/features/calepinage/budget.test.mjs')
  assert.ok(build >= 0, 'étape « Build frontend » introuvable dans ci.yml')
  assert.ok(garde > build,
    'ci.yml ne joue pas `node --test src/features/calepinage/budget.test.mjs` après « Build frontend » : '
    + 'le garde mesuré se tairait (dist/ absent).')
})

// ── 2. GARDE MESURÉ (actif seulement si `dist/` existe — voir en-tête) ────

const distDisponible = existsSync(DIST_ASSETS)

test('CAL224 — le poids gzip des chunks du module reste sous le budget MESURÉ',
  { skip: !distDisponible && 'dist/ absent (build pas encore lancé — voir en-tête)' },
  async () => {
    const { checkBundleBudget } = await import('../../../scripts/check_bundle_budget.mjs')
    const result = checkBundleBudget(join(FRONTEND_ROOT, 'dist'))

    const fichiers = fichiersDuModule()
    assert.ok(fichiers.length > 0,
      'aucun chunk du module trouvé dans dist/assets — noms de composants '
      + 'désynchronisés de CHUNKS_DU_MODULE ?')

    const parFichier = new Map(result.perFile.map((f) => [f.fileName, f.sizeKb]))
    let totalKb = 0
    const detail = []
    for (const fichier of fichiers) {
      const kb = parFichier.get(fichier) ?? 0
      totalKb += kb
      detail.push(`${fichier}: ${kb.toFixed(2)} Ko`)
    }

    assert.ok(totalKb <= MODULE_BUDGET_KB,
      `module calepinage MESURÉ: ${totalKb.toFixed(2)} Ko (gzip) > plafond `
      + `${MODULE_BUDGET_KB} Ko.\n${detail.join('\n')}`)
  })

test('CAL224 — aucun chunk du module n\u2019est modulepreloadé sur /login',
  { skip: !distDisponible && 'dist/ absent (build pas encore lancé — voir en-tête)' },
  () => {
    if (!existsSync(DIST_INDEX)) return // index.html absent d'un dist partiel.
    const html = readFileSync(DIST_INDEX, 'utf8')
    const preloads = [...html.matchAll(
      /<link[^>]*rel="modulepreload"[^>]*href="([^"]+)"/g)]
      .map((m) => m[1].split('/').pop())

    const fichiers = new Set(fichiersDuModule())
    const fuites = preloads.filter((f) => fichiers.has(f))
    assert.deepEqual(fuites, [],
      `chunk(s) du module précargé(s) au BOOT (index.html, toute page dont `
      + `/login) : ${fuites.join(', ')} — un écran contextuel à UN `
      + 'calepinage ne doit jamais être modulepreloadé sur une page qui ne '
      + 'l\u2019ouvre pas.')
  })

// ── 3. RÈGLE « EXACTEMENT UN CHUNK PAR PRÉFIXE » (liste factice, sans dist/) ──

test('ACAL2046 — un préfixe qui matche deux chunks fait échouer la mesure en le nommant', () => {
  const listing = ['Projet-aaa.js', 'Projet-bbb.js', 'Raccordement-ccc.js', 'Raccordement-ccc.js.map']
  assert.throws(() => fichiersParPrefixe(listing, ['Projet']), /« Projet » : 2 fichier/)
})

test('ACAL2046 — un préfixe sans chunk fait échouer la mesure (plus de filter(Boolean) muet)', () => {
  assert.throws(() => fichiersParPrefixe(['Raccordement-ccc.js'], ['PanneauProjet']), /« PanneauProjet » : 0 fichier/)
})

test('ACAL2046 — un chunk par préfixe passe', () => {
  assert.deepEqual(
    fichiersParPrefixe(['PanneauProjet-x.js', 'Projet-y.js', 'PanneauProjet-x.js.map'], ['PanneauProjet', 'Projet']),
    ['PanneauProjet-x.js', 'Projet-y.js'])
})
