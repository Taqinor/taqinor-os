// Preuves en direct du groupe ADRG, lot 8 (défauts relevés aux rejeux du 14-15/11, enregistrement
// `docs/audits/acceptation/ADRG/2026-11-14-df74c8d81.md`) : ADRG138 (/rapports : attribution et insights chargés
// seulement avec les droits de leurs routes), ADRG139 (/interventions et son entrée de menu gardées par
// `installation_voir`), ADRG141 (accueil /apps : badges `kpi-federes?vue=badges` demandés seulement au palier
// responsable/admin). Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société
// démo — jamais un rôle fabriqué), connectés PAR L'ÉCRAN DE CONNEXION (c'est l'objet même d'ADRG141 : la connexion
// atterrit sur /apps) ; chaque réponse de l'API est relevée (« onglet réseau »). Rendu seul : rien n'est écrit par les
// rôles. Persistance : n/a (lecture) — chaque écran est relu après rechargement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG138', 'ADRG139', 'ADRG141'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const OUVERTS = []
test.afterEach(async () => { for (const c of OUVERTS.splice(0)) await c.close().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const J = JSON.stringify
const comptes = []
test.afterAll(async () => {
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` ; renvoie {username, codes} (codes du rôle relus en base). */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const codes = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
compte(${J(username)}, role=r.pk, societe=${SOC})
sortie(sorted(r.permissions or []))`)
  comptes.push(username)
  return { username, codes, nomRole }
}

/** Onglet NEUF (aucun cookie de demo_admin) : réseau relevé DÈS l'ouverture, connexion par l'ÉCRAN de connexion
 *  (atterrissage /apps), visites guidées marquées vues. `reseau` reçoit « MÉTHODE chemin → statut ». */
async function ecranDe(page, suivi, testInfo, c) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  OUVERTS.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  const p = suivi.surveiller(await ctx.newPage())
  const reseau = []
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  await uiLoginJusquAuxApps(p, { username: c.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  return { ctx, p, reseau }
}
const chemin = (l) => l.split(' ')[1].split('?')[0]
/** Lignes de `reseau` dont le chemin (sans requête) correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
/** Réponses refusées (4xx/5xx) relevées. */
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)

// ── ADRG138 — /rapports : attribution (crm), revenu récurrent (sav), analytics (ventes) sous le droit de leur route ──
etape('PF4.4-ADRG138', ['ADRG138'], async ({ page, suivi, testInfo }) => {
  const LECTURES = [
    ['attribution', /^\/crm\/rapports\/attribution\/$/, 'Ventes & pipeline', 'Attribution des leads'],
    ['revenu récurrent', /^\/reporting\/insights\/recurring-revenue\/$/, 'Insights', 'Revenu récurrent (contrats de maintenance)'],
    ['analytics', /^\/reporting\/insights\/analytics\/$/, 'Insights', 'Analytics (délais & kWc installés)'],
  ]
  for (const [nomRole, prefixe] of [['Technicien responsable', 'adrg138tr'], ['Admin RH', 'adrg138rh'], ['Directeur', 'adrg138di']]) {
    const c = await compteDe(nomRole, prefixe)
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of ['', 'relu après rechargement : ']) {
      s.reseau.length = 0
      const attendues = nomRole === 'Directeur'
        ? LECTURES.map(([, re]) => s.p.waitForResponse((r) => re.test(new URL(r.url()).pathname.slice(API.length)) && r.request().method() === 'GET', T))
        : []
      if (passe) await s.p.reload(); else await s.p.goto('/rapports')
      for (const r of await Promise.all(attendues)) expect(r.status(), `${passe}Directeur : ${new URL(r.url()).pathname}`).toBe(200)
      await expect(s.p.getByRole('tab', { name: 'Insights', exact: true }), `${passe}${nomRole} : onglets des rapports`).toBeVisible(V)
      await calme(s.p)
      console.log(`[ADRG138] ${passe}${nomRole} : ${J(s.reseau)}`)
      expect(refus(s.reseau), `${passe}${nomRole} : aucune réponse refusée sur /rapports`).toEqual([])
      for (const [quoi, re, onglet, titre] of LECTURES) {
        const vus = appels(s.reseau, re)
        if (nomRole === 'Directeur') expect(vus.length, `${passe}Directeur : ${quoi} lu`).toBeGreaterThanOrEqual(1)
        await s.p.getByRole('tab', { name: onglet, exact: true }).click()
        const carte = s.p.getByRole('tabpanel').getByText(titre, { exact: true })
        if (vus.length) {
          expect(vus.every((l) => l.endsWith('→ 200')), `${passe}${nomRole} : ${quoi} ${J(vus)}`).toBe(true)
          await expect(carte.first(), `${passe}${nomRole} : carte « ${titre} » rendue (chargée)`).toBeVisible(V)
        } else {
          await expect(carte, `${passe}${nomRole} : ni lecture ni carte « ${titre} »`).toHaveCount(0)
        }
      }
      await expect(s.p.getByText('Rapport indisponible'), `${passe}${nomRole} : aucune carte en erreur`).toHaveCount(0)
    }
  }
})

// ── ADRG139 — /interventions : entrée de menu et route sous `installation_voir` ──────────────────────────────
const LISTE_INTERVENTIONS = /^\/installations\/interventions\/$/
etape('PF4.4-ADRG139', ['ADRG139'], async ({ page, suivi, testInfo }) => {
  // Commercial responsable (aucun code chantiers) : ni entrée de menu, ni appel, ni écran d'échec.
  const cr = await compteDe('Commercial responsable', 'adrg139cr')
  expect(cr.codes.includes('installation_voir'), `Given : Commercial responsable sans installation_voir ${J(cr.codes.filter((x) => x.startsWith('installation')))}`).toBe(false)
  const s = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of ['', 'relu après rechargement : ']) {
    // Menu de l'app Chantiers (barre latérale de l'app, ouverte sur son écran d'accueil /chantiers).
    if (passe) await s.p.reload(); else await s.p.goto('/chantiers')
    const nav = s.p.getByRole('navigation', { name: /^Navigation / })
    await expect(nav.getByRole('link', { name: 'Chantiers', exact: true }), `${passe}Commercial responsable : menu de l'app Chantiers rendu`).toBeVisible(V)
    await calme(s.p)
    await expect(nav.getByRole('link', { name: 'Interventions', exact: true }), `${passe}Commercial responsable : aucune entrée « Interventions »`).toHaveCount(0)
    await expect(s.p.locator('a[href="/interventions"]'), `${passe}Commercial responsable : aucun lien /interventions`).toHaveCount(0)
  }
  for (const passe of ['', 'relu après rechargement : ']) {
    s.reseau.length = 0
    if (passe) await s.p.reload(); else await s.p.goto('/interventions')
    await calme(s.p)
    console.log(`[ADRG139] ${passe}Commercial responsable /interventions → ${s.p.url()} : ${J(s.reseau)}`)
    expect(appels(s.reseau, LISTE_INTERVENTIONS), `${passe}Commercial responsable : aucun GET installations/interventions/`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial responsable : aucune réponse refusée`).toEqual([])
    await expect(s.p.getByText('Impossible de charger les interventions'), `${passe}Commercial responsable : pas d'écran d'échec`).toHaveCount(0)
  }
  // Témoin : Technicien responsable (installation_voir) — l'entrée de menu et la liste.
  const tr = await compteDe('Technicien responsable', 'adrg139tr')
  expect(tr.codes.includes('installation_voir'), 'Given : Technicien responsable avec installation_voir').toBe(true)
  const t = await ecranDe(page, suivi, testInfo, tr)
  for (const passe of ['', 'relu après rechargement : ']) {
    t.reseau.length = 0
    const liste = t.p.waitForResponse((r) => LISTE_INTERVENTIONS.test(new URL(r.url()).pathname.slice(API.length)) && r.request().method() === 'GET', T)
    if (passe) await t.p.reload(); else await t.p.goto('/interventions')
    expect((await liste).status(), `${passe}Technicien responsable : liste des interventions servie`).toBe(200)
    await calme(t.p)
    const nav = t.p.getByRole('navigation', { name: /^Navigation / })
    await expect(nav.getByRole('link', { name: 'Interventions', exact: true }), `${passe}Technicien responsable : entrée « Interventions »`).toBeVisible(V)
    await expect(t.p.getByText('Impossible de charger les interventions'), `${passe}Technicien responsable : liste rendue`).toHaveCount(0)
    expect(refus(t.reseau), `${passe}Technicien responsable : aucune réponse refusée`).toEqual([])
  }
})

// ── ADRG141 — accueil /apps : badges `kpi-federes?vue=badges` seulement au palier responsable/admin ───────────
const BADGES = /^\/reporting\/reports\/kpi-federes\/$/
etape('PF4.1-ADRG141', ['ADRG141'], async ({ page, suivi, testInfo }) => {
  // Viewer connecté par l'écran de connexion : il atterrit sur /apps — aucun appel badges, aucun refus.
  const vi = await compteDe('Viewer', 'adrg141vi')
  const s = await ecranDe(page, suivi, testInfo, vi)
  for (const passe of ['', 'relu après rechargement : ']) {
    if (passe) { s.reseau.length = 0; await s.p.reload() }
    await expect(s.p, `${passe}Viewer : accueil /apps`).toHaveURL(/\/apps/)
    await expect(s.p.getByRole('link').first(), `${passe}Viewer : tuiles de l'accueil rendues`).toBeVisible(V)
    await calme(s.p)
    console.log(`[ADRG141] ${passe}Viewer : ${J(s.reseau)}`)
    expect(appels(s.reseau, BADGES), `${passe}Viewer : aucun GET kpi-federes?vue=badges`).toEqual([])
    expect(refus(s.reseau), `${passe}Viewer : aucune réponse refusée (connexion + accueil)`).toEqual([])
  }
  // Témoin Directeur (même chemin de connexion) : badges lus (200).
  const di = await compteDe('Directeur', 'adrg141di')
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of ['', 'relu après rechargement : ']) {
    if (passe) { d.reseau.length = 0; await d.p.reload() }
    await expect(d.p, `${passe}Directeur : accueil /apps`).toHaveURL(/\/apps/)
    await expect.poll(() => appels(d.reseau, BADGES).length, { message: `${passe}Directeur : badges demandés`, timeout: 60_000 }).toBeGreaterThanOrEqual(1)
    const vus = appels(d.reseau, BADGES)
    expect(vus.every((l) => /vue=badges/.test(l) && l.endsWith('→ 200')), `${passe}Directeur : badges lus ${J(vus)}`).toBe(true)
    await calme(d.p)
    expect(refus(d.reseau), `${passe}Directeur : aucune réponse refusée`).toEqual([])
  }
})
