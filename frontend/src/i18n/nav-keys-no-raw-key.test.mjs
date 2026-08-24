import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { resolveValueWithCatalogs, LOCALES } from './resolve.js'

// Bug fondateur (24/08) : des clés i18n NUES s'affichaient dans la nav ERP
// (ex. `nav.crm_cockpit`) — `module.config.jsx` déclare chaque entrée avec
// `label:` (FR) ET `k:` (clé i18n), mais le repli sur `label` était mort code
// (cf. `Sidebar.jsx` `tr()` + `resolveValue()`/`resolveValueWithCatalogs()`
// dans `context.js`/`resolve.js`) : une clé absente du dictionnaire retombait
// sur la CLÉ BRUTE, jamais sur `label`.
//
// Ce test rejoue exactement l'algorithme de résolution de production
// (`resolveValueWithCatalogs`, importé depuis `resolve.js` — pas
// réimplémenté ; ce module est la partie PURE, zéro dépendance React/JSON,
// du cadre i18n, ce qui le rend chargeable par `node --test` comme le reste
// des `*.test.mjs` du dépôt) contre les VRAIS catalogues fr/en/ar (relus ici
// via `readFileSync`, comme `i18n-coverage.test.mjs` — `context.js`, lui,
// lie exactement le même algorithme aux mêmes catalogues via
// `i18nCatalogs.js`) sur CHAQUE clé `nav.*` réellement déclarée dans les
// `module.config.jsx` (+ `ActiveAppContext.jsx`, qui déclare aussi des
// entrées de nav hors module « coquille ») et prouve qu'aucune ne peut plus
// rendre sa propre clé brute, dans les 3 locales.
//
// Preuve de rouge (rejouable à la main) :
//   - retirer `fallback` de `resolveValueWithCatalogs(...)` dans `resolve.js`
//     (ou l'appel `t(key, undefined, fallback)` dans `Sidebar.jsx`) → ce test
//     échoue à nouveau sur toute clé absente d'un catalogue.
//   - ou supprimer une entrée `nav.*` d'un des 3 catalogues → ce test échoue
//     UNIQUEMENT si le libellé de repli lui-même venait à être vide/absent
//     (sinon le repli couvre — c'est justement l'invariant prouvé ici).

const here = path.dirname(fileURLToPath(import.meta.url))
const srcDir = path.join(here, '..')
const featuresDir = path.join(srcDir, 'features')
const catalogsDir = path.join(here, 'catalogs')

function loadCatalog(locale) {
  return JSON.parse(readFileSync(path.join(catalogsDir, `${locale}.json`), 'utf8'))
}
const CATALOGS = { fr: loadCatalog('fr'), en: loadCatalog('en'), ar: loadCatalog('ar') }
const resolveValue = (key, locale, overrides, fallback) =>
  resolveValueWithCatalogs(key, locale, overrides, fallback, CATALOGS)

// Repère chaque objet `{ ... }` du fichier par appariement d'accolades, et
// retient — pour chaque `k: 'nav.xxx'` — l'objet le plus PETIT qui le
// contient (l'entrée de nav elle-même, jamais un objet englobant comme une
// section ou un tableau `items`), avec le `label:` FR qui l'accompagne.
function extractNavEntries(filePath) {
  const text = readFileSync(filePath, 'utf8')
  const stack = []
  const objects = []
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '{') stack.push(i)
    else if (c === '}') {
      const start = stack.pop()
      if (start !== undefined) objects.push([start, i])
    }
  }
  const byKey = new Map()
  for (const [s, e] of objects) {
    const body = text.slice(s, e + 1)
    const km = body.match(/\bk:\s*['"]([^'"]+)['"]/)
    if (!km || !km[1].startsWith('nav.')) continue
    const lm = body.match(/\blabel:\s*(?:'([^']*(?:\\'[^']*)*)'|"([^"]*)")/)
    const label = lm ? (lm[1] ?? lm[2]).replace(/\\'/g, "'") : null
    const key = km[1]
    const bodyLen = body.length
    const prev = byKey.get(key)
    if (!prev || prev.bodyLen > bodyLen) {
      byKey.set(key, { key, label, file: path.relative(srcDir, filePath), bodyLen })
    }
  }
  return [...byKey.values()]
}

function collectModuleConfigFiles() {
  const files = []
  for (const entry of readdirSync(featuresDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const candidate = path.join(featuresDir, entry.name, 'module.config.jsx')
    if (existsSync(candidate)) files.push(candidate)
  }
  files.push(path.join(srcDir, 'lib', 'apps', 'ActiveAppContext.jsx'))
  return files
}

const files = collectModuleConfigFiles()
const entries = files.flatMap(extractNavEntries)

test('nav-keys: at least one module.config.jsx / ActiveAppContext.jsx nav.* key is found (sanity)', () => {
  // Garde-fou anti-faux-positif : si l'extraction casse silencieusement (ex.
  // renommage de `k:`/`label:`), ce test le détecte avant que les assertions
  // ci-dessous ne deviennent vides et donc trivialement vertes.
  assert.ok(entries.length >= 30, `expected >=30 declared nav.* keys, found ${entries.length}`)
})

test('nav-keys: every declared nav.* key resolves to real text — NEVER the raw key — in fr/en/ar', () => {
  const failures = []
  for (const { key, label, file } of entries) {
    for (const locale of LOCALES) {
      // Même chemin que `Sidebar.jsx` : `tr(item.k, item.label)` →
      // `t(key, undefined, fallback)` → `resolveValue(key, locale, overrides, fallback)`.
      const resolved = resolveValue(key, locale, null, label)
      if (resolved === key) {
        failures.push(`${key} (${file}, locale=${locale}) rendered the RAW KEY`)
      }
    }
  }
  assert.deepEqual(failures, [], `nav.* keys rendering their raw key:\n${failures.join('\n')}`)
})

test('nav-keys: resolveValue falls back to the provided label — never the raw key — for a key missing from every catalog (synthetic red-proof)', () => {
  const missingKey = 'nav.__does_not_exist_in_any_catalog__'
  for (const locale of LOCALES) {
    assert.equal(resolveValue(missingKey, locale, null, 'Libellé de repli'), 'Libellé de repli')
  }
  // Sans fallback fourni, le comportement historique (clé = filet de sécurité
  // de debug) reste inchangé — pas de régression du contrat existant de `t()`.
  assert.equal(resolveValue(missingKey, 'fr', null), missingKey)
})
