// Preuve en direct du groupe ALEC, lot 3 (contre-visite C-ALEC-VER2-203) : ALEC47 — sans `client_pii_voir`, la
// recherche des leads n'interroge ni le téléphone ni l'e-mail ; le nom trouve toujours le lead.
// AUCUN rôle livré n'a `crm_voir` sans `client_pii_voir` (constat « latent ») : la clause demande un rôle FABRIQUÉ —
// celui du `setUp` de `GardePiiTests` (jeu `COMMERCIAL_PERMISSIONS` du registre sans `client_pii_voir`), créé ici dans
// la société démo. Témoin : un compte au rôle SYSTÈME « Commercial » (registre, `init_roles`), propriétaire d'un lead
// au MÊME numéro. Connexion par le VRAI écran de connexion ; écran Leads (barre « Rechercher nom, téléphone,
// email… ») ; la même session interroge la VRAIE route `GET /api/django/crm/leads/?search=` (celle que corrige la
// tâche : l'écran Leads filtre la liste déjà servie, où le numéro d'un rôle sans PII arrive masqué). Persistance : n/a
// (lecture) — l'écran est relu après rechargement. Leads retirés à la fin.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, listeDe, setLeadsView, telephoneMobileUnique, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC47'])
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

/** Écran sous le compte `nom` : contexte neuf (SW bloqué), connexion par l'ÉCRAN de connexion, visites marquées vues.
 *  Renvoie {p, api} (`api` = requêtes de CE compte, même jarre de cookies). */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
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
  const p = suivi.surveiller(await ctx.newPage())
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return { p, api: ctx.request }
}

etape('PF6.2-ALEC47', ['ALEC47'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const TEL = telephoneMobileUnique()
  const NOM = `Temoin ALEC47 ${m}`
  const EMAIL = `temoin-alec47-${m}@example.invalid`
  const sans = `alec47sp_${m}`
  const temoin = `alec47co_${m}`
  const x = await py(`from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
from apps.crm.models import Lead
CO = ${SOC}
r = Role.objects.create(company_id=CO, nom=${J(`Commercial sans PII ALEC47 ${m}`)}, est_systeme=False,
    permissions=[p for p in COMMERCIAL_PERMISSIONS if p != 'client_pii_voir'])
u = compte(${J(sans)}, role=r.pk, societe=CO)
c = compte(${J(temoin)}, role=Role.objects.get(company_id=CO, nom='Commercial', est_systeme=True).pk, societe=CO)
a = Lead.objects.create(company_id=CO, nom=${J(NOM)}, prenom='Lead', telephone=${J(TEL)}, whatsapp=${J(TEL)}, email=${J(EMAIL)}, owner=u)
b = Lead.objects.create(company_id=CO, nom=${J(`Autre ALEC47 ${m}`)}, prenom='Lead', telephone=${J(TEL)}, owner=c)
u.refresh_from_db()
sortie(dict(role=r.pk, a=a.pk, b=b.pk, pii=[u.can_view_client_pii, c.can_view_client_pii], codes=sorted(r.permissions)[:3]))`)
  expect(x.pii, 'Given : le rôle fabriqué n\'a pas client_pii_voir, le Commercial livré l\'a').toEqual([false, true])
  try {
    // Ce que la VRAIE route rend à une session donnée pour `?search=`.
    const recherche = async (api, terme) => listeDe(await lireJson(await api.get(`${API}/crm/leads/?search=${encodeURIComponent(terme)}`, T), `search=${terme}`)).map((l) => l.id)
    const chercherAEcran = async (p, terme) => {
      const champ = p.getByPlaceholder('Rechercher nom, téléphone, email…')
      await champ.fill(terme)
      await expect(champ).toHaveValue(terme)
      await p.waitForTimeout(600) // débounce de la barre (250 ms) puis recalcul différé de la liste
    }
    const carte = (p, id) => p.locator(`[data-lead-id="${id}"]`)
    const ouvrirLeads = async (p, passe) => {
      await p.goto('/crm/leads')
      await setLeadsView(p, 'kanban')
      await expect(p.getByPlaceholder('Rechercher nom, téléphone, email…'), `${passe}écran Leads`).toBeVisible({ timeout: 60_000 })
      await p.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    }

    // ── Témoin d'abord : le Commercial livré trouve SON lead par le numéro (écran + route). ──
    const co = await ecran(page, suivi, testInfo, temoin)
    expect(await recherche(co.api, TEL), 'Commercial : route search=<numéro> trouve son lead').toContain(x.b)
    await ouvrirLeads(co.p, 'Commercial : ')
    await chercherAEcran(co.p, TEL)
    await expect(carte(co.p, x.b), 'Commercial : son lead trouvé par le numéro à l\'écran').toBeVisible({ timeout: 30_000 })

    // ── Rôle sans client_pii_voir : numéro → rien ; nom → le lead ; e-mail → rien. ──
    const sp = await ecran(co.p, suivi, testInfo, sans)
    const p = sp.p
    expect(await recherche(sp.api, TEL), 'sans PII : route search=<numéro> vide').toEqual([])
    expect(await recherche(sp.api, NOM), 'sans PII : route search=<nom> trouve le lead').toEqual([x.a])
    expect(await recherche(sp.api, EMAIL), 'sans PII : route search=<e-mail> vide').toEqual([])
    for (const passe of ['', 'rechargé : ']) {
      if (passe) await p.reload()
      await ouvrirLeads(p, passe)
      await chercherAEcran(p, NOM)
      await expect(carte(p, x.a), `${passe}sans PII : le lead trouvé par son nom`).toBeVisible({ timeout: 30_000 })
      await chercherAEcran(p, EMAIL)
      await expect(carte(p, x.a), `${passe}sans PII : rien par l'e-mail`).toHaveCount(0)
      await chercherAEcran(p, TEL)
      await expect(carte(p, x.a), `${passe}sans PII : aucune ligne par le numéro`).toHaveCount(0)
      await expect(carte(p, x.b), `${passe}sans PII : jamais le lead du témoin`).toHaveCount(0)
    }
    // Re-lu par la route après l'écran : toujours vide par le numéro.
    expect(await recherche(sp.api, TEL), 'sans PII, relu : route search=<numéro> vide').toEqual([])
  } finally {
    await py(`from apps.crm.models import Lead
Lead.all_objects.filter(pk__in=${J([x.a, x.b])}).delete() if hasattr(Lead, 'all_objects') else Lead.objects.filter(pk__in=${J([x.a, x.b])}).delete()
sortie(1)`).catch(() => null)
  }
})
