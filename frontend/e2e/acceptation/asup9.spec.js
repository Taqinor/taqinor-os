// Preuve en direct du groupe ASUP, lot 9 (17/11/2026) : ASUP68 — « Anonymiser (RGPD) » d'un client caviarde TOUTES
// les traces de corbeille de ses leads, entrées RESTAURÉES et journal d'annulation (`DeletionRecord`) compris. Compte
// d'essai au rôle SYSTÈME « Directeur » du registre (relu par son nom dans la société démo), connexion par la vraie
// route `/token/` dans un navigateur à part ; chaque réponse de l'API est relevée. Le lead (nom distinctif) est
// supprimé, restauré puis re-supprimé par les vraies routes ; « Anonymiser (RGPD) » se joue À L'ÉCRAN, sur la fiche
// du client. Données propres (shell Django), retirées en fin d'étape ; chaque écran est relu après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ASUP', ['ASUP68'])
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
  if (comptes.length) {
    await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
})

/** Compte d'essai : rôle SYSTÈME `nomRole` ; {username, id, nomRole, codes}. */
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

/** Navigateur à part connecté par /token/ ; visites guidées marquées vues ; réponses de l'API relevées dans `reseau`,
 *  console.error dans `consoles`. La page demo_admin de l'étape est refermée (la capture montre l'écran du rôle). */
async function ecranDe(page, suivi, testInfo, c) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  OUVERTS.push(() => ctx.close())
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
    } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  const p = suivi.surveiller(await ctx.newPage())
  const reseau = []
  const consoles = []
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  p.on('console', (msg) => { if (msg.type() === 'error') consoles.push(msg.text()) })
  p.on('pageerror', (e) => consoles.push(`pageerror : ${e.message}`))
  return { ctx, p, reseau, consoles, api: ctx.request, c }
}
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
const reponse = (p, re, methode = 'GET', filtre = () => true) => p.waitForResponse((r) => {
  const u = new URL(r.url())
  return re.test(u.pathname.slice(API.length)) && r.request().method() === methode && filtre(u)
}, T)
const toast = (p, texte) => p.locator('[data-sonner-toast]').filter({ hasText: texte }).first()
const PASSES = ['', 'relu après rechargement : ']

/** Toutes les cellules texte d'un classeur xlsx (octets), lues par openpyxl dans le shell Django. */
const cellulesDuClasseur = (octets) => py(`import base64, io
from openpyxl import load_workbook
wb = load_workbook(io.BytesIO(base64.b64decode('${Buffer.from(octets).toString('base64')}')), read_only=True, data_only=True)
cellules = []
for ws in wb.worksheets:
    for row in ws.iter_rows(values_only=True):
        cellules += [str(c) for c in row if c is not None]
sortie(cellules)`)

// ── PF10 — ASUP68 : lead supprimé, restauré, re-supprimé puis anonymisé ⇒ plus son nom nulle part dans la corbeille ──
etape('PF10-ASUP68-corbeille-anonymisee', ['ASUP68'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `Karim B. ${m}`
  const di = await compteDe('Directeur', 'asup68di')
  const ids = await py(`from apps.crm.models import Client, Lead
CO = ${SOC}
cl = Client.objects.create(company_id=CO, nom=${J(nom)}, prenom='', type_client='particulier', telephone=${J(telephoneMobileUnique())}, email='asup68-${m}@asup.invalid')
l = Lead.objects.create(company_id=CO, nom=${J(nom)}, client=cl, email='asup68-${m}@asup.invalid')
sortie(dict(client=cl.pk, lead=l.pk))`)
  try {
    const x = await apiDe(testInfo, di)
    // Given : supprimé (entrée active), restauré (entrée restaurée), re-supprimé (nouvelle entrée active).
    const sup1 = await x.delete(`${API}/crm/leads/${ids.lead}/`, T)
    expect(sup1.status(), `Directeur supprime le lead : ${(await sup1.text()).slice(0, 200)}`).toBe(200)
    const res = await x.post(`${API}/trash/corbeille/${(await sup1.json()).corbeille_id}/restaurer/`, T)
    expect(res.status(), `Directeur restaure le lead : ${(await res.text()).slice(0, 200)}`).toBe(200)
    const sup2 = await x.delete(`${API}/crm/leads/${ids.lead}/`, T)
    expect(sup2.status(), `Directeur re-supprime le lead : ${(await sup2.text()).slice(0, 200)}`).toBe(200)
    const avant = await lireJson(await x.get(`${API}/trash/corbeille/?restaures=1&type=Lead`, T), 'journal avant anonymisation')
    const lignes = (Array.isArray(avant) ? avant : avant.results || []).filter((e) => (e.libelle_snapshot || '').includes(nom))
    expect(lignes.map((e) => !!e.restaure_le).sort(), 'Given : le journal garde le nom du lead, une entrée restaurée et une active').toEqual([false, true])

    // When : « Anonymiser (RGPD) » sur la fiche du client, par le Directeur, à l'écran.
    const s = await ecranDe(page, suivi, testInfo, di)
    await s.p.goto('/crm')
    await s.p.getByPlaceholder('Rechercher nom, email, tél, ICE, IF, RC, CIN…').fill(nom)
    await s.p.getByRole('row').filter({ hasText: nom }).first().click({ timeout: 60_000 })
    await expect(s.p.getByText(`Fiche client — ${nom}`), 'fiche du client ouverte').toBeVisible(V)
    await s.p.getByRole('button', { name: 'Anonymiser (RGPD)' }).click()
    const dlg = s.p.getByRole('alertdialog')
    await expect(dlg).toContainText('Anonymiser ce client ?')
    await dlg.getByRole('button', { name: 'Anonymiser définitivement' }).click()
    await expect(toast(s.p, 'Client anonymisé (données personnelles effacées)'), 'client anonymisé').toBeVisible(V)

    // Then : /parametres/corbeille, « Inclure les éléments restaurés » coché — ni le nom, ni la marque ; « Lead anonymisé » listé.
    for (const passe of PASSES) {
      s.reseau.length = 0
      s.consoles.length = 0
      const liste = reponse(s.p, /^\/trash\/corbeille\/$/, 'GET', (u) => u.searchParams.get('restaures') === '1')
      if (passe) await s.p.reload(); else await s.p.goto('/parametres/corbeille')
      await expect(s.p.getByRole('heading', { level: 1, name: /Corbeille/ }), `${passe}écran Corbeille`).toBeVisible(V)
      const interrupteur = s.p.getByRole('switch', { name: /Inclure les éléments/ })
      await expect(interrupteur, `${passe}interrupteur « Inclure les éléments … restaurés »`).toBeVisible(V)
      if ((await interrupteur.getAttribute('aria-checked')) !== 'true') await interrupteur.click()
      const rep = await liste
      expect(rep.status(), `${passe}journal lu avec les éléments restaurés`).toBe(200)
      expect(JSON.stringify(await rep.json()), `${passe}JSON de la liste : sans le nom`).not.toContain(m)
      const tableau = s.p.getByTestId('corbeille-table')
      await expect(tableau, `${passe}tableau de la corbeille rendu`).toBeVisible(V)
      await calme(s.p)
      await expect(s.p.getByRole('switch', { name: /Inclure les éléments/ }), `${passe}interrupteur coché`).toHaveAttribute('aria-checked', 'true')
      const lead = tableau.getByTestId('corbeille-row').filter({ hasText: 'Lead anonymisé' })
      expect(await lead.count(), `${passe}« Lead anonymisé » listé (entrée restaurée et entrée active)`).toBeGreaterThanOrEqual(2)
      expect(await lead.getByText('Restauré', { exact: true }).count(), `${passe}l'entrée restaurée est bien listée`).toBeGreaterThanOrEqual(1)
      await expect(s.p.locator('body'), `${passe}écran : ni « ${nom} » ni sa marque`).not.toContainText(nom)
      await expect(s.p.locator('body'), `${passe}écran : pas la marque ${m}`).not.toContainText(m)
      expect(refus(s.reseau), `${passe}Corbeille : aucune réponse refusée`).toEqual([])
    }
    // API : `GET core/corbeille/` (journal d'annulation) ne contient pas le nom.
    const core = await x.get(`${API}/core/corbeille/`, T)
    const corps = await core.text()
    expect(core.status(), `GET core/corbeille/ : ${corps.slice(0, 200)}`).toBe(200)
    expect(corps, 'core/corbeille/ : sans le nom du lead').not.toContain(m)
    // Export xlsx de l'écran (mêmes filtres : éléments restaurés inclus) : sans le nom, avec le libellé neutre.
    const [telechargement] = await Promise.all([
      s.p.waitForEvent('download', T),
      s.p.getByRole('button', { name: 'Exporter le journal' }).click(),
    ])
    const chemin = await telechargement.path()
    const { readFile } = await import('node:fs/promises')
    const cellules = await cellulesDuClasseur(await readFile(chemin))
    expect(cellules.length, 'export xlsx : des cellules lues').toBeGreaterThan(0)
    expect(cellules.filter((c) => c.includes(m)), 'export xlsx : aucune cellule ne contient le nom ni la marque').toEqual([])
    expect(cellules.filter((c) => c === 'Lead anonymisé').length, 'export xlsx : « Lead anonymisé » listé').toBeGreaterThanOrEqual(2)
    // Persistance : relu en base, libellé neutre partout, l'entrée active reste restaurable.
    const base = await py(`from django.contrib.contenttypes.models import ContentType
from apps.crm.models import Lead
from apps.trash.models import ElementSupprime
from core.models import DeletionRecord
ct = ContentType.objects.get_for_model(Lead)
es = list(ElementSupprime.objects.filter(content_type=ct, object_id=${ids.lead}).values_list('libelle_snapshot', 'restaure_le'))
dr = list(DeletionRecord.objects.filter(content_type=ct, object_id=${ids.lead}).values_list('label', flat=True))
sortie(dict(es=[[a, b is not None] for a, b in es], dr=dr))`)
    expect(base.es.map((e) => e[0]), 'ElementSupprime du lead : libellé neutre').toEqual(base.es.map(() => 'Lead anonymisé'))
    expect(base.es.map((e) => e[1]).sort(), 'ElementSupprime : une restaurée, une active (restaurable)').toEqual([false, true])
    expect(base.dr.length, 'DeletionRecord du lead : présent').toBeGreaterThanOrEqual(2)
    expect(base.dr, 'DeletionRecord du lead : libellé neutre').toEqual(base.dr.map(() => 'Lead anonymisé'))
  } finally {
    await py(`from apps.crm.models import Client, Lead
from django.contrib.contenttypes.models import ContentType
from apps.trash.models import ElementSupprime
from core.models import DeletionRecord
ct = ContentType.objects.get_for_model(Lead)
ElementSupprime.objects.filter(content_type=ct, object_id=${ids.lead}).delete()
DeletionRecord.objects.filter(content_type=ct, object_id=${ids.lead}).delete()
Lead.all_objects.filter(pk=${ids.lead}).delete()
Client.objects.filter(pk=${ids.client}).delete()
sortie(1)`).catch(() => null)
  }
})
