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

// ── WR7 — portail client / CO₂ / nettoyages / rapports ──────────────────────

test('getClientPortal → GET /monitoring/configs/client-portal/?client=', () => {
  assert.match(src, /getClientPortal:[\s\S]*?api\.get\('\/monitoring\/configs\/client-portal\/'/)
  assert.match(src, /getClientPortal:[\s\S]*?client: clientId/)
})

test('getCo2 → GET /monitoring/configs/<id>/co2/', () => {
  assert.match(src, /getCo2:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/co2\/`/)
})

test('getCo2Fleet → GET /monitoring/configs/co2-fleet/', () => {
  assert.match(src, /getCo2Fleet:[\s\S]*?api\.get\('\/monitoring\/configs\/co2-fleet\/'/)
})

test('getCleanings → GET /monitoring/cleanings/', () => {
  assert.match(src, /getCleanings:[\s\S]*?api\.get\('\/monitoring\/cleanings\/'/)
})

test('addCleaning → POST /monitoring/cleanings/', () => {
  assert.match(src, /addCleaning:[\s\S]*?api\.post\('\/monitoring\/cleanings\/'/)
})

test('deleteCleaning → DELETE /monitoring/cleanings/<id>/', () => {
  assert.match(src, /deleteCleaning:[\s\S]*?api\.delete\(`\/monitoring\/cleanings\/\$\{id\}\/`/)
})

test('getSoiling → GET /monitoring/configs/<id>/soiling/', () => {
  assert.match(src, /getSoiling:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/soiling\/`/)
})

test('getOmReport → GET /monitoring/configs/<id>/om-report/', () => {
  assert.match(src, /getOmReport:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/om-report\/`/)
})

test('getOmReportPdf → GET /om-report/ avec format=pdf + blob', () => {
  assert.match(src, /getOmReportPdf:[\s\S]*?api\.get\(`\/monitoring\/configs\/\$\{configId\}\/om-report\/`/)
  assert.match(src, /getOmReportPdf:[\s\S]*?format: 'pdf'/)
  assert.match(src, /getOmReportPdf:[\s\S]*?responseType: 'blob'/)
})

test('emailOmReport → POST /monitoring/configs/<id>/email-om-report/', () => {
  assert.match(src, /emailOmReport:[\s\S]*?api\.post\(`\/monitoring\/configs\/\$\{configId\}\/email-om-report\/`/)
})
