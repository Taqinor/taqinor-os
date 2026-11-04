// ALEA62, ALEA63 — rejeu en direct : étape déplacée pendant le rechargement (réseau lent simulé par la route Playwright),
// « Devis auto » bloqué partout quand le catalogue C&I n'est pas prêt (société d'essai sans article de prestation).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ALEA', ['ALEA62', 'ALEA63'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

etape('P.fetch_perime', ['ALEA62'], async ({ page, suivi }) => {
  const r = page.request
  const nom = `ALEA62 ${marque()}`
  const l = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid` } }), 'lead')
  await page.goto(`/crm/leads?view=kanban&q=${encodeURIComponent(nom)}`)
  const carte = page.locator(`[data-lead-id="${l.id}"]`)
  await expect(carte).toBeVisible({ timeout: 60_000 })
  // Réseau lent : le fetch lancé par la bascule répond APRÈS le PATCH, avec une liste lue AVANT (X encore en NEW).
  let libererFetch
  const patchFini = new Promise((res) => { libererFetch = res })
  let fetchTenu = 0
  let corpsPerime = false
  let patchEstFini = false
  await page.route((u) => u.pathname === `${API}/crm/leads/`, async (route) => {
    if (route.request().method() !== 'GET' || patchEstFini) { await route.fallback(); return }
    try {
      const rep = await route.fetch()
      fetchTenu += 1
      const texte = await rep.text()
      corpsPerime ||= new RegExp(`"id":${l.id},`).test(texte) && /"stage":"NEW"/.test(texte)
      await patchFini
      await route.fulfill({ response: rep, body: texte })
    } catch { /* page fermée : plus rien à rendre */ }
  })
  await page.getByRole('button', { name: /^Filtres/ }).first().click()
  await page.locator('[aria-label="Filtre leads archivés"]').getByText('Tous', { exact: true }).click()
  await page.keyboard.press('Escape')
  await expect.poll(() => fetchTenu, { timeout: 30_000 }).toBeGreaterThan(0)
  const a = await carte.boundingBox()
  const colonne = page.locator('[aria-label^="Étape Contacté"]').first()
  const b = await colonne.boundingBox()
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(a.x + a.width / 2 + 15, a.y + a.height / 2 + 5, { steps: 4 })
  await page.mouse.move(b.x + b.width / 2, b.y + 60, { steps: 12 })
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.url().includes(`/crm/leads/${l.id}/`) && x.request().method() === 'PATCH', T),
    page.mouse.up(),
  ])
  expect(rep.status(), 'PATCH réussi').toBe(200)
  patchEstFini = true
  const stale = page.waitForResponse((x) => new URL(x.url()).pathname === `${API}/crm/leads/` && x.request().method() === 'GET', { timeout: 30_000 })
  libererFetch()
  await stale
  expect(corpsPerime, 'le fetch tenu rend bien X en NEW').toBe(true)
  await expect(colonne.locator(`[data-lead-id="${l.id}"]`), 'X garde sa colonne').toBeVisible({ timeout: 30_000 })
  await expect(page.locator('[aria-label^="Étape Nouveau"]').first().locator(`[data-lead-id="${l.id}"]`), 'jamais retombé en NEW').toHaveCount(0)
  await page.unrouteAll({ behavior: 'ignoreErrors' })
  suivi.verifie(5)
})

etape('PA1.08.catalogue_ci_partout', ['ALEA63'], async ({ page, testInfo, suivi }) => {
  const nom = 'alea63_admin'
  const m = marque()
  const ids = await py(`from decimal import Decimal
from django.core.cache import cache
from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.moteur_ci.composition import PRESTATIONS_CI
from authentication.models import Company
co, _ = Company.objects.get_or_create(slug='alea63-essai', defaults=dict(nom='ALEA63 Essai', est_demo=True))
Produit.objects.filter(company=co).delete()
u, _ = U.objects.get_or_create(username='${nom}', defaults=dict(company=co, role_legacy='admin'))
u.company = co; u.role_legacy = 'admin'; u.is_active = True; u.must_change_password = False; u.failed_login_count = 0; u.locked_until = None; u.set_password('${MDP_ESSAI}'); u.save()
l = Lead.objects.create(company=co, nom='ALEA63 ${m}', prenom='Essai', ville='Casablanca', telephone='${telephoneMobileUnique()}', type_installation='commercial', categorie_commerciale='bureau', conso_mensuelle_kwh=Decimal('10000'), contrat_electricite='bt_patente', raccordement='triphase', jours_ouverture=[1, 2, 3, 4, 5], heure_debut=8, heure_fin=18, owner=u)
cache.delete('ventes:catalogue_ci_pret:%s' % co.id)
sortie(dict(lead=l.id, co=co.id))`)
  const ctx = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, serviceWorkers: 'block' })
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1'); localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  })
  await expect(async () => {
    const r = await ctx.request.post(`${API}/token/`, { data: { username: nom, password: MDP_ESSAI } })
    expect(r.status(), `connexion de ${nom}`).toBe(200)
  }).toPass({ intervals: [10_000, 20_000, 30_000], timeout: 240_000 })
  // API : la ligne de liste ET la réponse du PATCH servent le blocage.
  const liste = listeDe(await lireJson(await ctx.request.get(`${API}/crm/leads/`, T), 'liste'))
  const ligne = liste.find((x) => x.id === ids.lead)
  expect(ligne?.devis_auto?.catalogue_ci?.pret, 'liste : catalogue non prêt').toBe(false)
  const patch = await lireJson(await ctx.request.patch(`${API}/crm/leads/${ids.lead}/`, { ...T, data: { prenom: 'Essai2' } }), 'PATCH')
  expect(patch.devis_auto?.catalogue_ci?.pret, 'réponse du PATCH : catalogue non prêt').toBe(false)
  const p = suivi.surveiller(await ctx.newPage())
  const nomLead = `ALEA63 ${m}`
  for (const vue of ['kanban', 'liste']) {
    await p.goto(`/crm/leads?view=${vue}&q=${encodeURIComponent(nomLead)}`)
    const carte = vue === 'kanban' ? p.locator(`[data-lead-id="${ids.lead}"]`) : p.locator('tr', { hasText: nomLead }).first()
    await expect(carte, `${vue} : le lead`).toBeVisible({ timeout: 60_000 })
    await carte.hover()
    const bouton = carte.locator('button:disabled[title*="catalogue" i], button[disabled][title*="poste" i], [aria-disabled="true"][title]').first()
    await expect(bouton, `${vue} : « Devis auto » désactivé, motif nommé`).toBeVisible({ timeout: 15_000 })
    expect(await bouton.getAttribute('title'), `${vue} : titre`).toMatch(/poste|catalogue/i)
  }
  // Fiche après autosave.
  await p.goto(`/crm/leads/${ids.lead}`)
  await p.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click({ timeout: 60_000 })
  await expect(p.getByTestId('lw-devis-auto-bloque'), 'fiche : bloqué').toBeDisabled({ timeout: 60_000 })
  // Persistance : relire liste et fiche ⇒ même blocage.
  expect((await lireJson(await ctx.request.get(`${API}/crm/leads/${ids.lead}/`, T), 'fiche')).devis_auto?.catalogue_ci?.pret).toBe(false)
  await ctx.close()
  await py(`U.objects.filter(username='${nom}').update(is_active=False); sortie(1)`)
})
