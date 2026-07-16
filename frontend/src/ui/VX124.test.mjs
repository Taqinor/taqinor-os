// VX124 — Craft-physics pack : les 4 micro-détails qui signent un produit
// investi (caret teinté, ombre brass au survol du CTA primaire, tracking
// desserré sur montants tabulaires 7 chiffres, wght qui "se solidifie" sur
// le chiffre KPI). Vérification de SOURCE (pas de node_modules installés
// dans ce lane — cf. Stat.test.mjs) :
//   node --test src/ui/VX124.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const INPUT_SRC = readFileSync(join(HERE, 'Input.jsx'), 'utf8')
const TEXTAREA_SRC = readFileSync(join(HERE, 'Textarea.jsx'), 'utf8')
const NUMBER_INPUTS_SRC = readFileSync(join(HERE, 'NumberInputs.jsx'), 'utf8')
const BUTTON_SRC = readFileSync(join(HERE, 'Button.jsx'), 'utf8')
const STAT_SRC = readFileSync(join(HERE, 'Stat.jsx'), 'utf8')
const TOKENS_SRC = readFileSync(join(HERE, '..', 'design', 'tokens.css'), 'utf8')

test('(a) Input pose caret-primary sur le champ de base (curseur teinté marque)', () => {
  assert.match(INPUT_SRC, /caret-primary/)
})

test('(a) Textarea pose aussi caret-primary', () => {
  assert.match(TEXTAREA_SRC, /caret-primary/)
})

test('(a) NumberInputs (Number/Currency/Percent/Phone) héritent de Input — donc du caret teinté', () => {
  // Les 4 variantes rendent toutes <Input ...> : pas de <input> brut qui
  // court-circuiterait le style de base.
  assert.match(NUMBER_INPUTS_SRC, /<Input\b/)
  assert.doesNotMatch(NUMBER_INPUTS_SRC, /<input\b/)
})

test('(b) tokens.css définit --shadow-primary-hover (ombre teintée brass, pas gris neutre)', () => {
  assert.match(TOKENS_SRC, /--shadow-primary-hover:/)
  assert.match(TOKENS_SRC, /--shadow-primary-hover:[^;]*color-mix\(in oklch, var\(--primary\)/)
})

test('(b) --shadow-primary-hover est exposé en utilitaire Tailwind (--shadow-ui-primary-hover)', () => {
  assert.match(TOKENS_SRC, /--shadow-ui-primary-hover: var\(--shadow-primary-hover\)/)
})

test('(b) seul le variant Button "default" (CTA primaire) porte hover:shadow-ui-primary-hover', () => {
  const defaultVariantLine = BUTTON_SRC.split('\n').find((l) => l.includes("default:"))
  assert.ok(defaultVariantLine, 'variant default introuvable dans Button.jsx')
  assert.match(defaultVariantLine + BUTTON_SRC.slice(BUTTON_SRC.indexOf(defaultVariantLine)), /hover:shadow-ui-primary-hover/)
  for (const otherVariant of ['secondary:', 'outline:', 'ghost:', 'destructive:', 'success:', 'link:']) {
    const line = BUTTON_SRC.split('\n').find((l) => l.trim().startsWith(otherVariant))
    assert.ok(line, `variant ${otherVariant} introuvable`)
    assert.doesNotMatch(line, /shadow-ui-primary-hover/)
  }
})

test('(c) tokens.css desserre le tracking à -0.01em sur les montants tabulaires display/h1', () => {
  assert.match(
    TOKENS_SRC,
    /\.tabular-nums\.text-display,\s*\n\.tabular-nums\.text-h1\s*\{\s*letter-spacing:\s*-0\.01em;\s*\}/,
  )
})

test('(d) tokens.css anime font-variation-settings (wght 500→600) via --motion-slow', () => {
  assert.match(TOKENS_SRC, /\.stat-value-solidify\s*\{[^}]*font-variation-settings:\s*'wght'\s*600/)
  assert.match(TOKENS_SRC, /animation:\s*stat-solidify\s*var\(--motion-slow\)/)
  assert.match(
    TOKENS_SRC,
    /@keyframes stat-solidify\s*\{\s*from\s*\{\s*font-variation-settings:\s*'wght'\s*500\s*\}\s*to\s*\{\s*font-variation-settings:\s*'wght'\s*600\s*\}\s*\}/,
  )
})

test('(d) --motion-slow retombe à 0ms sous prefers-reduced-motion (neutralise la transition)', () => {
  const reducedMotionBlock = TOKENS_SRC.slice(
    TOKENS_SRC.indexOf('@media (prefers-reduced-motion: reduce)'),
  )
  assert.match(reducedMotionBlock, /--motion-slow:\s*0ms/)
})

test('(d) Stat.jsx applique .stat-value-solidify sur le chiffre KPI (pas sur la carte entière)', () => {
  assert.match(STAT_SRC, /stat-value-solidify/)
})
