// Preuve en direct d'ADRG77 (C-ADRG-026, PLAN_AUDIT_TRANSVERSE.md, D-ADRG-4 = suit_la_case) : le bouton « Exporter »
// (CSV navigateur de `frontend/src/ui/datatable/DataTable.jsx`, prop `codeExport`) des tableaux stock suit la case
// « Exporter » du module. Clause : Stock → Mouvements rejoué avec un Commercial responsable (sans `stock_export`) ⇒
// aucun « Exporter » sur les trois tableaux de `MouvementsPage.jsx` (liste, vue groupée, Transferts) ; un Directeur
// (avec `stock_export`) ⇒ « Exporter » sur les trois. Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus
// par leur nom dans la société démo, droits relus en base), connectés par /token/ (même geste qu'adrg6.spec.js).
// Persistance : n/a (rendu) — l'écran est relu après rechargement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, connexionApi } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG77'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = (x) => JSON.stringify(x)
const SOC = `U.objects.get(username='demo_admin').company_id`
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })

/** Compte d'essai du rôle SYSTÈME `nomRole` ; renvoie les codes du rôle (relus en base). */
const compteDuRole = (nom, nomRole) => py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie(sorted(r.permissions or []))`)

/** Écran sous le compte `nom` : contexte neuf (SW bloqué), session par /token/, visites guidées vues. */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const p = suivi.surveiller(await ctx.newPage())
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return p
}

etape('PF4.1-ADRG77-mouvements', ['ADRG77'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const cr = { qui: 'Commercial responsable', nom: `adrg77cr_${m}`, present: false }
  const di = { qui: 'Directeur', nom: `adrg77di_${m}`, present: true }
  for (const x of [cr, di]) x.codes = await compteDuRole(x.nom, x.qui)
  console.log(`[ADRG77] codes stock — CR : ${J(cr.codes.filter((c) => c.startsWith('stock_')))} ; Directeur : ${J(di.codes.filter((c) => c.startsWith('stock_')))}`)
  expect([cr.codes.includes('stock_voir'), cr.codes.includes('stock_export')], 'Given : Commercial responsable voit le stock, SANS « Exporter »').toEqual([true, false])
  expect([di.codes.includes('stock_voir'), di.codes.includes('stock_export')], 'Given : Directeur voit le stock, AVEC « Exporter »').toEqual([true, true])

  const TABLES = [
    ['liste', 'Mouvements de stock'],
    ['vue groupée', 'Mouvements de stock — vue groupée (pivot)'],
    ['Transferts', 'Transferts entre emplacements'],
  ]
  for (const x of [cr, di]) {
    const p = await ecran(page, suivi, testInfo, x.nom)
    const csv = p.getByRole('button', { name: 'Exporter', exact: true })
    const verifier = async (passe, [vue, label]) => {
      await expect(p.locator(`[aria-label="${label}"]`).first(), `${passe} ${vue} : tableau affiché`).toBeVisible({ timeout: 60_000 })
      await p.waitForLoadState('networkidle').catch(() => undefined)
      if (x.present) await expect(csv.first(), `${passe} ${vue} : « Exporter » offert`).toBeVisible()
      else await expect(csv, `${passe} ${vue} : aucun « Exporter »`).toHaveCount(0)
    }
    for (const recharger of [false, true]) {
      const passe = `${x.qui}${recharger ? ' (rechargé)' : ''}`
      await p.goto('/stock/mouvements')
      if (recharger) await p.reload()
      await verifier(passe, TABLES[0])
      await p.getByRole('button', { name: /Vue groupée/ }).click()
      await verifier(passe, TABLES[1])
      await p.getByRole('button', { name: /Vue liste/ }).click()
      await p.getByRole('radio', { name: /Transferts/ }).click()
      await verifier(passe, TABLES[2])
    }
    if (x === cr) await p.goto('/stock/mouvements')
  }
})
