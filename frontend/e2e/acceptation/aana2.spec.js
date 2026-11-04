// AANA74 (rejeu partiel du 04/11) — sondes de contre-visite C-AANA-VER-001 à 005 au sha, rôle `sql_agent_ro` réel,
// validateur de l'agent SQL (route LLM non jouée : refus et rôle seulement), un seul taux d'acceptation /reporting = Quote-to-cash.
// Étapes (2), (3), (5), (7) : preuves du 01/11 (`AANA/2026-11-01-15ebadca5`), non rejouées ici.
import { spawnSync, execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { lireJson, assurerSessionPage } from '../helpers.js'

const etape = groupe('AANA', ['AANA74', 'AANA57', 'AANA58'])
const API = '/api/django'
const T = { timeout: 120_000 }
const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

etape('S.sondes_ver', ['AANA74'], async () => {
  for (const n of ['001', '002', '003', '004']) {
    const s = spawnSync('python', ['scripts/sonde.py', `AANA/C-AANA-VER-${n}`], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
    expect(s.stdout, `sonde ${n} ${s.stderr?.slice(-300)}`).toMatch(/"repro":\s*false/)
  }
  // 005 : fonction pure du validateur, dans l'image de l'agent (sqlglot n'est que là).
  const code = `${readFileSync(join(RACINE, 'docs/audits/sondes/AANA/C-AANA-VER-005.py'), 'utf8')}\n`
  const r = spawnSync('docker', ['exec', '-i', 'erp-agentique-fastapi_ia-1', 'python', '-'], { input: code, encoding: 'utf8', maxBuffer: 10_000_000 })
  expect(r.stdout, r.stderr?.slice(-300)).toContain('NON REPRODUIT')
})

etape('P1.role_et_refus', ['AANA74'], async () => {
  const roles = execFileSync('docker', ['exec', 'erp-agentique-db-1', 'sh', '-c',
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select rolsuper,rolbypassrls from pg_roles where rolname=\'sql_agent_ro\'"'], { encoding: 'utf8' }).trim()
  expect(roles, 'sql_agent_ro : f,f').toBe('f|f')
  const prog = `from app.services import sql_agent_service as s
for q in ('SELECT * FROM pg_stats', 'SELECT * FROM pg_roles', 'WITH "CRM_LEAD" AS (SELECT 1 AS id) SELECT * FROM crm_lead'):
    try:
        s._validate_and_secure(q, 1); print('ACCEPTE', q)
    except s.SQLSecurityError:
        print('REFUS', q)
`
  const r = spawnSync('docker', ['exec', '-i', 'erp-agentique-fastapi_ia-1', 'python', '-'], { input: prog, encoding: 'utf8' })
  expect(r.stdout, r.stderr?.slice(-300)).not.toContain('ACCEPTE')
  expect((r.stdout.match(/REFUS/g) || []).length, 'trois refus').toBe(3)
})

etape('P4.un_seul_taux', ['AANA57', 'AANA58', 'AANA74'], async ({ page, suivi }) => {
  const r = page.request
  const debut = '2026-10-01'
  const fin = '2026-10-31'
  const rep = await lireJson(await r.get(`${API}/reporting/dashboard/?from=${debut}&to=${fin}`, T), 'reporting')
  const q2c = await lireJson(await r.get(`${API}/ventes/dashboard/?start=${debut}&end=${fin}`, T), 'quote-to-cash')
  expect(rep.conversion.taux_acceptation_pct, `même taux ${JSON.stringify(rep.conversion).slice(0, 200)}`).toBe(q2c.devis.taux_acceptation_pct)
  expect(rep.conversion).toHaveProperty('nb_envoyes_periode')
  expect(rep.conversion).toHaveProperty('nb_acceptes_periode')
  await page.goto('/reporting')
  await expect(page.getByText(/Tunnel de conversion/i).first()).toBeVisible({ timeout: 60_000 })
  // Aucune barre du tunnel au-delà de 100 %, aucun pourcentage recalculé affiché dedans.
  const largeurs = await page.locator('section, div').filter({ hasText: /^Tunnel de conversion/ }).first().locator('[style*="width"]').evaluateAll((els) => els.map((e) => parseFloat(e.style.width)).filter((x) => !Number.isNaN(x)))
  for (const l of largeurs) expect(l, 'largeur bornée').toBeLessThanOrEqual(100)
  suivi.verifie(8)
})
