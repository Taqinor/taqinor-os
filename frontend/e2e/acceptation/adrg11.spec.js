// Preuves en direct du groupe ADRG, lot 11 (vague d'acceptation 6, runner GitHub) : rapports, tableau de bord,
// accueil, onboarding, paramètres et appels « assignables » — ADRG71, 73, 110, 111, 112, 113, 118, 119, 120.
// Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo — jamais un
// rôle fabriqué), connectés par la vraie route `/token/` dans un navigateur à part ; chaque réponse de l'API est
// relevée (« onglet réseau ») : une clause « aucune requête 403 » est affirmée sur ce relevé, en plus des oracles.
// Données propres créées par l'API de demo_admin ou le shell Django, retirées en fin d'étape ; chaque écran est relu
// après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG71', 'ADRG73', 'ADRG110', 'ADRG111', 'ADRG112', 'ADRG113', 'ADRG118', 'ADRG119', 'ADRG120'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 540_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const OUVERTS = []
test.afterEach(async () => { for (const fermer of OUVERTS.splice(0)) await fermer().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
const comptes = []
test.afterAll(async () => {
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` ; {username, id, nomRole, codes} (codes du rôle relus en base). */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const x = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(username)}, role=r.pk, societe=${SOC})
sortie(dict(id=u.id, codes=sorted(r.permissions or [])))`)
  comptes.push(username)
  return { username, id: x.id, codes: x.codes, nomRole }
}

/** Contexte API (vraie route /token/) d'un compte. */
async function apiDe(testInfo, c) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  OUVERTS.push(() => ctx.dispose())
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return ctx
}

/** Navigateur à part (aucun cookie de demo_admin) connecté par /token/ ; visites guidées marquées vues ; chaque
 *  réponse de l'API relevée dans `reseau` (« MÉTHODE chemin?requête → statut »). La page demo_admin de l'étape est
 *  refermée : la capture montre l'écran du rôle joué. */
async function ecranDe(page, suivi, testInfo, c, stockage = {}) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  OUVERTS.push(() => ctx.close())
  await ctx.addInitScript((extra) => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      for (const [k, v] of Object.entries(extra)) localStorage.setItem(k, v)
    } catch { /* mode privé */ }
  }, stockage)
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  const reseau = []
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  return { ctx, p, reseau, api: ctx.request, c }
}
const chemin = (l) => l.split(' ')[1].split('?')[0]
/** Lignes de `reseau` dont le chemin (sans requête) correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
/** Réponses refusées (4xx/5xx) relevées. */
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
/** Attend une réponse GET dont le chemin (relatif à l'API) correspond à `re`. */
const reponse = (p, re) => p.waitForResponse((r) => re.test(new URL(r.url()).pathname.slice(API.length)) && r.request().method() === 'GET', T)
/** Ouvre `url` (ou recharge) en vidant le relevé ; attend le calme. */
async function charger(s, url, passe) {
  s.reseau.length = 0
  if (passe) await s.p.reload(); else await s.p.goto(url)
  await calme(s.p)
}
const PASSES = ['', 'relu après rechargement : ']

/** 403 qui NOMME le code manquant (`droit_manquant`). */
async function refusNomme(res, code, quoi) {
  const corps = await res.text()
  expect(res.status(), `${quoi} : ${corps.slice(0, 240)}`).toBe(403)
  expect(corps, `${quoi} : le refus nomme ${code}`).toContain(code)
  expect(corps, `${quoi} : code droit_manquant`).toContain('droit_manquant')
}

// ── PF4.3 — ADRG71 : rapports chantiers / SAV / stock sous la lecture du module source ; /rapports du Commercial ──
const SERVICE = /^\/reporting\/reports\/service\/$/
etape('PF4.3-ADRG71', ['ADRG71'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const chantier = await py(`from apps.installations.models import Installation
sortie(Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG71-${m}').pk)`)
  const CHANTIERS = ['reporting/reports/service/', 'reporting/reports/field/', 'reporting/insights/technicien-scorecard/',
    'reporting/reports/chantier/', `reporting/archive/chantier/${chantier}/`]
  const AUTRES = ['reporting/insights/sav-sla/', 'reporting/insights/recurring-revenue/', 'reporting/reports/stock/']
  try {
    const co = await compteDe('Commercial', 'adrg71co')
    const rh = await compteDe('Admin RH', 'adrg71rh')
    const tr = await compteDe('Technicien responsable', 'adrg71tr')
    const [aco, arh, atr] = [await apiDe(testInfo, co), await apiDe(testInfo, rh), await apiDe(testInfo, tr)]
    // La fiche technicien exige `?technicien=` (400 sans) : chacun lit le Technicien responsable.
    const q = (route) => (route.includes('technicien-scorecard') ? `?technicien=${tr.id}` : '')
    const bilan = []
    for (const route of [...CHANTIERS, ...AUTRES]) {
      bilan.push([route, (await aco.get(`${API}/${route}${q(route)}`, T)).status(), (await arh.get(`${API}/${route}${q(route)}`, T)).status(),
        (await atr.get(`${API}/${route}${q(route)}`, T)).status()])
    }
    console.log(`[ADRG71] ${bilan.map((b) => `${b[0]} co=${b[1]} rh=${b[2]} tr=${b[3]}`).join(' | ')}`)
    for (const [route, sc, sh, st] of bilan) {
      expect(sc, `Commercial ${route}`).toBe(CHANTIERS.includes(route) ? 403 : 200)
      expect(sh, `Admin RH ${route}`).toBe(403)
      expect(st, `Technicien responsable ${route}`).toBe(200)
    }
    // Écran /rapports au Commercial : carte chantiers (« Service ») absente, sans erreur ni requête refusée.
    const s = await ecranDe(page, suivi, testInfo, co)
    for (const passe of PASSES) {
      const ventes = reponse(s.p, /^\/reporting\/reports\/sales\/$/)
      s.reseau.length = 0
      if (passe) await s.p.reload(); else await s.p.goto('/rapports')
      expect((await ventes).status(), `${passe}Commercial : rapport ventes servi`).toBe(200)
      await s.p.getByRole('tab', { name: 'Service', exact: true }).click()
      await calme(s.p)
      const onglet = s.p.getByRole('tabpanel')
      await expect(onglet, `${passe}Commercial : onglet Service ouvert`).toBeVisible(V)
      console.log(`[ADRG71] ${passe}Commercial /rapports : ${J(s.reseau)}`)
      await expect(onglet.getByText('Service (chantiers + SAV)'), `${passe}Commercial : carte chantiers absente`).toHaveCount(0)
      await expect(s.p.getByText('Rapport indisponible'), `${passe}Commercial : aucune carte en erreur`).toHaveCount(0)
      expect(appels(s.reseau, SERVICE), `${passe}Commercial : aucun GET reporting/reports/service/`).toEqual([])
      expect(refus(s.reseau), `${passe}Commercial : aucune réponse refusée sur /rapports`).toEqual([])
    }
  } finally {
    await py(`from apps.installations.models import Installation
Installation.objects.filter(pk=${chantier}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── PF4.3 — ADRG73 : export Excel du tableau de bord sous `reporting_export` (route + bouton de /reporting) ──────
etape('PF4.3-ADRG73', ['ADRG73'], async ({ page, suivi, testInfo }) => {
  const co = await compteDe('Commercial', 'adrg73co')
  const cr = await compteDe('Commercial responsable', 'adrg73cr')
  expect(co.codes.includes('reporting_export'), 'Given : Commercial sans reporting_export').toBe(false)
  expect(cr.codes.includes('reporting_export'), 'Given : Commercial responsable avec reporting_export').toBe(true)
  const aco = await apiDe(testInfo, co)
  const acr = await apiDe(testInfo, cr)
  await refusNomme(await aco.get(`${API}/reporting/dashboard/?export=xlsx`, T), 'reporting_export', 'Commercial export xlsx')
  expect((await aco.get(`${API}/reporting/dashboard/`, T)).status(), 'Commercial : JSON 200').toBe(200)
  const x = await acr.get(`${API}/reporting/dashboard/?export=xlsx`, T)
  expect(x.status(), 'Commercial responsable : export 200').toBe(200)
  expect((await x.body()).subarray(0, 2).toString(), 'classeur PK…').toBe('PK')
  const bouton = (p) => p.getByRole('button', { name: /Exporter Excel/ })
  // Commercial : tableau de bord rendu (KPI), « Actualiser » présent, aucun « Exporter Excel », aucune requête refusée.
  const s = await ecranDe(page, suivi, testInfo, co)
  for (const passe of PASSES) {
    const tableau = reponse(s.p, /^\/reporting\/dashboard\/$/)
    s.reseau.length = 0
    if (passe) await s.p.reload(); else await s.p.goto('/reporting')
    expect((await tableau).status(), `${passe}Commercial : tableau de bord servi`).toBe(200)
    await expect(s.p.getByText('CA encaissé').first(), `${passe}Commercial : KPI du tableau de bord rendus`).toBeVisible(V)
    await expect(s.p.getByRole('button', { name: /Actualiser/ }).first(), `${passe}Commercial : barre d'actions rendue`).toBeVisible(V)
    await calme(s.p)
    await expect(bouton(s.p), `${passe}Commercial : aucun bouton « Exporter Excel »`).toHaveCount(0)
    expect(refus(s.reseau), `${passe}Commercial : aucune réponse refusée sur /reporting`).toEqual([])
  }
  // Commercial responsable : bouton présent, et il télécharge le classeur (GET ?export=xlsx → 200).
  const r = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of PASSES) {
    const tableau = reponse(r.p, /^\/reporting\/dashboard\/$/)
    if (passe) await r.p.reload(); else await r.p.goto('/reporting')
    expect((await tableau).status(), `${passe}Commercial responsable : tableau de bord servi`).toBe(200)
    await expect(bouton(r.p).first(), `${passe}Commercial responsable : bouton « Exporter Excel »`).toBeVisible(V)
  }
  const [exp] = await Promise.all([
    r.p.waitForResponse((x2) => /\/reporting\/dashboard\/$/.test(new URL(x2.url()).pathname) && new URL(x2.url()).searchParams.get('export') === 'xlsx', T),
    bouton(r.p).first().click(),
  ])
  expect(exp.status(), 'Commercial responsable : export depuis l\'écran').toBe(200)
})

// ── PF4.4 — ADRG118 : coût de revient, commissions, rentabilité de /rapports au seul palier administrateur ─────
const INSIGHTS_ADMIN = [
  ['coût de revient', /^\/reporting\/insights\/job-costing\/$/, 'Coût de revient par chantier'],
  ['commissions', /^\/reporting\/insights\/commissions\/$/, 'Commissions commerciales'],
  ['rentabilité', /^\/reporting\/insights\/profitability\/$/, 'Rentabilité par segment'],
]
etape('PF4.4-ADRG118', ['ADRG118'], async ({ page, suivi, testInfo }) => {
  for (const [nomRole, prefixe] of [['Commercial', 'adrg118co'], ['Commercial responsable', 'adrg118cr']]) {
    const c = await compteDe(nomRole, prefixe)
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of PASSES) {
      const ventes = reponse(s.p, /^\/reporting\/reports\/sales\/$/)
      s.reseau.length = 0
      if (passe) await s.p.reload(); else await s.p.goto('/rapports')
      expect((await ventes).status(), `${passe}${nomRole} : rapport ventes servi`).toBe(200)
      await s.p.getByRole('tab', { name: 'Insights', exact: true }).click()
      await calme(s.p)
      const onglet = s.p.getByRole('tabpanel')
      await expect(onglet, `${passe}${nomRole} : onglet Insights ouvert`).toBeVisible(V)
      console.log(`[ADRG118] ${passe}${nomRole} : ${J(s.reseau)}`)
      for (const [quoi, re, titre] of INSIGHTS_ADMIN) {
        expect(appels(s.reseau, re), `${passe}${nomRole} : aucun GET ${quoi}`).toEqual([])
        await expect(onglet.getByText(titre, { exact: true }), `${passe}${nomRole} : carte « ${titre} » absente`).toHaveCount(0)
      }
      expect(refus(s.reseau), `${passe}${nomRole} : aucune réponse refusée sur /rapports`).toEqual([])
    }
  }
  // Témoin Directeur : les trois lus (200) et les trois cartes rendues.
  const di = await compteDe('Directeur', 'adrg118di')
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const lus = INSIGHTS_ADMIN.map(([, re]) => reponse(d.p, re))
    if (passe) await d.p.reload(); else await d.p.goto('/rapports')
    for (const [i, rep] of (await Promise.all(lus)).entries()) expect(rep.status(), `${passe}Directeur : ${INSIGHTS_ADMIN[i][0]} servi`).toBe(200)
    await d.p.getByRole('tab', { name: 'Insights', exact: true }).click()
    const onglet = d.p.getByRole('tabpanel')
    for (const [, , titre] of INSIGHTS_ADMIN) {
      await expect(onglet.getByText(titre, { exact: true }).first(), `${passe}Directeur : carte « ${titre} » rendue`).toBeVisible(V)
    }
    await expect(d.p.getByText('Rapport indisponible'), `${passe}Directeur : aucune carte en erreur`).toHaveCount(0)
  }
})

// ── PF4.4 — ADRG119 : carte « Service (chantiers + SAV) » de /rapports sous la lecture des chantiers ─────────────
etape('PF4.4-ADRG119', ['ADRG119'], async ({ page, suivi, testInfo }) => {
  const co = await compteDe('Commercial', 'adrg119co')
  expect(co.codes.some((x) => x.startsWith('installation_')), 'Given : Commercial sans code installation_*').toBe(false)
  const s = await ecranDe(page, suivi, testInfo, co)
  for (const passe of PASSES) {
    const ventes = reponse(s.p, /^\/reporting\/reports\/sales\/$/)
    s.reseau.length = 0
    if (passe) await s.p.reload(); else await s.p.goto('/rapports')
    expect((await ventes).status(), `${passe}Commercial : rapport ventes servi`).toBe(200)
    await calme(s.p)
    await s.p.getByRole('tab', { name: 'Service', exact: true }).click()
    const onglet = s.p.getByRole('tabpanel')
    await expect(onglet, `${passe}Commercial : onglet Service ouvert`).toBeVisible(V)
    await expect(onglet.getByText('Service (chantiers + SAV)'), `${passe}Commercial : aucune carte Service`).toHaveCount(0)
    await expect(s.p.getByText('Rapport indisponible'), `${passe}Commercial : aucune carte « Rapport indisponible »`).toHaveCount(0)
    expect(appels(s.reseau, SERVICE), `${passe}Commercial : /reporting/reports/service/ jamais demandé`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial : aucune réponse refusée`).toEqual([])
  }
  // Témoin Technicien responsable (installation_voir) : demandé (200), carte remplie.
  const tr = await compteDe('Technicien responsable', 'adrg119tr')
  const t = await ecranDe(page, suivi, testInfo, tr)
  for (const passe of PASSES) {
    const service = reponse(t.p, SERVICE)
    if (passe) await t.p.reload(); else await t.p.goto('/rapports')
    expect((await service).status(), `${passe}Technicien responsable : rapport service servi`).toBe(200)
    await t.p.getByRole('tab', { name: 'Service', exact: true }).click()
    const onglet = t.p.getByRole('tabpanel')
    await expect(onglet.getByText('Service (chantiers + SAV)').first(), `${passe}Technicien responsable : carte Service`).toBeVisible(V)
    await expect(onglet.getByText(/Tickets ouverts/).first(), `${passe}Technicien responsable : carte remplie`).toBeVisible(V)
    await expect(onglet.getByText('Rapport indisponible'), `${passe}Technicien responsable : carte non en erreur`).toHaveCount(0)
  }
})

// ── PF4.4 — ADRG120 : accueil /dashboard selon les droits (tableau servi, leads, « Mes chiffres ») ──────────────
const TABLEAU = /^\/reporting\/dashboard\/$/
const LEADS = /^\/crm\/leads\/$/
const ATTEINTE = /^\/crm\/objectifs\/attainment\/$/
etape('PF4.4-ADRG120', ['ADRG120'], async ({ page, suivi, testInfo }) => {
  // Technicien : ni tableau de bord servi, ni leads, ni « Mes chiffres » ; aucune requête refusée.
  const te = await compteDe('Technicien', 'adrg120te')
  const s = await ecranDe(page, suivi, testInfo, te)
  for (const passe of PASSES) {
    await charger(s, '/dashboard', passe)
    await expect(s.p.getByText('Tableau de bord').first(), `${passe}Technicien : accueil rendu`).toBeVisible(V)
    await calme(s.p)
    console.log(`[ADRG120] ${passe}Technicien /dashboard : ${J(s.reseau)}`)
    for (const [quoi, re] of [['reporting/dashboard/', TABLEAU], ['crm/leads/', LEADS], ['crm/objectifs/attainment/', ATTEINTE]]) {
      expect(appels(s.reseau, re), `${passe}Technicien : aucun GET ${quoi}`).toEqual([])
    }
    await expect(s.p.getByText('Mes chiffres', { exact: true }), `${passe}Technicien : pas de carte « Mes chiffres »`).toHaveCount(0)
    expect(refus(s.reseau), `${passe}Technicien : aucune réponse refusée sur l'accueil`).toEqual([])
  }
  // Viewer : aucune requête vers reporting/dashboard/ (et aucune réponse refusée).
  const vi = await compteDe('Viewer', 'adrg120vi')
  const v = await ecranDe(page, suivi, testInfo, vi)
  for (const passe of PASSES) {
    await charger(v, '/dashboard', passe)
    await expect(v.p.getByText('Tableau de bord').first(), `${passe}Viewer : accueil rendu`).toBeVisible(V)
    await calme(v.p)
    console.log(`[ADRG120] ${passe}Viewer /dashboard : ${J(v.reseau)}`)
    expect(appels(v.reseau, TABLEAU), `${passe}Viewer : aucun GET reporting/dashboard/`).toEqual([])
    expect(refus(v.reseau), `${passe}Viewer : aucune réponse refusée sur l'accueil`).toEqual([])
  }
  // Commercial : les trois lus (200), « Mes chiffres » et le CA mensuel servis.
  const co = await compteDe('Commercial', 'adrg120co')
  const c = await ecranDe(page, suivi, testInfo, co)
  for (const passe of PASSES) {
    const tableau = reponse(c.p, TABLEAU)
    const leads = reponse(c.p, LEADS)
    await charger(c, '/dashboard', passe)
    expect((await tableau).status(), `${passe}Commercial : tableau de bord servi`).toBe(200)
    expect((await leads).status(), `${passe}Commercial : leads lus`).toBe(200)
    await expect(c.p.getByText('Mes chiffres', { exact: true }).first(), `${passe}Commercial : carte « Mes chiffres »`).toBeVisible(V)
    await expect.poll(() => appels(c.reseau, ATTEINTE).length, { message: `${passe}Commercial : atteinte d'objectifs lue`, timeout: 60_000 }).toBeGreaterThanOrEqual(1)
    expect(appels(c.reseau, ATTEINTE).every((l) => l.endsWith('→ 200')), `${passe}Commercial : atteinte ${J(appels(c.reseau, ATTEINTE))}`).toBe(true)
    await expect(c.p.getByText("Chiffre d'affaires mensuel").first(), `${passe}Commercial : carte CA mensuel`).toBeVisible(V)
    await expect(c.p.getByText(/Accès réservé : chiffre d'affaires/), `${passe}Commercial : CA mensuel servi (pas « accès réservé »)`).toHaveCount(0)
    expect(refus(c.reseau), `${passe}Commercial : aucune réponse refusée sur l'accueil`).toEqual([])
  }
})

// ── PF4.4 — ADRG110 : compte produits de l'onboarding lu seulement avec `stock_voir` ──────────────────────────────
const PRODUITS = /^\/stock\/produits\/$/
etape('PF4.4-ADRG110', ['ADRG110'], async ({ page, suivi, testInfo }) => {
  const ct = await compteDe('Commercial terrain', 'adrg110ct')
  expect(ct.codes.some((x) => x.startsWith('stock_')), `Given : Commercial terrain sans code stock ${J(ct.codes)}`).toBe(false)
  const s = await ecranDe(page, suivi, testInfo, ct)
  // /visites, puis l'accueil des applications, puis /visites rechargé : trois chargements de pages internes.
  for (const [url, passe, temoin] of [['/visites', '', 'Ma journée'], ['/apps', '', null], ['/visites', 'rechargé : ', 'Ma journée']]) {
    s.reseau.length = 0
    if (passe) { await s.p.goto(url); s.reseau.length = 0; await s.p.reload() } else await s.p.goto(url)
    if (temoin) await expect(s.p.getByText(temoin).first(), `${passe}Commercial terrain ${url} : écran rendu`).toBeVisible(V)
    else await expect(s.p.getByRole('link').first(), `Commercial terrain ${url} : écran rendu`).toBeVisible(V)
    await calme(s.p)
    console.log(`[ADRG110] ${passe}Commercial terrain ${url} (${s.p.url()}) : ${J(s.reseau)}`)
    expect(appels(s.reseau, PRODUITS), `${passe}Commercial terrain ${url} : aucun GET stock/produits/`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial terrain ${url} : aucune réponse refusée`).toEqual([])
  }
  // Témoin Directeur : la lecture `stock/produits/?page_size=1` est faite (200) et l'étape « produit » comptée.
  const di = await compteDe('Directeur', 'adrg110di')
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const compteProduits = d.p.waitForResponse((r) => {
      const u = new URL(r.url())
      return PRODUITS.test(u.pathname.slice(API.length)) && u.searchParams.get('page_size') === '1' && r.request().method() === 'GET'
    }, T)
    if (passe) await d.p.reload(); else await d.p.goto('/parametres?onglet=onboarding')
    const rep = await compteProduits
    expect(rep.status(), `${passe}Directeur : compte des produits lu`).toBe(200)
    const corps = await rep.json()
    const n = Array.isArray(corps) ? corps.length : (corps.count ?? corps.results?.length ?? 0)
    expect(n, `${passe}Directeur : catalogue démo non vide`).toBeGreaterThan(0)
    const etapeProduit = d.p.locator('li').filter({ hasText: 'Créez votre premier produit' }).first()
    await expect(etapeProduit, `${passe}Directeur : étape « produit » de la prise en main`).toBeVisible(V)
    await expect(etapeProduit, `${passe}Directeur : étape « produit » comptée (faite)`).toHaveClass(/border-success/)
  }
})

// ── PF4.4 — ADRG111 : types d'intervention et étapes de checklist de /parametres sous `installation_voir` ──────────
const TYPES_ITV = /^\/installations\/types-intervention\/$/
const ETAPES_CK = /^\/installations\/checklist-etapes\/$/
etape('PF4.4-ADRG111', ['ADRG111'], async ({ page, suivi, testInfo }) => {
  const cr = await compteDe('Commercial responsable', 'adrg111cr')
  expect(cr.codes.some((x) => x.startsWith('installation_')), 'Given : Commercial responsable sans code installation_*').toBe(false)
  const s = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of PASSES) {
    await charger(s, '/parametres', passe)
    await expect(s.p.getByText('Société & identité').first(), `${passe}Commercial responsable : Paramètres ouverts`).toBeVisible(V)
    await calme(s.p)
    console.log(`[ADRG111] ${passe}Commercial responsable /parametres : ${J(s.reseau)}`)
    expect(appels(s.reseau, TYPES_ITV), `${passe}Commercial responsable : aucun GET types-intervention/`).toEqual([])
    expect(appels(s.reseau, ETAPES_CK), `${passe}Commercial responsable : aucun GET checklist-etapes/`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial responsable : aucune réponse refusée`).toEqual([])
  }
  // Témoin Directeur : les deux lus (200), onglet Avancé › « Chantiers — Types d'intervention » rempli.
  const di = await compteDe('Directeur', 'adrg111di')
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const types = reponse(d.p, TYPES_ITV)
    const etapes = reponse(d.p, ETAPES_CK)
    if (passe) await d.p.reload(); else await d.p.goto('/parametres?onglet=avance')
    const rt = await types
    expect(rt.status(), `${passe}Directeur : types d'intervention lus`).toBe(200)
    expect((await etapes).status(), `${passe}Directeur : étapes de checklist lues`).toBe(200)
    const corps = await rt.json()
    const lignes = Array.isArray(corps) ? corps : (corps.results ?? [])
    expect(lignes.length, `${passe}Directeur : types d'intervention servis`).toBeGreaterThan(0)
    await expect(d.p.getByText("Chantiers — Types d'intervention").first(), `${passe}Directeur : référentiel chantiers`).toBeVisible(V)
    await expect(d.p.locator(`input[value="${lignes[0].libelle.replace(/"/g, '\\"')}"]`).first(),
      `${passe}Directeur : type « ${lignes[0].libelle} » affiché`).toBeVisible(V)
  }
})

// ── PF4.4 — ADRG112 : demandes de personnes concernées (Confidentialité) lues seulement avec `dsr_traiter` ─────────
const DSR = /^\/core\/dsr-requests\/$/
etape('PF4.4-ADRG112', ['ADRG112'], async ({ page, suivi, testInfo }) => {
  const cr = await compteDe('Commercial responsable', 'adrg112cr')
  expect(cr.codes.includes('dsr_traiter'), 'Given : Commercial responsable sans dsr_traiter').toBe(false)
  const s = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of PASSES) {
    await charger(s, '/parametres?onglet=confidentialite', passe)
    await expect(s.p.getByText('Accès refusé').first(), `${passe}Commercial responsable : refus affiché d'emblée`).toBeVisible(V)
    await expect(s.p.getByText(/exigent le droit .*\(dsr_traiter\)/).first(), `${passe}Commercial responsable : le refus nomme dsr_traiter`).toBeVisible(V)
    await calme(s.p)
    console.log(`[ADRG112] ${passe}Commercial responsable Confidentialité : ${J(s.reseau)}`)
    expect(appels(s.reseau, DSR), `${passe}Commercial responsable : aucun GET core/dsr-requests/`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial responsable : aucune réponse refusée`).toEqual([])
  }
  // Témoin Directeur : liste lue (200) et rendue.
  const di = await compteDe('Directeur', 'adrg112di')
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const liste = reponse(d.p, DSR)
    if (passe) await d.p.reload(); else await d.p.goto('/parametres?onglet=confidentialite')
    expect((await liste).status(), `${passe}Directeur : demandes lues`).toBe(200)
    await expect(d.p.getByText('Demandes de personnes concernées').first(), `${passe}Directeur : liste des demandes affichée`).toBeVisible(V)
    await expect(d.p.getByText(/exigent le droit .*\(dsr_traiter\)/), `${passe}Directeur : aucun refus`).toHaveCount(0)
  }
})

// ── PF4.4 — ADRG113 : `crm/assignable-users/` appelé seulement quand la règle serveur l'autorise ─────────────────
const ASSIGNABLES = /^\/crm\/assignable-users\/$/
etape('PF4.4-ADRG113', ['ADRG113'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const vi = await compteDe('Viewer', 'adrg113vi')
  const co = await compteDe('Commercial', 'adrg113co')
  const lv = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG113 Viewer ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead Viewer')
  const lc = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG113 Commercial ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead Commercial')
  await py(`from apps.crm.models import Lead
Lead.objects.filter(pk=${lv.id}).update(owner_id=${vi.id})
Lead.objects.filter(pk=${lc.id}).update(owner_id=${co.id})
sortie(1)`)
  const verifier = (s, quoi) => {
    console.log(`[ADRG113] ${quoi} : ${J(s.reseau)}`)
    expect(appels(s.reseau, ASSIGNABLES), `${quoi} : aucun GET crm/assignable-users/`).toEqual([])
    expect(refus(s.reseau), `${quoi} : aucune réponse refusée`).toEqual([])
  }
  // Viewer : liste des leads, fiche de son lead, agenda.
  const v = await ecranDe(page, suivi, testInfo, vi)
  for (const passe of PASSES) {
    const liste = reponse(v.p, LEADS)
    await charger(v, '/crm/leads', passe)
    expect((await liste).status(), `${passe}Viewer : leads lus`).toBe(200)
    await v.p.getByRole('radio', { name: 'Vue liste' }).click()
    await expect(v.p.getByText(lv.nom).first(), `${passe}Viewer : son lead listé`).toBeVisible(V)
    await calme(v.p)
    verifier(v, `${passe}Viewer liste des leads`)
    await charger(v, `/crm/leads/${lv.id}`, passe)
    await expect(v.p.locator('.lw-rail-triade').first(), `${passe}Viewer : fiche du lead rendue`).toBeVisible(V)
    await expect(v.p.getByText(lv.nom).first(), `${passe}Viewer : fiche de SON lead`).toBeVisible(V)
    await calme(v.p)
    verifier(v, `${passe}Viewer fiche lead`)
    await charger(v, '/calendrier', passe)
    await expect(v.p.getByRole('heading', { name: 'Calendrier' }), `${passe}Viewer : agenda rendu`).toBeVisible(V)
    await calme(v.p)
    verifier(v, `${passe}Viewer /calendrier`)
  }
  // Technicien : agenda.
  const te = await compteDe('Technicien', 'adrg113te')
  const t = await ecranDe(page, suivi, testInfo, te)
  for (const passe of PASSES) {
    await charger(t, '/calendrier', passe)
    await expect(t.p.getByRole('heading', { name: 'Calendrier' }), `${passe}Technicien : agenda rendu`).toBeVisible(V)
    await calme(t.p)
    verifier(t, `${passe}Technicien /calendrier`)
  }
  // Témoin Commercial : la liste des responsables est lue (200, non vide) à la liste et à la fiche.
  const c = await ecranDe(page, suivi, testInfo, co)
  for (const [url, quoi] of [['/crm/leads', 'liste des leads'], [`/crm/leads/${lc.id}`, 'fiche lead']]) {
    const lus = reponse(c.p, ASSIGNABLES)
    await charger(c, url, '')
    const rep = await lus
    expect(rep.status(), `Commercial ${quoi} : responsables lus`).toBe(200)
    const corps = await rep.json()
    const users = Array.isArray(corps) ? corps : (corps.results ?? [])
    expect(users.length, `Commercial ${quoi} : liste des responsables remplie`).toBeGreaterThan(0)
    expect(refus(c.reseau), `Commercial ${quoi} : aucune réponse refusée`).toEqual([])
  }
  await expect(c.p.locator('.lw-rail-triade .ap-trigger').first(), 'Commercial : sélecteur « Responsable » de la fiche').toBeVisible(V)
})
