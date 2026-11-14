// Preuve en direct du groupe AANA, lot 6 (relecture adverse du rejeu AANA81, constat C-AANA-VER5-001) : AANA91 —
// Paramètres › IA (`/parametres/ia`, écran réservé à l'administration) sous un compte au rôle SYSTÈME « Directeur »
// (registre, `init_roles`), connecté par le VRAI écran de connexion : les lignes `ventes_devis` et `ventes_lignedevis`
// de la liste des tables de l'agent SQL décrivent leurs colonnes réelles, sans aucun « montant ».
// La liste vient du VRAI service FastAPI (`GET /api/fastapi/sql-agent/schema` → `get_schema_summary()`), démarré sur
// le runner (uvicorn, 127.0.0.1:8001, même DJANGO_SECRET_KEY que Django : le jeton de la session est vérifié par le
// service). Le runner n'a pas de nginx devant les deux services : la requête de la page vers `/api/fastapi/…` est
// RELAYÉE telle quelle (cookies de la session compris) au service par `page.route` + `route.fetch`, sans rien changer
// à la réponse — l'écran affiche ce que le service sert. Aucun appel au fournisseur LLM (lecture de textes statiques).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AANA', ['AANA91'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const SERVICE_IA = process.env.E2E_FASTAPI_URL || 'http://localhost:8001'
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = (x) => JSON.stringify(x)
const SOC = `U.objects.get(username='demo_admin').company_id`
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })

etape('P.parametres_ia_colonnes_reelles', ['AANA91'], async ({ page, suivi, testInfo }) => {
  const nom = `aana91di_${marque()}`
  await py(`from apps.roles.models import Role
compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom='Directeur', est_systeme=True).pk, societe=${SOC})
sortie(1)`)
  await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  const p = suivi.surveiller(await ctx.newPage())
  // Relais de TOUT `/api/fastapi/…` vers le vrai service IA (même chemin, mêmes en-têtes, cookies de la session) ;
  // réponse inchangée (le rôle de nginx en production).
  const servies = []
  await p.route(/\/api\/fastapi\//, async (route) => {
    const q = route.request()
    const cible = new URL(q.url())
    const cookies = (await ctx.cookies(testInfo.project.use.baseURL)).map((c) => `${c.name}=${c.value}`).join('; ')
    const rep = await route.fetch({ url: `${SERVICE_IA}${cible.pathname}${cible.search}`, headers: { ...q.headers(), cookie: cookies } })
    if (/\/sql-agent\/schema$/.test(cible.pathname)) servies.push({ statut: rep.status(), corps: await rep.text() })
    await route.fulfill({ response: rep })
  })
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  const ligne = (table) => p.locator('li').filter({ has: p.getByText(table, { exact: true }) })
  for (const passe of ['', 'rechargé : ']) {
    if (passe) await p.reload()
    else await p.goto('/parametres/ia')
    await expect(p.getByRole('heading', { name: /Paramètres — IA/ }), `${passe}écran Paramètres › IA`).toBeVisible({ timeout: 60_000 })
    await expect(p.getByText(/Tables autorisées \(\d+\)/), `${passe}liste des tables servie par le service IA`).toBeVisible({ timeout: 60_000 })
    await expect(p.getByText('Diagnostic indisponible'), `${passe}aucun échec de lecture`).toHaveCount(0)
    const dernier = servies.at(-1)
    expect(dernier?.statut, `${passe}le service IA a répondu (${dernier?.corps?.slice(0, 200)})`).toBe(200)
    const schema = JSON.parse(dernier.corps)
    console.log(`[AANA91] ${passe}schema servi : provider=${schema.provider} model=${schema.model} tables=${schema.tables?.length} ; `
      + `ventes_devis=${J(schema.tables?.find((t) => t.table === 'ventes_devis'))} ; ventes_lignedevis=${J(schema.tables?.find((t) => t.table === 'ventes_lignedevis'))}`)
    const devis = ligne('ventes_devis')
    const lignes = ligne('ventes_lignedevis')
    await expect(devis, `${passe}ligne ventes_devis affichée`).toHaveCount(1)
    await expect(lignes, `${passe}ligne ventes_lignedevis affichée`).toHaveCount(1)
    for (const col of ['reference', 'date_creation', 'client', 'statut', 'envoye']) {
      await expect(devis, `${passe}ventes_devis cite « ${col} »`).toContainText(col)
    }
    for (const col of ['designation', 'quantite', 'prix_unitaire', 'remise', 'taux_tva']) {
      await expect(lignes, `${passe}ventes_lignedevis cite « ${col} »`).toContainText(col)
    }
    for (const [l, t] of [[devis, 'ventes_devis'], [lignes, 'ventes_lignedevis']]) {
      await expect(l, `${passe}${t} : aucun « montant »`).not.toContainText(/montant/i)
    }
    await expect(devis, `${passe}ventes_devis : plus de « numero »`).not.toContainText(/numero/i)
    // L'écran dit exactement ce que le service sert pour ces deux tables.
    for (const t of ['ventes_devis', 'ventes_lignedevis']) {
      const d = schema.tables.find((x) => x.table === t)?.description
      expect(d, `${passe}${t} : description servie`).toBeTruthy()
      await expect(ligne(t), `${passe}${t} : texte servi affiché tel quel`).toContainText(d)
    }
  }
})
