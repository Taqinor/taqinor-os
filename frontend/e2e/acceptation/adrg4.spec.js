// Rejeu en direct d'ADRG122 (défaut vu en direct le 14/11/2026 sur l'accueil `/apps`) : la tournée du
// jour (`installations/interventions/ma-tournee/`) n'est plus demandée en arrière-plan — pré-chargement
// matinal de la coquille, widget « À faire aujourd'hui » — pour un compte auquel le serveur la refuse.
// Rôles LIVRÉS du registre (rôles système de la société de demo_admin, relus par leur nom, jamais un rôle
// fabriqué). Connexion par le VRAI écran de connexion. Horloge du navigateur figée à 8 h 30 (UTC) du jour :
// le pré-chargement n'existe qu'avant midi, le rejeu doit dire la même chose à toute heure.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps, boutonNouveauLead } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG122'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
// Onglets des rôles : fermés APRÈS l'étape (ses oracles, dont le 8, relisent chaque page encore ouverte).
const OUVERTS = []
test.afterEach(async () => { for (const c of OUVERTS.splice(0)) await c.close().catch(() => undefined) })

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const J = JSON.stringify
const deux = (n) => String(n).padStart(2, '0')
const MAINTENANT = new Date()
// Jour du rejeu (calendrier UTC) et son matin : l'onglet tourne en UTC, 8 h 30 y est « avant midi ».
const JOUR = `${MAINTENANT.getUTCFullYear()}-${deux(MAINTENANT.getUTCMonth() + 1)}-${deux(MAINTENANT.getUTCDate())}`
const MATIN = new Date(`${JOUR}T08:30:00Z`)
const TOURNEE = /\/installations\/interventions\/ma-tournee\//
const MOBILE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société (registre, `init_roles`). Renvoie {username, id}. */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True).pk
sortie(compte(${J(username)}, role=r, societe=${SOC}).id)`)
  return { username, id }
}

/** Onglet NEUF (aucune session, horloge au matin), observé par les oracles ; `appels` reçoit chaque
 *  requête de tournée émise par cet onglet (méthode, URL). */
async function ongletDuMatin(page, suivi, testInfo, options = {}) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    timezoneId: 'UTC', ...options,
  })
  await ctx.clock.setFixedTime(MATIN)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  OUVERTS.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  const appels = []
  p.on('request', (q) => { if (TOURNEE.test(q.url())) appels.push(`${q.method()} ${q.url()}`) })
  return { p, appels }
}

/** L'accueil est rendu et le réseau s'est tu : une absence de requête vaut alors preuve. */
async function accueilRendu(p, quoi) {
  await expect(p, `${quoi} : accueil /apps`).toHaveURL(/\/apps/, { timeout: 60_000 })
  await expect(p.getByRole('heading', { name: 'Mes applications' }), `${quoi} : grille des applications`).toBeVisible({ timeout: 60_000 })
  await p.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined)
}

// ── Compte auquel le serveur refuse la tournée : plus aucun appel, plus aucun 4xx ───────────────────

etape('PF4.4-ADRG122-refus', ['ADRG122'], async ({ page, suivi, testInfo }) => {
  const co = await compteDe('Commercial', 'adrg122co')
  // Témoin : le serveur refuse bien la tournée à ce rôle (sinon l'absence d'appel ne prouverait rien).
  const temoin = await py(`from rest_framework.test import APIClient
c = APIClient(); c.force_authenticate(U.objects.get(pk=${co.id}))
sortie(c.get('/api/django/installations/interventions/ma-tournee/', {'date': ${J(JOUR)}}, HTTP_HOST='localhost').status_code)`)
  expect(temoin, 'la route refuse la tournée au Commercial').toBe(403)

  // 1) Bureau : connexion réelle → accueil `/apps`, puis une app, puis retour (la coquille se remonte).
  const { p, appels } = await ongletDuMatin(page, suivi, testInfo)
  await uiLoginJusquAuxApps(p, { username: co.username, password: MDP_ESSAI })
  expect(await p.evaluate(() => new Date().getHours()), 'horloge de l’onglet : le matin').toBe(8)
  await accueilRendu(p, 'Commercial')
  expect(appels, 'Commercial, accueil après connexion : aucune requête de tournée').toEqual([])
  await p.goto('/crm/leads')
  await expect(boutonNouveauLead(p), 'Commercial : écran des leads rendu').toBeVisible({ timeout: 60_000 })
  await p.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined)
  await p.goto('/apps')
  await accueilRendu(p, 'Commercial, retour')
  await p.reload()
  await accueilRendu(p, 'Commercial, rechargé')
  expect(appels, 'Commercial, après navigation et rechargement : toujours aucune requête de tournée').toEqual([])
  expect(await p.evaluate(() => localStorage.getItem('taqinor.prechargementTournee')), 'aucun témoin de pré-chargement posé').toBeNull()

  // 2) Largeur mobile : l'accueil mobile du commercial et son bloc « À faire aujourd'hui ».
  const m = await ongletDuMatin(page, suivi, testInfo, MOBILE)
  await uiLoginJusquAuxApps(m.p, { username: co.username, password: MDP_ESSAI })
  await m.p.goto('/mobile/commercial')
  const bloc = m.p.locator('[data-widget="a-faire-aujourdhui"]')
  await expect(bloc, 'bloc « À faire aujourd’hui » rendu').toBeVisible({ timeout: 60_000 })
  // Le bloc a fini de lire ses sources (liste, « rien d'urgent » ou avis de lecture incomplète).
  await expect(bloc.locator('ul').or(bloc.getByText("Rien d'urgent aujourd'hui")).or(bloc.getByText(/n'a pas pu être lue/)).first(),
    'bloc chargé').toBeVisible({ timeout: 60_000 })
  await m.p.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined)
  expect(m.appels, 'Commercial, accueil mobile : aucune requête de tournée').toEqual([])
})

// ── Technicien : la tournée reste pré-chargée et affichée ───────────────────────────────────────────

etape('PF4.4-ADRG122-tournee', ['ADRG122'], async ({ page, suivi, testInfo }) => {
  const te = await compteDe('Technicien', 'adrg122te')
  const ref = `CH-ADRG122-${marque().toUpperCase()}`
  const x = await py(`from apps.installations.models import Installation, Intervention
co = ${SOC}
a = U.objects.get(username='demo_admin')
inst = Installation.objects.create(company_id=co, reference=${J(ref)})
iv = Intervention.objects.create(company_id=co, installation=inst, type_intervention='controle',
    technicien_id=${te.id}, date_prevue=${J(JOUR)}, created_by=a)
sortie(dict(itv=iv.id, inst=inst.id))`)
  try {
    const { p, appels } = await ongletDuMatin(page, suivi, testInfo)
    const reponse = p.waitForResponse((r) => TOURNEE.test(r.url()), { timeout: 120_000 })
    await uiLoginJusquAuxApps(p, { username: te.username, password: MDP_ESSAI })
    await accueilRendu(p, 'Technicien')
    const rep = await reponse
    expect(rep.status(), 'Technicien, accueil du matin : tournée servie').toBe(200)
    expect(new URL(rep.url()).searchParams.get('date'), 'tournée demandée pour le jour').toBe(JOUR)
    expect(((await rep.json()).stops || []).map((s) => s.id), 'l’intervention du jour est dans la tournée pré-chargée').toContain(x.itv)
    await expect.poll(() => p.evaluate(() => localStorage.getItem('taqinor.prechargementTournee')),
      { message: 'témoin de pré-chargement posé pour le jour', timeout: 30_000 }).toBe(JOUR)
    // Une seule fois par jour et par appareil : revenir sur l'accueil ne redemande rien.
    const avant = appels.length
    await p.goto('/apps')
    await accueilRendu(p, 'Technicien, retour')
    expect(appels.length, 'pas de second pré-chargement le même jour').toBe(avant)
    // « Ma journée » affiche sa tournée.
    await p.goto('/ma-journee')
    await expect(p.getByRole('button', { name: new RegExp(ref) }).first(), 'Ma journée : l’intervention du jour est listée').toBeVisible({ timeout: 60_000 })
  } finally {
    await py(`from apps.installations.models import Installation, Intervention
Intervention.objects.filter(pk=${x.itv}).delete()
Installation.objects.filter(pk=${x.inst}).delete()`).catch(() => undefined)
  }
})
