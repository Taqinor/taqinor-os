// WIR22 — badge « Contrôle d'intégrité » (Rapports.jsx, onglet Insights).
// Vérification de SOURCE (JSX, pas de node_modules installés dans ce lane —
// cf. rapports-attribution.test.mjs pour la même convention).
//   node --test src/pages/rapports-integrite.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'Rapports.jsx'), 'utf8')

test('charge via reportingApi.integriteInsight(), au même titre que les autres insights all-time', () => {
  assert.match(SRC, /load\('integrite', reportingApi\.integriteInsight\(\), setIntegrite\)/)
})

test('reloadCard sait recharger la carte integrite (bouton Réessayer de StateBlock)', () => {
  const reloadBody = SRC.slice(
    SRC.indexOf('const reloadCard ='), SRC.indexOf('const renderReportCard ='))
  assert.match(reloadBody, /key === 'integrite'/)
})

test("affiche un badge (danger si anomalies, success sinon), jamais de graphique", () => {
  const cardBody = SRC.slice(
    SRC.indexOf('Contrôle d\'intégrité"'), SRC.indexOf('</InsightCard>\n          </div>'))
  assert.match(cardBody, /integrite\.total_anomalies > 0 \? 'danger' : 'success'/)
  assert.match(cardBody, /Aucune anomalie/)
})

test('liste les familles en anomalie (label + nombre) quand total_anomalies > 0', () => {
  const cardBody = SRC.slice(
    SRC.indexOf('Contrôle d\'intégrité"'), SRC.indexOf('</InsightCard>\n          </div>'))
  assert.match(cardBody, /Object\.values\(integrite\.familles\)/)
  assert.match(cardBody, /\.filter\(\(f\) => f\.ids\.length > 0\)/)
})

test('aucun bouton export xlsx (l’endpoint ne supporte pas ?export=xlsx)', () => {
  const cardBody = SRC.slice(
    SRC.indexOf('Contrôle d\'intégrité"'), SRC.indexOf('</InsightCard>\n          </div>'))
  assert.doesNotMatch(cardBody, /onExport=/)
})
