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
   Le budget ci-dessous (73 Ko) est le PALIER IMMÉDIATEMENT au-dessus de la
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

//: Mesuré (voir en-tête). Relevé PAR PALIER documenté, jamais élargi à vue.
const MODULE_BUDGET_KB = 73

//: Les composants du module RÉELLEMENT lazy-chargés par `module.config.jsx`
//: (préfixe de chunk = nom du fichier source, convention Vite/Rollup par
//: défaut de ce dépôt — vérifié à chaque build).
const CHUNKS_MODULE_CONFIG = [
  'CalepinageList', 'CalepinageNouveau', 'VariantesCompare',
  'FichesIncompletes', 'PompagePanel', 'PlanImporteCalage',
  'PhotoSiteCalage', 'SaisiePente', 'SchemaUnifilairePanel', 'Bibliotheque',
  'BadgePerime',
]

//: CALX398 — les onglets NEUFS de `atelier/onglets.js` (CALX1 et suivants) qui
//: n'ont AUCUN site d'appel dans `module.config.jsx` : leur chunk existe
//: UNIQUEMENT parce que le rail les charge. Un onglet qui reprend un
//: composant DÉJÀ dans `CHUNKS_MODULE_CONFIG` (les treize routes profondes
//: historiques) n'a PAS sa place ici — Rollup déduplique le même module, il
//: n'ajoute aucun poids neuf.
const CHUNKS_ATELIER_ONGLETS = [
  'PanneauDocuments', 'PanneauPertes', 'PanneauReleve', 'PanneauActivite',
  'PanneauVersions', 'PanneauMasseLestage', 'PanneauSeries', 'PanneauBatterie',
  'EquipementsElectriques', 'CheminementCables', 'Raccordement',
  'OngletCoupeRangees', 'VerdictElectrique', 'PanneauEconomie', 'Projet',
  'DiffVersions',
]

const CHUNKS_DU_MODULE = [...CHUNKS_MODULE_CONFIG, ...CHUNKS_ATELIER_ONGLETS]

function fichiersDuModule() {
  const fichiers = readdirSync(DIST_ASSETS).filter((f) => f.endsWith('.js'))
  return CHUNKS_DU_MODULE
    .map((prefixe) => fichiers.find((f) => f.startsWith(`${prefixe}-`)))
    .filter(Boolean)
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
      `module calepinage: ${totalKb.toFixed(2)} Ko (gzip) > budget `
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
