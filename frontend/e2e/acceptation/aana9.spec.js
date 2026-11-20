// Preuve en direct du groupe AANA, lot 9 : AANA92 (C-AANA-VER4-401) — Paramètres › IA (`/parametres/ia`, écran réservé à
// l'administration) sous un compte au rôle SYSTÈME « Directeur » (registre, `init_roles`), connecté par le VRAI écran de
// connexion : les lignes `ventes_facture` et `ventes_lignefacture` de la liste des tables de l'agent SQL décrivent leurs
// colonnes réelles (reference, date_emission, client, total_ht_stocke, total_ttc_stocke, statut ; designation, produit,
// quantite, prix_unitaire, remise, taux_tva), sans « numero » ni « montant » ; les quatre tables devis/factures ne citent que
// des champs de leur modèle (les deux lignes devis d'AANA91 sont réaffirmées). Même patron qu'aana6.spec.js : la liste vient du
// VRAI service FastAPI (`GET /api/fastapi/sql-agent/schema` → `get_schema_summary()`, uvicorn 127.0.0.1:8001 sur le runner), la
// requête de la page est RELAYÉE telle quelle par `page.route` + `route.fetch` (le rôle de nginx), la réponse n'est pas modifiée.
// Aucun appel au fournisseur LLM (textes statiques). Non prouvable ici : le classement mots-clés « combien de factures ce
// mois-ci » ⇒ `ventes_facture` (test unitaire du service, hors écran).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AANA', ['AANA92'])
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

etape('P.parametres_ia_colonnes_factures', ['AANA92'], async ({ page, suivi, testInfo }) => {
  const nom = `aana92di_${marque()}`
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
    console.log(`[AANA92] ${passe}schema servi : provider=${schema.provider} model=${schema.model} tables=${schema.tables?.length} ; `
      + `ventes_facture=${J(schema.tables?.find((t) => t.table === 'ventes_facture'))} ; ventes_lignefacture=${J(schema.tables?.find((t) => t.table === 'ventes_lignefacture'))}`)
    const devis = ligne('ventes_devis')
    const lignesDevis = ligne('ventes_lignedevis')
    const factures = ligne('ventes_facture')
    const lignes = ligne('ventes_lignefacture')
    for (const [l, t] of [[devis, 'ventes_devis'], [lignesDevis, 'ventes_lignedevis'], [factures, 'ventes_facture'], [lignes, 'ventes_lignefacture']]) {
      await expect(l, `${passe}ligne ${t} affichée`).toHaveCount(1)
      await expect(l, `${passe}${t} : aucun « montant »`).not.toContainText(/montant/i)
      await expect(l, `${passe}${t} : plus de « numero »`).not.toContainText(/numero/i)
    }
    for (const col of ['reference', 'date_emission', 'client', 'total_ht_stocke', 'total_ttc_stocke', 'statut']) {
      await expect(factures, `${passe}ventes_facture cite « ${col} »`).toContainText(col)
    }
    for (const col of ['designation', 'produit', 'quantite', 'prix_unitaire', 'remise', 'taux_tva']) {
      await expect(lignes, `${passe}ventes_lignefacture cite « ${col} »`).toContainText(col)
    }
    // AANA91 réaffirmé : les deux tables devis restent sur leurs colonnes réelles.
    for (const col of ['reference', 'date_creation', 'client', 'statut', 'envoye']) {
      await expect(devis, `${passe}ventes_devis cite « ${col} »`).toContainText(col)
    }
    for (const col of ['designation', 'quantite', 'prix_unitaire', 'remise', 'taux_tva']) {
      await expect(lignesDevis, `${passe}ventes_lignedevis cite « ${col} »`).toContainText(col)
    }
    // L'écran dit exactement ce que le service sert pour ces deux tables.
    for (const t of ['ventes_devis', 'ventes_lignedevis', 'ventes_facture', 'ventes_lignefacture']) {
      const d = schema.tables.find((x) => x.table === t)?.description
      expect(d, `${passe}${t} : description servie`).toBeTruthy()
      await expect(ligne(t), `${passe}${t} : texte servi affiché tel quel`).toContainText(d)
    }
  }
})
