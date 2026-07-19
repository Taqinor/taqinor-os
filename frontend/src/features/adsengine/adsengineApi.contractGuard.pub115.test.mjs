import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   PUB115 — Garde de contrat API front↔back du module Publicité.
   ----------------------------------------------------------------------------
   PUB1/PUB2 ont dû réparer des écrans construits AVANT leurs routes backend
   (`DashboardScreen` onglet Signaux, TreeScreen ses 3 panneaux) : le front
   appelait un chemin qui n'existait nulle part côté ``apps/adsengine/
   {urls.py,views.py}`` → 404 silencieux. Ce test rend cette classe de bug
   STRUCTURELLEMENT IMPOSSIBLE à réintroduire : il énumère automatiquement
   chaque chemin que ``adsengineApi.js`` appelle et vérifie qu'il résout un
   pattern RÉEL du côté backend — routeur DRF (``router.register``), patterns
   directs (``path(...)`` dans ``urlpatterns``), et actions ``@action``
   (``url_path`` explicite ou repli sur le nom de méthode — le comportement
   RÉEL de DRF quand ``url_path`` est omis, PAS une conversion underscore→
   tiret : vérifié contre plusieurs actions du fichier qui comptent sur ce
   repli, ex. ``publish``/``approve``/``templates``).

   Simplification délibérée : l'extraction des ``@action`` est GLOBALE (pas
   rattachée à SON ViewSet précis) — suffisant pour prouver qu'une route
   EXISTE quelque part (la classe de bug visée), pas qu'elle est posée sur
   EXACTEMENT le bon ViewSet (aucune collision de nom d'action constatée dans
   ce fichier à l'écriture de ce test). Le e2e (PUB14) ne couvre PAS cette
   classe (il navigue l'UI, jamais tous les chemins d'API un par un).

   Lecture directe des fichiers SOURCE (texte), sans exécuter Django — le
   test tourne dans ``node --test`` (auto-découverte CI, zéro dépendance npm),
   pas dans Vitest (cf. ``vitest.config.js``).
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(here, '..', '..', '..', '..')
const apiSrc = readFileSync(join(here, 'adsengineApi.js'), 'utf8')
const urlsSrc = readFileSync(
  join(repoRoot, 'backend', 'django_core', 'apps', 'adsengine', 'urls.py'), 'utf8')
const viewsSrc = readFileSync(
  join(repoRoot, 'backend', 'django_core', 'apps', 'adsengine', 'views.py'), 'utf8')

// ── Backend : préfixes routés (DRF router) ──────────────────────────────────
function extractRouterPrefixes(src) {
  return new Set([...src.matchAll(/router\.register\(\s*r?'([^']+)'/g)].map(m => m[1]))
}

// ── Backend : patterns directs (`path('...', View.as_view())` hors routeur) ─
function extractDirectPaths(src) {
  return [...src.matchAll(/\bpath\(\s*'([^']*)'/g)]
    .map(m => m[1])
    .filter(p => p !== '') // exclut path('', include(router.urls))
}

// Scanner à profondeur de parenthèses — bulletproof face aux parens imbriquées
// dans les arguments d'un `@action(...)` (ex. `permission_classes=[Has...(...)]`).
function findMatchingParen(str, openIdx) {
  let depth = 0
  for (let i = openIdx; i < str.length; i++) {
    if (str[i] === '(') depth++
    else if (str[i] === ')') {
      depth--
      if (depth === 0) return i
    }
  }
  return -1
}

// ── Backend : actions `@action` (detail True/False + url_path) ─────────────
function extractActions(src) {
  const actions = []
  const re = /@action\(/g
  let m
  while ((m = re.exec(src))) {
    const openIdx = m.index + '@action'.length
    const closeIdx = findMatchingParen(src, openIdx)
    if (closeIdx === -1) continue
    const argsBlob = src.slice(openIdx + 1, closeIdx)
    const detailMatch = argsBlob.match(/detail\s*=\s*(True|False)/)
    const detail = detailMatch ? detailMatch[1] === 'True' : true
    const urlPathMatch = argsBlob.match(/url_path\s*=\s*r?'([^']+)'/)
    const after = src.slice(closeIdx + 1)
    const defMatch = after.match(/^\s*\n(?:\s*@[^\n]*\n)*\s*def\s+(\w+)\s*\(/)
    if (!defMatch) continue
    const methodName = defMatch[1]
    const urlPath = urlPathMatch ? urlPathMatch[1] : methodName
    actions.push({ detail, urlPath })
  }
  return actions
}

const routerPrefixes = extractRouterPrefixes(urlsSrc)
const directPaths = extractDirectPaths(urlsSrc)
const actions = extractActions(viewsSrc)
const listActionPaths = new Set(actions.filter(a => !a.detail).map(a => a.urlPath))
const detailActionPaths = new Set(actions.filter(a => a.detail).map(a => a.urlPath))
// url_path paramétrés (ex. r'tests/(?P<test_id>[^/.]+)/leads') : comparés
// segment par segment — un segment-groupe regex matche n'importe quel segment.
const actionSegPatterns = actions.map(a => ({
  detail: a.detail,
  // Un groupe nommé peut contenir '/' (ex. [^/.]+) — le remplacer par un
  // jeton AVANT de découper en segments.
  segs: a.urlPath.replace(/\(\?P<[^>]+>[^)]*\)/g, '@@PARAM@@').split('/').filter(Boolean),
}))
function segMatch(patSegs, segs) {
  if (patSegs.length !== segs.length) return false
  return patSegs.every((p, i) => (p === '@@PARAM@@' ? segs[i].length > 0 : p === segs[i]))
}

// ── Front : chaque chemin appelé par adsengineApi.js ────────────────────────
function extractResourcePrefixes(src) {
  return [...src.matchAll(/\.\.\.resource\('([^']+)'\)/g)].map(m => m[1])
}

function extractFrontCalls(src) {
  const calls = new Set()
  // Littéraux simples : api.get('/adsengine/...'), api.post('/adsengine/...', payload)
  for (const m of src.matchAll(/api\.(?:get|post|patch|delete)\(\s*'(\/adsengine\/[^']*)'/g)) {
    calls.add(m[1])
  }
  // Template literals : api.get(`/adsengine/actions/${id}/approve/`) — chaque
  // interpolation devient un segment dynamique placeholder ('1').
  for (const m of src.matchAll(/api\.(?:get|post|patch|delete)\(\s*`(\/adsengine\/[^`]*)`/g)) {
    calls.add(m[1].replace(/\$\{[^}]*\}/g, '1'))
  }
  // Fabrique CRUD `...resource('prefix')` (makeResourceFactory) : synthétise
  // les 2 formes qu'elle génère (list/create sur la racine, get/update/remove
  // sur un id).
  for (const prefix of extractResourcePrefixes(src)) {
    calls.add(`/adsengine/${prefix}/`)
    calls.add(`/adsengine/${prefix}/1/`)
  }
  return [...calls].sort()
}

const frontCalls = extractFrontCalls(apiSrc)

// ── Résolution : ce chemin front matche-t-il un pattern backend réel ? ──────
function isIdSegment(seg) {
  return /^\d+$/.test(seg)
}

function directPathMatches(segments) {
  return directPaths.some(dp => {
    const dpSegs = dp.split('/').filter(Boolean)
    if (dpSegs.length !== segments.length) return false
    return dpSegs.every((seg, i) => /^<[^>]+>$/.test(seg) || seg === segments[i])
  })
}

function resolvable(path) {
  const rel = path.replace(/^\/adsengine\//, '')
  const segments = rel.split('/').filter(Boolean)
  if (segments.length === 0) return false
  const [first, ...rest] = segments

  if (routerPrefixes.has(first)) {
    if (rest.length === 0) return true // list/create sur la racine du routeur
    if (rest.length === 1) {
      // <id>/ (retrieve/update/delete) OU une action detail=False
      return isIdSegment(rest[0]) || listActionPaths.has(rest[0])
    }
    if (rest.length === 2 && isIdSegment(rest[0])) {
      // <id>/<action>/ — action detail=True
      return detailActionPaths.has(rest[1])
    }
    // Actions à url_path paramétré (PUB2 : tests/(?P<test_id>…)/leads) —
    // liste d'abord, puis détail derrière un segment id.
    if (actionSegPatterns.some(a => !a.detail && segMatch(a.segs, rest))) return true
    if (rest.length >= 2 && isIdSegment(rest[0])
        && actionSegPatterns.some(a => a.detail && segMatch(a.segs, rest.slice(1)))) return true
    // Sinon : repli légitime sur les patterns directs ci-dessous.
  }

  return directPathMatches(segments)
}

// GATED — gaps CONNUS et déjà TRACÉS par un autre item de plan (jamais un
// moyen d'ignorer une future régression : seuls ces chemins EXACTS sont
// concernés, tout AUTRE chemin non-résolu échoue normalement). Un item retiré
// de cette liste dès que sa route atterrit — la ligne du plan documente le
// pourquoi, pas ce fichier.
//   - PUB1 (lane backend/adsengine-wiring) : signaux/ + signaux/cohorte/.
//   - PUB2 (lane backend/adsengine-wiring) : file-voi/, <id>/tests/,
//     tests/<id>/leads/ sur noeuds-hypothese/.
const KNOWN_GAPS = new Map([
  // (vide — PUB1/PUB2 ont livré les routes signaux/ et noeuds-hypothese/*.
  //  N'ajouter une entrée ICI que pour un front livré AVANT sa route, jamais
  //  pour excuser une régression.)
])

for (const path of frontCalls) {
  const gate = KNOWN_GAPS.get(path)
  const check = () => {
    assert.equal(resolvable(path), true,
      `Aucune route backend ne résout ${path} (apps/adsengine/{urls.py,views.py}). ` +
      "Si la route vient d'être retirée côté back, retire aussi l'appel front ; " +
      "si le front vient d'être livré, construis d'abord la route (règle du garde).")
  }
  if (gate) {
    // TODO structuré (pas un skip silencieux) : visible dans le rapport de
    // run, ne fait pas échouer le garde, DISPARAÎT de lui-même (assertion
    // qui passerait alors) le jour où la route atterrit — à retirer de
    // KNOWN_GAPS à ce moment (sinon une VRAIE régression sur ce chemin
    // précis resterait masquée).
    test(`adsengineApi.js -> ${path} résout un pattern réel de urls.py/views.py`,
      { todo: `gap connu, attend ${gate} (lane backend/adsengine-wiring)` }, check)
  } else {
    test(`adsengineApi.js -> ${path} résout un pattern réel de urls.py/views.py`, check)
  }
}

// Filet de sécurité : si une route KNOWN_GAPS est en fait DÉJÀ résolvable
// (le jour où PUB1/PUB2 atterrissent, ou par erreur dès aujourd'hui), on le
// signale explicitement — sinon KNOWN_GAPS resterait périmé indéfiniment.
test('KNOWN_GAPS ne contient aucune route déjà résolue (à nettoyer sinon)', () => {
  const stale = [...KNOWN_GAPS.keys()].filter(p => resolvable(p))
  assert.deepEqual(stale, [],
    `Ces chemins de KNOWN_GAPS résolvent déjà une route réelle — retire-les ` +
    `de la liste : ${stale.join(', ')}`)
})

// Sanity check du garde lui-même : si l'extraction régresse à (quasi) zéro
// chemin, TOUS les tests ci-dessus disparaîtraient silencieusement plutôt que
// d'échouer — le garde masquerait alors toute dérive future. On échoue donc
// bruyamment si le compte de chemins extraits s'effondre.
test('le garde de contrat couvre un nombre plausible de chemins (extraction non régressée)', () => {
  assert.ok(frontCalls.length > 40,
    `Seulement ${frontCalls.length} chemin(s) extrait(s) de adsengineApi.js — ` +
    "l'extraction a probablement régressé (vérifier les regex de ce test).")
})
