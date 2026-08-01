// APX34 — le DERNIER trou de densité : les tables CSS legacy `.data-table`
// obéissent enfin à la préférence globale.
// État RE-vérifié : `useDensity()` pilotait déjà les 56 écrans DataTable
// (32/40 px), la densité par vue est LIVRÉE (NTUX17), les libellés existent
// déjà dans Mes préférences — le seul trou réel était `.data-table td/th`,
// rendue à la main par ~66 écrans, que basculer la préférence ne changeait
// pas d'un pixel. Aucun nouveau système de densité n'est introduit.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const css = readFileSync(path.join(__dirname, '..', 'index.css'), 'utf8')
const tokens = readFileSync(path.join(__dirname, 'tokens.css'), 'utf8')

function rule(selector, from = 0) {
  const i = css.indexOf(selector + ' {', from)
  assert.ok(i > 0, `${selector} introuvable`)
  return css.slice(i, css.indexOf('}', i))
}

test('le token de densité --row-py existe dans les DEUX densités', () => {
  const conf = tokens.slice(tokens.indexOf("[data-density='comfortable']"))
  assert.match(conf.slice(0, conf.indexOf('}')), /--row-py: 0\.625rem/)
  const comp = tokens.slice(tokens.indexOf("[data-density='compact']"))
  assert.match(comp.slice(0, comp.indexOf('}')), /--row-py: 0\.375rem/)
})

test('les tables legacy dérivent leur hauteur de ligne du token', () => {
  for (const sel of ['.data-table th', '.data-table td']) {
    const r = rule(sel)
    assert.match(r, /padding-block: var\(--row-py\)/, `${sel}`)
    // Le padding horizontal ne bouge pas : la densité ne joue que sur la
    // hauteur de ligne.
    assert.match(r, /padding-inline: 14px/, `${sel}`)
    assert.doesNotMatch(r, /padding: \d+px \d+px/, `${sel} : padding figé restant`)
  }
})

test('le mobile reste au CONFORT quelle que soit la préférence', () => {
  // Sous le point de rupture, --row-py est réarmé à la valeur confortable.
  const i = css.indexOf('.data-table { --row-py: 0.625rem; }')
  assert.ok(i > 0, 'réarmement mobile absent')
  // …et ce réarmement vit bien DANS une media query mobile.
  const before = css.slice(0, i)
  const lastMedia = before.lastIndexOf('@media')
  assert.match(css.slice(lastMedia, lastMedia + 60), /max-width:\s*76[78]px/)
})

test('AUCUN nouveau système de densité : DataTable et densityOverride intacts', () => {
  const dt = readFileSync(
    path.join(__dirname, '..', 'ui', 'datatable', 'DataTable.jsx'), 'utf8')
  // La densité par vue (NTUX17) et la dérivation du moteur restent en place.
  assert.match(dt, /densityOverride/)
  assert.match(dt, /useDensity/)
  // Le moteur ne consomme PAS --row-py : les deux mécanismes restent séparés.
  assert.doesNotMatch(dt, /--row-py/)
})
