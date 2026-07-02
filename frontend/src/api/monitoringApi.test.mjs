import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* WR6/WR7 — Verrouille le CONTRAT REST de la suite O&M monitoring : chaque
   méthode doit appeler l'URL RÉELLE du backend (apps/monitoring — actions du
   MonitoringConfigViewSet / ProductionWarrantyViewSet / CleaningEventViewSet).
   Toute dérive d'URL casse ce test (même approche que messagesApi.test.mjs :
   le module importe ./axios avec effets de bord, on vérifie donc la source). */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'monitoringApi.js'), 'utf8')

// ── WR6 — parc / analytique / garanties ─────────────────────────────────────

test('getFleet → GET /monitoring/configs/fleet/', () => {
  assert.match(src, /getFleet:[\s\S]*?api\.get\('\/monitoring\/configs\/fleet\/'/)
})

test('getOmMetrics → GET /monitoring/configs/<id>/om-metrics/', () => {
  assert.match(src, /getOmMetrics:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/om-metrics\/`/)
})

test('getHistory → GET /monitoring/configs/<id>/history/', () => {
  assert.match(src, /getHistory:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/history\/`/)
})

test('getWarranties → GET /monitoring/warranties/', () => {
  assert.match(src, /getWarranties:[\s\S]*?api\.get\('\/monitoring\/warranties\/'/)
})

test('saveWarranty → PATCH ou POST /monitoring/warranties/', () => {
  assert.match(src, /saveWarranty:[\s\S]*?api\.patch\(`\/monitoring\/warranties\/\$\{id\}\/`/)
  assert.match(src, /saveWarranty:[\s\S]*?api\.post\('\/monitoring\/warranties\/'/)
})

test('deleteWarranty → DELETE /monitoring/warranties/<id>/', () => {
  assert.match(src, /deleteWarranty:[\s\S]*?api\.delete\(`\/monitoring\/warranties\/\$\{id\}\/`/)
})

test('getWarrantyStatus → GET /monitoring/warranties/<id>/status/', () => {
  assert.match(src, /getWarrantyStatus:[\s\S]*?api\.get\(`\/monitoring\/warranties\/\$\{id\}\/status\/`/)
})

test('getWarrantyCurve → GET /monitoring/warranties/<id>/curve/', () => {
  assert.match(src, /getWarrantyCurve:[\s\S]*?api\.get\(`\/monitoring\/warranties\/\$\{id\}\/curve\/`/)
})
