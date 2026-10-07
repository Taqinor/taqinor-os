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

// AANA29 (C-AANA-022) — le taux affiché sous « Tunnel de conversion » est le
// taux SERVI par le backend (contrat PACT10 AANA1 :
// backend/django_core/apps/reporting/contract_samples/dashboard.json), jamais
// la formule écran nb_factures ÷ nb_devis qui donnait 150 % sur
// {nb_devis: 10, nb_acceptes: 3, nb_factures: 15}.
test('taux_acceptation_servi', async () => {
  const contrat = JSON.parse(readFileSync(join(
    here, '..', '..', '..', 'backend', 'django_core', 'apps', 'reporting',
    'contract_samples', 'dashboard.json'), 'utf8'))
  const conversion = contrat.exemple.conversion
  assert.ok('taux_acceptation_pct' in conversion,
    'le contrat AANA1 doit porter conversion.taux_acceptation_pct')

  // L'écran lit la clé servie, sous le libellé attendu…
  assert.ok(reporting.includes('formatPercent(conversion.taux_acceptation_pct)'),
    'Reporting.jsx doit afficher conversion.taux_acceptation_pct tel quel')
  assert.ok(reporting.includes('Devis acceptés / créés'))
  // …et ne recalcule plus aucun taux à partir des compteurs.
  assert.ok(!/nb_factures\s*\/\s*conversion\.nb_devis/.test(reporting),
    'la formule nb_factures ÷ nb_devis (> 100 %) doit avoir disparu')
  assert.ok(!/nb_acceptes\s*\/\s*conversion\.nb_devis/.test(reporting),
    "le taux ne doit pas être recalculé à l'écran")

  // Rendu de la valeur servie : « 30 % », jamais « 150 % ».
  const { formatPercent } = await import('../lib/format.js')
  const servi = { nb_devis: 10, nb_acceptes: 3, nb_factures: 15, taux_acceptation_pct: 30 }
  const affiche = formatPercent(servi.taux_acceptation_pct)
  assert.match(affiche, /^30\s%$/)
  assert.ok(!formatPercent(servi.taux_acceptation_pct).includes('150'))
})
