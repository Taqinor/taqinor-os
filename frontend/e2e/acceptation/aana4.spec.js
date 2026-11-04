// AANA60 — preuve en direct sur la pile locale : l'accueil lit les chiffres SERVIS. Compte commercial démo (rôle
// « Commercial », créé pour l'essai) : « Mes chiffres » = Quote-to-cash `?month=<courant>&mine=1`, la carte CA mensuel
// dit « Accès réservé… » quand /reporting/dashboard/ répond 403. Compte directeur (demo_admin, rôle Directeur) :
// la conversion devis → signé = `devis.taux_acceptation_pct` servi et le CA du mois de l'accueil = `ca_mensuel` de
// /reporting/dashboard/, comme l'écran /reporting.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout, MDP_ESSAI } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('AANA', ['AANA60'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })
const API = '/api/django'
const T = { timeout: 120_000 }
const plat = (s) => String(s).replace(/[\s\u00a0\u202f]+/g, '')
const pct = (v) => `${Math.round(Number(v))}`
const moisCourant = () => new Date().toISOString().slice(0, 7)

// Écart accepté (base FAIL) pour les rôles hors direction : la carte « Badge SLA » de l'accueil (NTOBS21,
// `features/reporting/SlaBadgeCard.jsx` via `parametresApi.getReliabilitySettings`) appelle
// `/core/fiabilite/reglages/`, réservé à `fiabilite_voir` → 403 + `console.error` (oracles 2-3) ; hors AANA60.
const ECART_SLA = { base: 'FAIL', raison: "SlaBadgeCard (NTOBS21, frontend/src/features/reporting/SlaBadgeCard.jsx) appelle GET /api/django/core/fiabilite/reglages/ pour tout rôle à l'accueil : 403 + console.error pour un rôle sans fiabilite_voir — défaut de NTOBS21, hors AANA60 ; avant AANA60 la même étape échouait déjà (chiffres recalculés localement)" }

/** Ouvre l'accueil sous un compte d'essai du rôle `nomRole` (société de demo_admin), rend {page, ctx, q2c, reporting}. */
async function accueilSous(pageAdmin, suivi, testInfo, username, nomRole) {
  await py(`a = U.objects.get(username='demo_admin')
from apps.roles.models import Role
r = Role.objects.get(company_id=a.company_id, nom='${nomRole}')
c = compte('${username}', role=r.pk, societe=a.company_id)
sortie(dict(id=c.id))`)
  const ctx = await pageAdmin.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  const page = suivi.surveiller(await ctx.newPage())
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await uiLoginJusquAuxApps(page, { username, password: MDP_ESSAI })
  const mine = page.waitForResponse((x) => /\/ventes\/dashboard\//.test(x.url()) && /mine=1/.test(x.url()), { timeout: 60_000 }).catch(() => null)
  const rep = page.waitForResponse((x) => /\/reporting\/dashboard\/?$/.test(new URL(x.url()).pathname), { timeout: 60_000 })
  await page.goto('/dashboard')
  const r = await rep
  const m = await mine
  return { page, ctx, q2c: m ? await m.json() : null, mineUrl: m ? m.url() : null, reporting: r.status() === 200 ? await r.json() : null, statutReporting: r.status() }
}
const desactiver = (u) => py(`U.objects.filter(username='${u}').update(is_active=False)
sortie(1)`).catch(() => null)

etape('P.commercial_mes_chiffres', ['AANA60'], async ({ page: pageAdmin, suivi, testInfo }) => {
  // Deux devis du mois au nom du commercial (posés par l'API admin, auteur réattribué) : un envoyé, un accepté.
  const r = pageAdmin.request
  await assurerSessionPage(pageAdmin)
  const devisIds = []
  for (const accepter of [false, true]) {
    const m = `${Date.now().toString(36)}${accepter ? 'a' : 'e'}`
    const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AANA60 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
    const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau AANA60 ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
    const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
    await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
    if (accepter) await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AANA60' } }), 'accepter')
    devisIds.push(d.id)
  }
  await py(`a = U.objects.get(username='demo_admin')
from apps.roles.models import Role
from apps.ventes.models import Devis
c = compte('aana60_commercial', role=Role.objects.get(company_id=a.company_id, nom='Commercial').pk, societe=a.company_id)
Devis.objects.filter(pk__in=${JSON.stringify(devisIds)}).update(created_by=c)
sortie(1)`)
  const x = await accueilSous(pageAdmin, suivi, testInfo, 'aana60_commercial', 'Commercial')
  try {
    const { page, q2c } = x
    expect(q2c, 'Quote-to-cash `mine=1` demandé').toBeTruthy()
    expect(new URL(x.mineUrl).searchParams.get('month')).toBe(moisCourant())
    expect(q2c.devis.envoyes_periode, `effectifs servis du vendeur (${JSON.stringify(q2c.devis)})`).toBeGreaterThan(0)
    const carte = page.getByTestId('mes-chiffres-card')
    await expect(carte).toBeVisible({ timeout: 60_000 })
    const texte = plat(await carte.innerText()).toLowerCase()
    expect(texte, `taux servi ${q2c.devis.taux_acceptation_pct}`).toContain(`tauxdesignature${pct(q2c.devis.taux_acceptation_pct)}`)
    expect(texte).toContain(`devisenvoyés${q2c.devis.envoyes_periode}`)
    expect(texte).toContain(`devisacceptés${q2c.devis.acceptes_periode}`)
    // Persistance : rechargement ⇒ mêmes chiffres.
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page.getByTestId('mes-chiffres-card')).toBeVisible({ timeout: 60_000 })
    expect(plat(await page.getByTestId('mes-chiffres-card').innerText()).toLowerCase()).toBe(texte)
  } finally {
    await x.ctx.close()
    for (const id of devisIds) await r.patch(`${API}/ventes/devis/${id}/`, { ...T, data: { is_active: false } }).catch(() => null)
    await desactiver('aana60_commercial')
  }
}, { ecart: ECART_SLA })

etape('P.role_refuse_acces_reserve', ['AANA60'], async ({ page: pageAdmin, suivi, testInfo }) => {
  suivi.attendre(/\/reporting\/dashboard\/?$/, 403)
  const x = await accueilSous(pageAdmin, suivi, testInfo, 'aana60_lecteur', 'Viewer')
  try {
    expect(x.statutReporting, 'rôle hors direction : /reporting/dashboard/ refusé').toBe(403)
    await expect(x.page.getByText("Accès réservé : chiffre d'affaires visible par la direction.")).toBeVisible({ timeout: 60_000 })
    await expect(x.page.getByText(/Paiements reçus HT · [1-9]/)).toHaveCount(0)
  } finally {
    await x.ctx.close()
    await desactiver('aana60_lecteur')
  }
}, { ecart: { base: 'FAIL', raison: `${ECART_SLA.raison} ; pour le rôle Viewer, deux autres cartes de l'accueil appellent aussi des routes que ce rôle ne lit pas : components/layout/ImpactPastille.jsx (GET /monitoring/configs/co2-fleet/ → 403) et components/MesEquipesCard.jsx (GET /crm/equipes/statistiques/ → 403) — hors AANA60` } })

etape('P.directeur_taux_ca', ['AANA60'], async ({ page }) => {
  await assurerSessionPage(page)
  const qrep = page.waitForResponse((x) => /\/ventes\/dashboard\/?$/.test(new URL(x.url()).pathname) && !/mine=1/.test(x.url()), { timeout: 60_000 })
  const rrep = page.waitForResponse((x) => /\/reporting\/dashboard\/?$/.test(new URL(x.url()).pathname), { timeout: 60_000 })
  await page.goto('/dashboard')
  const q2c = await (await qrep).json()
  const r = await rrep
  expect(r.status(), 'directeur : /reporting/dashboard/ servi').toBe(200)
  const reporting = await r.json()
  const mois = (reporting.ca_mensuel || []).slice(-6)
  // Conversion devis → signé : taux et effectifs servis.
  const conv = page.getByText(/signés sur .* devis émis/).first()
  if ((q2c.devis?.envoyes_periode ?? 0) > 0) {
    await expect(conv, 'carte conversion').toBeVisible({ timeout: 60_000 })
    expect(plat(await conv.innerText())).toContain(`${q2c.devis.acceptes_periode}signéssur${q2c.devis.envoyes_periode}devisémis`)
  }
  // CA mensuel de l'accueil = série servie (6 derniers mois) ; la description porte la somme servie.
  const total = mois.reduce((s, m) => s + Number(m.ca || 0), 0)
  const carteCa = page.getByText(/Paiements reçus HT · .* sur 6 mois/).first()
  await expect(carteCa).toBeVisible({ timeout: 60_000 })
  const fmt = String(Math.round(total)).replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  expect(plat(await carteCa.innerText()), `CA servi sur 6 mois = ${total}`).toContain(plat(fmt))
  // /reporting relu par l'API : même série, même taux (aucun calcul local).
  const relu = await (await page.request.get(`${API}/reporting/dashboard/`, { timeout: 60_000 })).json()
  expect(relu.ca_mensuel).toEqual(reporting.ca_mensuel)
  await page.goto('/reporting')
  await expect(page.locator('body')).toBeVisible()
})

// ERR-ACC-ACCUEIL-403-LECTEUR — preuve en direct sur la pile locale : l'accueil du rôle Lecteur (Viewer) ne monte
// plus `MesEquipesCard` (GET /crm/equipes/statistiques/) ni `ImpactPastille` (GET /monitoring/configs/co2-fleet/) :
// aucune de ces deux requêtes, aucun toast d'erreur global. Compte d'essai du rôle « Viewer » de la société de
// demo_admin (jamais `company_id` codé en dur), désactivé en fin d'étape. Contre-épreuve : demo_admin (direction)
// lit toujours les deux cartes.

const etapeErrAcc = groupe('AANA', ['ERR-ACC-ACCUEIL-403-LECTEUR'])
const INTERDITES = [/\/monitoring\/configs\/co2-fleet\/?/, /\/crm\/equipes\/statistiques\/?/]
// Écart accepté (base FAIL : la même étape échouait déjà avant la correction, avec en plus les deux lectures visées) :
// deux AUTRES cartes de l'accueil répondent encore 403 au Lecteur — hors ERR-ACC-ACCUEIL-403-LECTEUR.
const ECART = { base: 'FAIL', raison: "deux autres lectures de l'accueil restent refusées au Lecteur, hors de cette correction : GET /reporting/dashboard/ → 403 (carte CA « Accès réservé : chiffre d'affaires visible par la direction. », comportement voulu d'AANA60) et GET /core/fiabilite/reglages/ → 403 + console.error (SlaBadgeCard, NTOBS21 : sans toast depuis 36c72d4809 mais l'appel part encore) ; les deux lectures visées (co2-fleet, equipes/statistiques) ne partent plus et aucun toast d'erreur" }
const TOAST = '[data-sonner-toast][data-type="error"], [role="status"] .toast-error, .Toastify__toast--error'

etapeErrAcc('P.lecteur_accueil_sans_403', ['ERR-ACC-ACCUEIL-403-LECTEUR'], async ({ page: pageAdmin, suivi, testInfo }) => {
  await py(`a = U.objects.get(username='demo_admin')
from apps.roles.models import Role
r = Role.objects.get(company_id=a.company_id, nom='Viewer')
c = compte('erracc_lecteur', role=r.pk, societe=a.company_id)
sortie(dict(id=c.id))`)
  const ctx = await pageAdmin.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  try {
    const page = suivi.surveiller(await ctx.newPage())
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    const vues = []
    page.on('request', (q) => { if (INTERDITES.some((re) => re.test(q.url()))) vues.push(q.url()) })
    await uiLoginJusquAuxApps(page, { username: 'erracc_lecteur', password: MDP_ESSAI })
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    await expect(page.locator('main').first()).toBeVisible({ timeout: 60_000 })
    expect(vues, `accueil Lecteur : aucune lecture interdite (${vues.join(', ')})`).toEqual([])
    await expect(page.locator(TOAST), 'aucun toast d\'erreur global').toHaveCount(0)
    // Persistance : rechargement ⇒ toujours aucune des deux lectures.
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    await expect(page.locator('main').first()).toBeVisible({ timeout: 60_000 })
    expect(vues, 'après rechargement').toEqual([])
    await expect(page.locator(TOAST)).toHaveCount(0)
    // L'accueil est bien rendu (carte CA du Lecteur, AANA60) — la capture de l'étape est cette page (contexte laissé ouvert).
    await expect(page.getByText("Accès réservé : chiffre d'affaires visible par la direction.")).toBeVisible({ timeout: 60_000 })
    await pageAdmin.close() // la capture de l'étape prend la première page ouverte : celle du Lecteur
  } finally {
    await py(`U.objects.filter(username='erracc_lecteur').update(is_active=False)
sortie(1)`).catch(() => null)
  }
}, { ecart: ECART })

etapeErrAcc('P.direction_garde_les_cartes', ['ERR-ACC-ACCUEIL-403-LECTEUR'], async ({ page }) => {
  await assurerSessionPage(page)
  const equipes = page.waitForResponse((x) => /\/crm\/equipes\/statistiques\/?/.test(x.url()), { timeout: 60_000 })
  const co2 = page.waitForResponse((x) => /\/monitoring\/configs\/co2-fleet\/?/.test(x.url()), { timeout: 60_000 })
  await page.goto('/dashboard')
  expect((await equipes).status(), 'direction : statistiques d\'équipes lues').toBe(200)
  expect((await co2).status(), 'direction : pastille d\'impact lue').toBe(200)
})
