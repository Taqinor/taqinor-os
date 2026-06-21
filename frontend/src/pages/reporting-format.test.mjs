// K149 — Formatage des nombres (reporting/dashboard).
// Garde-fou au niveau source : Reporting.jsx et Dashboard.jsx routent leurs
// montants/%/dates par les utilitaires F19 (lib/format) et n'affichent plus de
// figures brutes non formatées. (Pas de rendu DOM : on lit la source, comme les
// autres tests .mjs du dépôt.)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const reporting = readFileSync(join(here, 'Reporting.jsx'), 'utf8')
const dashboard = readFileSync(join(here, 'Dashboard.jsx'), 'utf8')

test('Reporting.jsx importe les utilitaires F19 (formatMAD/formatNumber/formatPercent)', () => {
  assert.match(reporting, /from '\.\.\/lib\/format'/)
  for (const fn of ['formatMAD', 'formatNumber', 'formatPercent']) {
    assert.ok(reporting.includes(fn), `Reporting.jsx doit utiliser ${fn}`)
  }
})

test('Reporting.jsx : notation compacte fr-MA pour les tuiles KPI', () => {
  // dhCompact utilise Intl fr-MA en notation compacte.
  assert.match(reporting, /notation:\s*'compact'/)
  assert.match(reporting, /'fr-MA'/)
  // Les KPI monétaires passent par dhCompact.
  assert.ok(reporting.includes('dhCompact(kpis.ca_paye)'))
  assert.ok(reporting.includes('dhCompact(kpis.valeur_stock)'))
})

test('Reporting.jsx : plus de pourcentage brut « }%` » hors formatPercent', () => {
  // Les pourcentages d'affichage passent par formatPercent (pas de `}%` collé).
  assert.ok(
    !/\}\s*%\s*</.test(reporting) && !/\)\s*\+\s*'%'/.test(reporting),
    'un pourcentage semble encore concaténé à la main dans Reporting.jsx',
  )
})

test('Dashboard.jsx route ses figures par F19 (formatMAD/formatNumber/formatPercent/formatDate)', () => {
  assert.match(dashboard, /from '\.\.\/lib\/format'/)
  for (const fn of ['formatMAD', 'formatNumber', 'formatPercent', 'formatDate']) {
    assert.ok(dashboard.includes(fn), `Dashboard.jsx doit utiliser ${fn}`)
  }
})

test('Reporting.jsx & Dashboard.jsx : alignement des chiffres avec tabular-nums', () => {
  assert.ok(reporting.includes('tabular-nums'))
  assert.ok(dashboard.includes('tabular-nums'))
})
