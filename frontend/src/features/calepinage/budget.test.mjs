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

   LA BORNE EST MESURÉE, PAS DEVINÉE : `npx vite build` (2026-09-20) donne
   22.91 Ko gzip pour les dix chunks lazy du module (`CalepinageList`,
   `CalepinageNouveau`, `VariantesCompare`, `FichesIncompletes`,
   `PompagePanel`, `PlanImporteCalage`, `PhotoSiteCalage`, `SaisiePente`,
   `SchemaUnifilairePanel`, `Bibliotheque`, plus `BadgePerime`) — le budget
   ci-dessous (30 Ko) laisse une marge raisonnable, RELEVÉE par palier documenté
   le jour où un écran légitime la dépasse (même convention que
   `check_bundle_budget.mjs`), jamais élargie « pour respirer ».

   `PanneauAllees` n'a PAS son propre chunk : il est importé STATIQUEMENT par
   `AtelierPanneaux.jsx`, lui-même importé par `pages/ventes/ToitureDesign.jsx`
   (le builder 3D PARTAGÉ lead/devis/ao/calepinage) — il voyage donc dans le
   chunk `ToitureDesign`, déjà hors du périmètre de ce module (c'est l'atelier
   COMMUN, pas un écran du module) et hors du plafond `roof-tool` séparé.
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
const MODULE_BUDGET_KB = 30

//: Les composants du module RÉELLEMENT lazy-chargés par `module.config.jsx`
//: (préfixe de chunk = nom du fichier source, convention Vite/Rollup par
//: défaut de ce dépôt — vérifié à chaque build).
const CHUNKS_DU_MODULE = [
  'CalepinageList', 'CalepinageNouveau', 'VariantesCompare',
  'FichesIncompletes', 'PompagePanel', 'PlanImporteCalage',
  'PhotoSiteCalage', 'SaisiePente', 'SchemaUnifilairePanel', 'Bibliotheque',
  'BadgePerime',
]

function fichiersDuModule() {
  const fichiers = readdirSync(DIST_ASSETS).filter((f) => f.endsWith('.js'))
  return CHUNKS_DU_MODULE
    .map((prefixe) => fichiers.find((f) => f.startsWith(`${prefixe}-`)))
    .filter(Boolean)
}

// ── 1. GARDE STATIQUE (toujours actif, aucun `dist/` requis) ──────────────

test('CAL224 — chaque écran du module est LAZY (jamais un import statique)', () => {
  const config = readFileSync(
    join(FRONTEND_ROOT, 'src', 'features', 'calepinage', 'module.config.jsx'),
    'utf8')
  for (const nom of CHUNKS_DU_MODULE) {
    if (nom === 'BadgePerime') continue // composant partagé, pas une route.
    const motif = new RegExp(
      `const ${nom} = lazy\\(\\(\\) => import\\('\\./[\\w/]*${nom}'\\)\\)`)
    assert.match(config, motif,
      `${nom} doit être importé via lazy(() => import(...)) dans `
      + 'module.config.jsx — un import statique ferait grossir le chunk '
      + 'd\u2019entrée pour un écran contextuel.')
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
