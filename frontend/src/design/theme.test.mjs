import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  normalizeTheme, normalizeDensity, resolveTheme, THEMES, DENSITIES,
  TEXT_SCALE, FORMAT_FEATURES, tabularNumStyle, applyThemeWithTransition,
} from './theme.js'

const tokensCss = readFileSync(
  fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf8',
)

/** Récupère la valeur d'un custom prop (première occurrence) dans tokens.css. */
function tokenValue(name) {
  const m = tokensCss.match(new RegExp(`${name}\\s*:\\s*([^;]+);`))
  return m ? m[1].trim() : null
}

test('normalizeTheme: valeurs valides + repli système', () => {
  assert.equal(normalizeTheme('light'), 'light')
  assert.equal(normalizeTheme('dark'), 'dark')
  assert.equal(normalizeTheme('system'), 'system')
  assert.equal(normalizeTheme('bidon'), 'system')
  assert.equal(normalizeTheme(null), 'system')
  assert.deepEqual(THEMES, ['light', 'dark', 'system'])
})

test('normalizeDensity: défaut comfortable', () => {
  assert.equal(normalizeDensity('compact'), 'compact')
  assert.equal(normalizeDensity('comfortable'), 'comfortable')
  assert.equal(normalizeDensity('xxl'), 'comfortable')
  assert.deepEqual(DENSITIES, ['comfortable', 'compact'])
})

test('resolveTheme: système suit l’OS, explicite est respecté', () => {
  assert.equal(resolveTheme('system', true), 'dark')
  assert.equal(resolveTheme('system', false), 'light')
  assert.equal(resolveTheme('light', true), 'light')
  assert.equal(resolveTheme('dark', false), 'dark')
  assert.equal(resolveTheme('bidon', true), 'dark') // repli système
})

/* ── F120 — primitives de marque en OKLCH, sans régression visuelle ─────── */
test('F120: toutes les primitives de marque utilisent oklch()', () => {
  const primitives = [
    '--color-brass-50', '--color-brass-100', '--color-brass-200',
    '--color-brass-300', '--color-brass-400', '--color-brass-500',
    '--color-brass-600', '--color-brass-700',
    '--color-nuit', '--color-nuit-800', '--color-nuit-700',
    '--color-encre', '--color-encre-soft', '--color-encre-faint',
    '--color-azur-100', '--color-azur-200', '--color-azur-600',
    '--color-azur-700', '--color-azur-900', '--color-azur-950',
    '--color-lune', '--color-lune-soft', '--color-lune-faint',
  ]
  for (const name of primitives) {
    const v = tokenValue(name)
    assert.ok(v, `${name} doit exister`)
    assert.match(v, /^oklch\(/, `${name} doit être en oklch()`)
  }
})

test('F120: la couche sémantique conserve exactement les hex rendus', () => {
  // Garde anti-régression : si l'une de ces valeurs change, un écran change.
  const semantic = {
    '--background': '#f6f8fc',
    '--foreground': '#0c1335',
    '--primary': '#e8b54a',
    '--border': '#dde3f0',
  }
  for (const [name, hex] of Object.entries(semantic)) {
    assert.equal(tokenValue(name), hex, `${name} doit rester ${hex}`)
  }
})

/* ── F121 — échelle typographique + utilitaires de format ────────────────── */
test('F121: TEXT_SCALE a 7 paliers à tracking de plus en plus négatif', () => {
  assert.deepEqual(
    Object.keys(TEXT_SCALE),
    ['display', 'h1', 'h2', 'h3', 'body', 'small', 'caption'],
  )
  const ls = (k) => parseFloat(TEXT_SCALE[k].letterSpacing)
  // letter-spacing croît négativement des petits aux grands titres.
  assert.ok(ls('display') < ls('h1'))
  assert.ok(ls('h1') < ls('h2'))
  assert.ok(ls('h2') < ls('h3'))
  assert.ok(ls('h3') < ls('body'))
  assert.equal(ls('body'), 0)
})

test('F121: TEXT_SCALE correspond exactement aux tokens --text-*', () => {
  for (const [key, def] of Object.entries(TEXT_SCALE)) {
    assert.equal(tokenValue(`--text-${key}`), def.size, `--text-${key}`)
    assert.equal(tokenValue(`--text-${key}-lh`), def.lineHeight, `--text-${key}-lh`)
    assert.equal(tokenValue(`--text-${key}-ls`), def.letterSpacing, `--text-${key}-ls`)
  }
})

test('F121: utilitaire de format = chiffres tabulaires + zéro barré', () => {
  const style = tabularNumStyle()
  assert.equal(style.fontVariantNumeric, 'tabular-nums slashed-zero')
  assert.match(style.fontFeatureSettings, /'tnum' 1/)
  assert.match(style.fontFeatureSettings, /'zero' 1/)
  // Copie défensive : ne renvoie pas la constante gelée elle-même.
  assert.notEqual(style, FORMAT_FEATURES)
  // Le token CSS .tabular-nums porte les mêmes réglages.
  assert.match(tokensCss, /font-variant-numeric:\s*tabular-nums slashed-zero/)
  assert.match(tokensCss, /font-feature-settings:\s*'tnum' 1, 'zero' 1/)
})

/* ── VX134(e) — bascule de thème avec transition transitoire ─────────────── */
test('applyThemeWithTransition : classe transitoire posée puis retirée (jamais permanente)', async () => {
  const classes = new Set()
  const fakeRoot = {
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c) },
      contains: (c) => classes.has(c),
    },
    style: {},
    setAttribute: () => {},
  }
  globalThis.document = { documentElement: fakeRoot, querySelector: () => null }
  globalThis.window = { matchMedia: () => ({ matches: false }) }
  try {
    applyThemeWithTransition('dark')
    // Posée + thème appliqué IMMÉDIATEMENT (aucun FOUC — pas d'attente avant
    // que .dark n'apparaisse).
    assert.ok(classes.has('theme-transitioning'), 'la classe transitoire doit être posée tout de suite')
    assert.ok(classes.has('dark'), 'le thème doit être appliqué tout de suite, sans attendre la transition')
    await new Promise((resolve) => { setTimeout(resolve, 260) })
    assert.ok(!classes.has('theme-transitioning'), 'la classe transitoire doit être retirée après coup — jamais permanente')
  } finally {
    delete globalThis.document
    delete globalThis.window
  }
})
