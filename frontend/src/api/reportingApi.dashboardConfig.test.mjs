import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* WR8 — Verrouille le contrat REST de la config de tableau de bord (FG96) :
   les méthodes doivent viser les vraies URL du backend
   (apps/reporting DashboardConfigViewSet + action effective/). */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'reportingApi.js'), 'utf8')

test('listDashboardConfigs → GET /reporting/dashboard-config/', () => {
  assert.match(src, /listDashboardConfigs:[\s\S]*?api\.get\('\/reporting\/dashboard-config\/'/)
})

test('effectiveDashboardConfig → GET /reporting/dashboard-config/effective/', () => {
  assert.match(src, /effectiveDashboardConfig:[\s\S]*?api\.get\('\/reporting\/dashboard-config\/effective\/'/)
})

test('saveDashboardConfig → PATCH ou POST /reporting/dashboard-config/', () => {
  assert.match(src, /saveDashboardConfig:[\s\S]*?api\.patch\(`\/reporting\/dashboard-config\/\$\{id\}\/`/)
  assert.match(src, /saveDashboardConfig:[\s\S]*?api\.post\('\/reporting\/dashboard-config\/'/)
})

test('deleteDashboardConfig → DELETE /reporting/dashboard-config/<id>/', () => {
  assert.match(src, /deleteDashboardConfig:[\s\S]*?api\.delete\(`\/reporting\/dashboard-config\/\$\{id\}\/`/)
})

test('cohorts (FG98) → GET /reporting/insights/cohorts/', () => {
  assert.match(src, /cohorts:[\s\S]*?api\.get\('\/reporting\/insights\/cohorts\/'/)
})

test('integriteInsight (WIR22, carte ALL_DASHBOARD_CARDS "integrite") → GET /reporting/insights/integrite/', () => {
  assert.match(src, /integriteInsight:[\s\S]*?api\.get\('\/reporting\/insights\/integrite\/'/)
})
