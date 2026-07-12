// K147 — Tests de la logique pure du thème graphique (node:test, sans DOM).
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CHART_TOKENS, resolveColor, prefersReducedMotion, animationDuration,
  CHART_ANIM_DURATION, BAR_RADIUS, BAR_RADIUS_H,
  CHART_CATEGORICAL, categoricalColor, CHART_GRID_STYLE,
  CHART_COMPARISON_STYLE, CHART_REFERENCE_LINE_STYLE,
} from './chart-theme.js'

test('resolveColor : nom de ton → var() token', () => {
  assert.equal(resolveColor('primary'), CHART_TOKENS.primary)
  assert.equal(resolveColor('info'), CHART_TOKENS.info)
  assert.equal(resolveColor('danger'), CHART_TOKENS.danger)
})

test('resolveColor : couleur CSS brute renvoyée telle quelle', () => {
  assert.equal(resolveColor('var(--custom)'), 'var(--custom)')
  assert.equal(resolveColor('#abc'), '#abc')
})

test('resolveColor : valeur vide → ton info par défaut', () => {
  assert.equal(resolveColor(), CHART_TOKENS.info)
  assert.equal(resolveColor(null), CHART_TOKENS.info)
})

test('toutes les couleurs du thème sont des tokens var() (jamais en dur)', () => {
  for (const v of Object.values(CHART_TOKENS)) {
    assert.match(v, /^var\(--/, `couleur non tokenisée: ${v}`)
  }
})

test('prefersReducedMotion : false hors navigateur (pas de window.matchMedia)', () => {
  // En environnement node sans matchMedia, doit renvoyer false sans planter.
  assert.equal(prefersReducedMotion(), false)
})

test('animationDuration : durée marque par défaut quand pas de réduction', () => {
  assert.equal(animationDuration(), CHART_ANIM_DURATION)
  assert.equal(animationDuration(250), 250)
})

test('BAR_RADIUS : coins hauts arrondis (vertical) et droite (horizontal)', () => {
  assert.deepEqual(BAR_RADIUS, [4, 4, 0, 0])
  assert.deepEqual(BAR_RADIUS_H, [0, 4, 4, 0])
})

// VX41 — Palette catégorielle de marque (séries multiples).
test('CHART_CATEGORICAL : toutes les couleurs sont des tokens var() (jamais en dur)', () => {
  assert.ok(CHART_CATEGORICAL.length >= 4)
  for (const v of CHART_CATEGORICAL) {
    assert.match(v, /^var\(--/, `couleur non tokenisée: ${v}`)
  }
})

test('categoricalColor : boucle sur la palette (index >= length)', () => {
  const n = CHART_CATEGORICAL.length
  assert.equal(categoricalColor(0), CHART_CATEGORICAL[0])
  assert.equal(categoricalColor(n), CHART_CATEGORICAL[0])
  assert.equal(categoricalColor(n + 2), CHART_CATEGORICAL[2])
})

test('CHART_GRID_STYLE : grille signature — horizontal seul, jamais vertical', () => {
  assert.equal(CHART_GRID_STYLE.horizontal, true)
  assert.equal(CHART_GRID_STYLE.vertical, false)
  assert.match(CHART_GRID_STYLE.strokeDasharray, /\d+ \d+/)
})

test('CHART_COMPARISON_STYLE : série « période précédente » en pointillé non remplie', () => {
  assert.match(CHART_COMPARISON_STYLE.strokeDasharray, /\d+ \d+/)
  assert.equal(CHART_COMPARISON_STYLE.fillOpacity, 0)
})

test('CHART_REFERENCE_LINE_STYLE : annotation d\'événement en pointillé tokenisé', () => {
  assert.match(CHART_REFERENCE_LINE_STYLE.stroke, /^var\(--/)
  assert.match(CHART_REFERENCE_LINE_STYLE.strokeDasharray, /\d+ \d+/)
})
