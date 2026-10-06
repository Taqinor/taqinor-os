import { test } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join } from 'node:path'
import { extraireCles } from './calepinageApi.usage.test.mjs'
import { lireSourceCalepinageApi } from './calepinage/lireSource.mjs'

/* ============================================================================
   SPL291 — GOLDEN de `calepinageApi.js`, capturé AVANT tout déplacement.
   ----------------------------------------------------------------------------
   Le fichier le plus chaud d'un seul propriétaire (88 clés de feuille + le
   CRUD partagé) va être éclaté en fragments (SPL292-SPL295, move only). Ce
   golden fige ce que la façade FAIT — pas ce que son texte dit :
     - chaque clé de `calepinageApi.calepinages|moteur|parametres` (et chaque
       méthode de `crud('calepinages')`) est APPELÉE avec des arguments fixes ;
     - un axios factice ENREGISTREUR remplace `./axios` (et lui seul) : la
       façade et `makeResourceFactory` sont les VRAIS modules ;
     - l'instantané `{verbe, url, data, config}` de chaque appel est comparé à
       `calepinageApi.golden.json`.

   L'ensemble des clés est un PLANCHER (⊇) : une capacité neuve ne rougit pas,
   une clé retirée ou une URL changée rougit et exige une mise à jour
   VOLONTAIRE de l'instantané dans le même commit :
     CALEPINAGE_GOLDEN_ECRIRE=1 node --test src/api/calepinageApi.golden.test.mjs

   Pourquoi `node:test` + un crochet de résolution plutôt que Vitest : CI ne
   lance les `*.test.mjs` que sous `node --test` (vitest n'inclut que
   `.test.js(x)`), et `calepinageApi.js` importe `./axios` / `./resource` SANS
   extension (résolution Vite). Le crochet ci-dessous ajoute `.js` aux imports
   relatifs de `src/api/` et sert `./axios` depuis l'enregistreur — rien
   d'autre n'est substitué (la source testée n'est jamais mockée).
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))
const GOLDEN_PATH = join(here, 'calepinageApi.golden.json')
const API_PATH = join(here, 'calepinageApi.js')

// Valeur CAPTURÉE le 04/10/2026 (79 `calepinages` + 3 `moteur` + 6 `parametres`, puis +2 en vague B, +4 en vague C ACAL, +1 ACAL222 remettreDocument, +2 ACAL23 enregistrerLayoutCalepinageConditionnel/enregistrerSectionLayout).
const NOMBRE_CLES_EXTRAITES = 98

/* ── L'axios factice ENREGISTREUR (module autonome, servi en data: URL) ──── */
const AXIOS_ENREGISTREUR = `
const appels = (globalThis.__CALEPINAGE_GOLDEN_APPELS__ ??= [])
const SANS_CORPS = new Set(['get', 'delete', 'head', 'options'])
const reponse = { data: { nom: 'source', roof_layout: { k: 1 }, resultat: { r: 1 } } }
function verbe(nom) {
  return (url, a, b) => {
    appels.push(SANS_CORPS.has(nom)
      ? { verbe: nom, url, data: null, config: a }
      : { verbe: nom, url, data: a, config: b })
    return Promise.resolve(reponse)
  }
}
export default {
  get: verbe('get'), post: verbe('post'), put: verbe('put'),
  patch: verbe('patch'), delete: verbe('delete'),
}
`

const CROCHETS = `
const AXIOS = ${JSON.stringify(`data:text/javascript,${encodeURIComponent(AXIOS_ENREGISTREUR)}`)}
const API_DIR = ${JSON.stringify(pathToFileURL(here).href + '/')}
export async function resolve(specifier, context, next) {
  const parent = context.parentURL || ''
  if (parent.startsWith(API_DIR) && (specifier === './axios' || specifier === '../axios')) {
    return { url: AXIOS, shortCircuit: true }
  }
  if (parent.startsWith(API_DIR) && /^\\.\\.?\\//.test(specifier) && !/\\.[cm]?js$/.test(specifier)) {
    return next(specifier + '.js', context)
  }
  return next(specifier, context)
}
`
register(`data:text/javascript,${encodeURIComponent(CROCHETS)}`)

const { default: calepinageApi } = await import(pathToFileURL(API_PATH).href)
const APPELS = globalThis.__CALEPINAGE_GOLDEN_APPELS__

/* ── Arguments fixes par clé (défaut [7, 3, {k: 1}, 'x']) ─────────────────── */
function formulaire() {
  const fd = new FormData()
  fd.append('fichier', new Blob(['abc'], { type: 'image/png' }), 'toit.png')
  fd.append('genre', 'photo')
  return fd
}
const DEFAUT = () => [7, 3, { k: 1 }, 'x']
const ARGS = {
  'calepinages.envoyerImage': () => [7, formulaire()],
  'calepinages.ajouterPhoto': () => [7, formulaire()],
  'calepinages.deposerMeteoFichier': () => [7, formulaire()],
  'calepinages.importerPlan': () => [7, formulaire()],
  'calepinages.importerProjet': () => [formulaire()],
  'calepinages.deposerImageDocument': () => [7, { genre: 'plan', fichier: 'data:x' }],
  'calepinages.telechargerSortie': () => ['/calepinage/calepinages/7/sorties/x/', { k: 1 }],
  'calepinages.telechargerDocument': () => ['/calepinage/calepinages/7/documents/x/', { k: 1 }],
  'calepinages.simuler': () => [7, { forcer: true }],
  'calepinages.comparatifXlsx': () => [7, [8, 9]],
  'calepinages.comparerProjets': () => [[7, 8]],
  'calepinages.dupliquerVariante': () => [7, 3, 'Ma copie'],
}

/* ── Sérialisation stable d'un appel (FormData/Blob/undefined lisibles) ──── */
function normaliser(valeur) {
  if (valeur === undefined) return null
  if (typeof FormData !== 'undefined' && valeur instanceof FormData) {
    return { FormData: [...valeur.entries()].map(([k, v]) => [k, normaliser(v)]) }
  }
  if (typeof Blob !== 'undefined' && valeur instanceof Blob) {
    return { Blob: { type: valeur.type, size: valeur.size, name: valeur.name ?? null } }
  }
  if (Array.isArray(valeur)) return valeur.map(normaliser)
  if (valeur && typeof valeur === 'object') {
    return Object.fromEntries(Object.keys(valeur).sort().map((k) => [k, normaliser(valeur[k])]))
  }
  return valeur
}

async function instantane() {
  const out = {}
  for (const ns of Object.keys(calepinageApi).sort()) {
    for (const cle of Object.keys(calepinageApi[ns]).sort()) {
      const id = `${ns}.${cle}`
      const args = (ARGS[id] ?? DEFAUT)()
      APPELS.length = 0
      await calepinageApi[ns][cle](...args)
      out[id] = APPELS.map(normaliser)
    }
  }
  return out
}

const actuel = await instantane()

if (process.env.CALEPINAGE_GOLDEN_ECRIRE === '1') {
  writeFileSync(GOLDEN_PATH, `${JSON.stringify(actuel, null, 2)}\n`)
}
const golden = JSON.parse(readFileSync(GOLDEN_PATH, 'utf8'))

/* ── Verdict pur, réutilisé par le test-du-test ci-dessous ────────────────── */
export function comparerAuGolden(reference, courant) {
  const ecarts = []
  for (const id of Object.keys(reference)) {
    if (!(id in courant)) {
      ecarts.push(`${id} : clé retirée de la façade`)
    } else if (JSON.stringify(reference[id]) !== JSON.stringify(courant[id])) {
      ecarts.push(`${id} : ${JSON.stringify(reference[id])} → ${JSON.stringify(courant[id])}`)
    }
  }
  return ecarts
}

test('SPL291 — chaque clé figée appelle le MÊME verbe/URL/corps/config (plancher ⊇)', () => {
  const ecarts = comparerAuGolden(golden, actuel)
  assert.deepEqual(ecarts, [],
    `Écart au golden — si c'est voulu, régénérer l'instantané dans le même commit :\n${ecarts.join('\n')}`)
})

test('SPL291 — le golden couvre toutes les clés de feuille + le CRUD partagé', () => {
  const cles = Object.keys(golden)
  for (const m of ['list', 'get', 'create', 'update', 'remove']) {
    assert.ok(cles.includes(`calepinages.${m}`), `crud('calepinages').${m} absent du golden`)
  }
  // 90 clés de feuille + 5 méthodes CRUD.
  assert.equal(cles.length, NOMBRE_CLES_EXTRAITES + 5)
  for (const id of cles) assert.ok(golden[id].length >= 1, `${id} n'a émis aucun appel HTTP`)
})

test('SPL291 — extraireCles(calepinageApi.js) rend exactement les NOMBRE_CLES_EXTRAITES clés capturées', () => {
  const cles = extraireCles(lireSourceCalepinageApi())
  assert.equal(cles.length, NOMBRE_CLES_EXTRAITES)
  const runtime = new Set(Object.keys(golden))
  for (const { namespace, cle } of cles) {
    assert.ok(runtime.has(`${namespace}.${cle}`), `${namespace}.${cle} extraite mais non servie`)
  }
})

/* ── Test-du-test : le golden ROUGIT sur une façade mutée ─────────────────── */
test('SPL291 — test-du-test : une URL mutée ou une clé retirée rougit', () => {
  const muteUrl = structuredClone(golden)
  muteUrl['calepinages.layout'][0].url = '/calepinage/calepinages/7/layout-MUTE/'
  assert.equal(comparerAuGolden(golden, muteUrl).length, 1)

  const sansCle = structuredClone(golden)
  delete sansCle['moteur.pose']
  assert.match(comparerAuGolden(golden, sansCle).join('\n'), /moteur\.pose : clé retirée/)

  const avecCleNeuve = { ...structuredClone(golden), 'calepinages.capaciteNeuve': [] }
  assert.deepEqual(comparerAuGolden(golden, avecCleNeuve), [], 'une clé neuve ne rougit pas')

  // Nombre de clés muté dans une copie du source ⇒ extraireCles s'écarte de 92.
  const src = lireSourceCalepinageApi()
  const mute = src.replace(/^ {4}modeles: \(\) =>[^\n]*\n/m, '')
  assert.notEqual(mute, src)
  assert.equal(extraireCles(mute).length, NOMBRE_CLES_EXTRAITES - 1)
})
