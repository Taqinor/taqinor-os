// AANA — spec d'acceptation en direct : CA facture sur le total rempli (AANA77), rôle lecture seule de l'agent SQL (AANA64),
// probabilités servies au Kanban / Pipeline / Prévisions (AANA67), étapes (1), (3), (4),
// (6) de la contre-visite (AANA74). AANA60 n'est pas construite (BLOCKED au plan) : pas d'étape. Hors périmètre de cette spec, dit à l'orchestrateur : pile neuve (`down -v`, interdit
// sur une pile partagée), volet agent SQL d'AANA77 (bloqué au plan), LLM (aucune clé) : les requêtes passent par le moteur réel.
import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AANA', ['AANA77', 'AANA64', 'AANA67'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const chiffres = (t) => Number(String(t).replace(/[^\d]/g, ''))

/** Exécute une requête par le moteur RÉEL de l'agent SQL (app.core.database.create_sql_agent_engine), jamais de LLM. */
function requeteAgent(sql) {
  const code = `
import json
from sqlalchemy import text
from app.core import database as d
with d.create_sql_agent_engine().connect() as c:
    print('@@' + json.dumps([list(r) for r in c.execute(text(${JSON.stringify(sql)}))], default=str))`
  const sortie = execFileSync('docker', ['compose', 'exec', '-T', 'fastapi_ia', 'python', '-c', code], { encoding: 'utf8', maxBuffer: 5_000_000 })
  return JSON.parse(sortie.split('\n').find((l) => l.startsWith('@@')).slice(2))
}

// ── AANA77 — ca_ht = somme des total_ht des factures émises / payées / en retard ─────────────────────
etape('P5.metrique_ca', ['AANA77'], async ({ page, suivi }) => {
  const c = await py(`from decimal import Decimal
from django.core.management import call_command
from apps.semantic import services as s
call_command('seed_metriques', verbosity=0)
from apps.ventes.models import Facture
from authentication.models import Company
co = Company.objects.get(pk=1)
v = s.resolve_metric_valeur(co, None, 'ca_ht')
L = [f for f in Facture.objects.filter(company=co, statut__in=['emise', 'payee', 'en_retard'])]
sortie({'metrique': float(v or 0), 'somme': float(sum((f.total_ht for f in L), Decimal('0'))), 'n': len(L)})`)
  expect(c.n, 'la société a des factures').toBeGreaterThan(0)
  expect(c.metrique, `ca_ht = Σ total_ht sur ${c.n} factures`).toBeCloseTo(c.somme, 0)
  await page.goto('/reporting')
  await expect(page.locator('body')).toContainText(/Reporting|Rapports|Tableau/, { timeout: 60_000 })
  suivi.verifie(5)
})

// ── AANA64 / AANA74(1) — l'agent tourne sous sql_agent_ro : f,f ; le provisionnement rejoué ne change rien ─
etape('P5.1', ['AANA64'], async ({ page, suivi }) => {
  const role = requeteAgent('select rolname, rolsuper, rolbypassrls, current_user from pg_roles where rolname = current_user')
  expect(role, 'une ligne').toHaveLength(1)
  expect(role[0], 'sql_agent_ro, ni superuser ni bypassrls').toEqual(['sql_agent_ro', false, false, 'sql_agent_ro'])
  const droits = () => requeteAgent("select table_name, privilege_type from information_schema.role_table_grants where grantee = current_user order by 1, 2")
  const avant = droits()
  expect(avant.length, 'une liste blanche, pas zéro').toBeGreaterThan(0)
  expect(avant.every((d) => d[1] === 'SELECT'), 'lecture seule').toBe(true)
  execFileSync('bash', ['backend/db/provision_sql_agent_ro.sh'], { cwd: new URL('../../../', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'), encoding: 'utf8', maxBuffer: 5_000_000 })
  expect(droits(), 'second passage : identique').toEqual(avant)
  await page.goto('/dashboard')
  await expect(page.getByTestId('mes-chiffres-card')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── AANA67 / AANA74(6) — Kanban, Pipeline et Prévisions lisent la probabilité SERVIE ─────────────────
etape('P5.kanban', ['AANA67'], async ({ page, suivi }) => {
  const m = marque()
  await page.setViewportSize({ width: 1700, height: 1000 })
  const r = page.request
  const proba = (await lireJson(await r.get(`${API}/reporting/probabilites-etape/`, T), 'probabilités')).probabilites
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AANA67 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const produit = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur AANA67 ${m}`, prix_vente: '83333.33', prix_achat: '111.00' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: produit.id, designation: produit.nom, quantite: '1', prix_unitaire: '83333.33', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] },
  }), 'devis ~100 000 TTC')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await r.get(`${API}/crm/leads/${lead.id}/`, T), 'lead relu')
  expect(relu.stage, 'étape devis envoyé').toBe('QUOTE_SENT')
  const ttc = Number((await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')).total_ttc)
  const attendu = Math.round(ttc * proba.QUOTE_SENT)
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(`AANA67 ${m}`)}`)
  const colonne = page.getByLabel(/^Étape Devis envoyé/)
  await expect(colonne).toHaveAttribute('aria-label', /1 lead$/, { timeout: 60_000 })
  const argent = colonne.locator('.kb-col-money')
  await expect(argent, 'kanban : Prév. = proba × TTC').toContainText('Prév.', { timeout: 30_000 })
  expect(chiffres((await argent.innerText()).split('Prév.')[1]), 'kanban').toBeCloseTo(attendu, -1)
  await expect(argent).toHaveAttribute('title', new RegExp(`Prévisionnel pondéré à ${Math.round(proba.QUOTE_SENT * 100)} %`))
  const total = page.locator('.lp-pipeline-total:visible').first()
  await expect(total).toBeVisible()
  const titre = await total.getAttribute('title')
  expect(chiffres(titre.split('Prévisionnel pondéré :')[1].split('(')[0]), 'Pipeline').toBeCloseTo(attendu, -1)
  await page.goto(`/crm/leads?view=prevision&q=${encodeURIComponent(`AANA67 ${m}`)}`)
  // La colonne du mois se peint après le chargement des leads : on attend sa valeur, jamais une lecture immédiate.
  await expect.poll(async () => Math.max(0, ...(await page.locator('.kb-col-forecast:visible').allInnerTexts()).map(chiffres)),
    { timeout: 60_000, intervals: [1_000, 2_000], message: 'Prévisions : Prév. = proba × TTC' }).toBeGreaterThan(attendu - 5)
  expect(Math.max(...(await page.locator('.kb-col-forecast:visible').allInnerTexts()).map(chiffres)), 'Prévisions').toBeLessThan(attendu + 5)
  void listeDe
  suivi.verifie(5)
})
