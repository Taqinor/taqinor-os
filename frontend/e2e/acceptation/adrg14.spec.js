// Preuves en direct du groupe ADRG, lot 14 (acceptation du 17/11/2026, pile locale) : correctifs de la vague 9 du plan
// PLAN_AUDIT_CHANTIERS — ADRG148 (Suivi GPS sans lecture des utilisateurs assignables hors droit crm), ADRG149 (exports
// de /chantiers et /parc sous `installation_export`), ADRG150 (« Ouvrir un ticket » de la fiche chantier sous
// `sav_gerer`), ADRG151 (menu et routes /planification et /ma-journee sous `installation_voir`).
// Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo), connectés par la
// vraie route `/token/` dans un navigateur à part ; chaque réponse de l'API est relevée (« onglet réseau ») et chaque
// console.error de la page : les clauses « aucun appel X » et « sans 403 » sont affirmées sur ces relevés, en plus des
// oracles. Rendu seul : rien n'est écrit par les rôles (persistance n/a) — chaque écran est relu après rechargement.
// Données propres (API de demo_admin ou shell Django : un devis du Commercial et le chantier qui en découle), retirées en
// fin d'étape.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG148', 'ADRG149', 'ADRG150', 'ADRG151'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 480_000 })
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

/** Navigateur à part (aucun cookie de demo_admin) connecté par /token/ ; visites guidées marquées vues ; chaque
 *  réponse de l'API relevée dans `reseau` (« MÉTHODE chemin?requête → statut »), chaque console.error dans
 *  `consoles`. `stockage` : clés de localStorage posées avant tout script de la page. */
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
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
      for (const [k, val] of Object.entries(extra)) localStorage.setItem(k, val)
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
  const consoles = []
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  p.on('console', (msg) => { if (msg.type() === 'error') consoles.push(msg.text()) })
  p.on('pageerror', (e) => consoles.push(`pageerror : ${e.message}`))
  return { ctx, p, reseau, consoles, c }
}
const chemin = (l) => l.split(' ')[1].split('?')[0]
/** Lignes de `reseau` dont le chemin (sans requête) correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
/** Réponses refusées (4xx/5xx) relevées. */
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
const reponse = (p, re, methode = 'GET') => p.waitForResponse((r) => {
  const u = new URL(r.url())
  return re.test(u.pathname.slice(API.length)) && r.request().method() === methode
}, T)
/** Ouvre `url` (ou recharge) en vidant les relevés ; attend le calme. */
async function charger(s, url, passe) {
  s.reseau.length = 0
  s.consoles.length = 0
  if (passe) await s.p.reload(); else await s.p.goto(url)
  await calme(s.p)
}
const PASSES = ['', 'relu après rechargement : ']

/** Chantier de la société démo rattaché à un devis du compte `auteur` (c'est ce lien qui ouvre la lecture des chantiers
 *  à un Commercial par `ventes_voir`) ; `statut` posé. Renvoie {chantier, ref, devis}. */
async function chantierDe(r, m, tag, auteur, statut, technicien = null) {
  const prod = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau ${tag} ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `${tag} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${tag.toLowerCase()}${m}@example.invalid` } }), 'lead')
  const dv = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  const ids = await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
Devis.objects.filter(pk=${dv.id}).update(created_by_id=${auteur.id})
i = Installation.objects.create(company_id=${SOC}, reference='CHT-${tag}-${m}', statut=${J(statut)}, created_by_id=${auteur.id}, devis_id=${dv.id}${technicien ? `, technicien_responsable_id=${technicien.id}` : ''})
sortie(dict(chantier=i.pk, ref=i.reference))`)
  return { ...ids, devis: dv.id, produit: prod.id, lead: lead.id }
}
const nettoyerChantier = (o) => py(`from apps.installations.models import Installation
try:
    Installation.objects.filter(pk=${o.chantier}).delete()
except Exception:
    Installation.objects.filter(pk=${o.chantier}).update(annule=True)
sortie(1)`).catch(() => null)

// ── PF4-ADRG148-suivi-gps : /planification/suivi-gps sans `crm/assignable-users/` hors droit crm ───────────────────
const ASSIGNABLES = /^\/crm\/assignable-users\/$/
const ONGLETS_GPS = ['Consentements', 'Carte live', 'Alertes géofence', 'Historique de présence']
etape('PF4-ADRG148-suivi-gps', ['ADRG148'], async ({ page, suivi, testInfo }) => {
  const tr = await compteDe('Technicien responsable', 'adrg148tr')
  const di = await compteDe('Directeur', 'adrg148di')
  expect(tr.codes.some((c) => c.startsWith('crm_')), `Given : Technicien responsable sans code crm_* ${J(tr.codes.filter((c) => c.startsWith('crm_')))}`).toBe(false)
  expect(di.codes.some((c) => c.startsWith('crm_')), 'Given : Directeur avec un code crm_*').toBe(true)
  // Technicien responsable : les quatre onglets rendus, aucun GET crm/assignable-users/, aucune 403.
  const s = await ecranDe(page, suivi, testInfo, tr)
  for (const passe of PASSES) {
    await charger(s, '/planification/suivi-gps', passe)
    await expect(s.p.getByRole('heading', { name: 'Suivi GPS terrain' }), `${passe}Technicien responsable : écran Suivi GPS rendu`).toBeVisible(V)
    for (const o of ONGLETS_GPS) {
      await expect(s.p.getByRole('tab', { name: o }), `${passe}Technicien responsable : onglet « ${o} »`).toBeVisible(V)
    }
    await calme(s.p)
    console.log(`[ADRG148] ${passe}Technicien responsable suivi-gps → ${s.p.url()} : ${J(s.reseau)}`)
    expect(appels(s.reseau, ASSIGNABLES), `${passe}Technicien responsable : aucun GET crm/assignable-users/`).toEqual([])
    expect(refus(s.reseau), `${passe}Technicien responsable : aucune réponse refusée (aucune 403)`).toEqual([])
  }
  // Témoin Directeur : exactement un appel, 200 ; mêmes onglets.
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const lu = reponse(d.p, ASSIGNABLES)
    await charger(d, '/planification/suivi-gps', passe)
    expect((await lu).status(), `${passe}Directeur : utilisateurs assignables lus`).toBe(200)
    await expect(d.p.getByRole('heading', { name: 'Suivi GPS terrain' }), `${passe}Directeur : écran Suivi GPS rendu`).toBeVisible(V)
    for (const o of ONGLETS_GPS) {
      await expect(d.p.getByRole('tab', { name: o }), `${passe}Directeur : onglet « ${o} »`).toBeVisible(V)
    }
    await calme(d.p)
    const vus = appels(d.reseau, ASSIGNABLES)
    expect(vus, `${passe}Directeur : exactement un GET crm/assignable-users/ ${J(vus)}`).toHaveLength(1)
    expect(vus[0], `${passe}Directeur : appel en 200`).toMatch(/^GET .* → 200$/)
    expect(refus(d.reseau), `${passe}Directeur : aucune réponse refusée`).toEqual([])
  }
})

// ── PF4-ADRG149-exports-chantiers : « Exporter » de /chantiers (vue liste) et /parc sous `installation_export` ────
etape('PF4-ADRG149-exports-chantiers', ['ADRG149'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const cr = await compteDe('Commercial responsable', 'adrg149cr')
  const di = await compteDe('Directeur', 'adrg149di')
  expect(cr.codes.includes('installation_export'), 'Given : Commercial responsable sans installation_export').toBe(false)
  expect(di.codes.includes('installation_export'), 'Given : Directeur avec installation_export').toBe(true)
  // Chantier « réceptionné » (dans le parc), rattaché à un devis du Commercial responsable : visible aux deux écrans.
  const o = await chantierDe(page.request, m, 'ADRG149', cr, 'receptionne')
  const stockage = { 'taqinor.chantiers.view': 'liste' }
  try {
    const exporterTableau = (p) => p.getByRole('button', { name: 'Exporter', exact: true })
    const exporterExcel = (p) => p.getByRole('button', { name: /Exporter Excel/ })
    const s = await ecranDe(page, suivi, testInfo, cr, stockage)
    for (const passe of PASSES) {
      await charger(s, '/chantiers', passe)
      await expect(s.p.getByRole('row').filter({ hasText: o.ref }).first(), `${passe}Commercial responsable /chantiers : chantier listé (tableau rendu, vue liste)`).toBeVisible(V)
      await calme(s.p)
      await expect(exporterTableau(s.p), `${passe}Commercial responsable /chantiers : aucun « Exporter » du tableau`).toHaveCount(0)
      await expect(exporterExcel(s.p), `${passe}Commercial responsable /chantiers : aucun « Exporter Excel »`).toHaveCount(0)
      console.log(`[ADRG149] ${passe}Commercial responsable /chantiers : ${J(s.reseau)}`)
      expect(refus(s.reseau), `${passe}Commercial responsable /chantiers : aucune réponse refusée (aucune 403)`).toEqual([])
    }
    for (const passe of PASSES) {
      await charger(s, '/parc', passe)
      await expect(s.p.getByRole('row').filter({ hasText: o.ref }).first(), `${passe}Commercial responsable /parc : chantier listé (tableau rendu)`).toBeVisible(V)
      await calme(s.p)
      await expect(exporterExcel(s.p), `${passe}Commercial responsable /parc : aucun « Exporter Excel »`).toHaveCount(0)
      await expect(exporterTableau(s.p), `${passe}Commercial responsable /parc : aucun « Exporter » du tableau`).toHaveCount(0)
      console.log(`[ADRG149] ${passe}Commercial responsable /parc : ${J(s.reseau)}`)
      expect(refus(s.reseau), `${passe}Commercial responsable /parc : aucune réponse refusée (aucune 403)`).toEqual([])
    }
    // Témoin Directeur : les trois boutons.
    const d = await ecranDe(page, suivi, testInfo, di, stockage)
    for (const passe of PASSES) {
      await charger(d, '/chantiers', passe)
      await expect(d.p.getByRole('row').filter({ hasText: o.ref }).first(), `${passe}Directeur /chantiers : chantier listé`).toBeVisible(V)
      await expect(exporterTableau(d.p), `${passe}Directeur /chantiers : « Exporter » du tableau`).toBeVisible(V)
      await expect(exporterExcel(d.p).first(), `${passe}Directeur /chantiers : « Exporter Excel »`).toBeVisible(V)
      expect(refus(d.reseau), `${passe}Directeur /chantiers : aucune réponse refusée`).toEqual([])
    }
    for (const passe of PASSES) {
      await charger(d, '/parc', passe)
      await expect(d.p.getByRole('row').filter({ hasText: o.ref }).first(), `${passe}Directeur /parc : chantier listé`).toBeVisible(V)
      await expect(exporterExcel(d.p).first(), `${passe}Directeur /parc : « Exporter Excel »`).toBeVisible(V)
      await expect(exporterTableau(d.p), `${passe}Directeur /parc : « Exporter » du tableau`).toBeVisible(V)
      expect(refus(d.reseau), `${passe}Directeur /parc : aucune réponse refusée`).toEqual([])
    }
  } finally {
    await nettoyerChantier(o)
  }
})

// ── PF4-ADRG150-ticket-fiche-chantier : « Ouvrir un ticket » de la fiche chantier sous `sav_gerer` ─────────────────
etape('PF4-ADRG150-ticket-fiche-chantier', ['ADRG150'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteDe('Commercial', 'adrg150co')
  const tr = await compteDe('Technicien responsable', 'adrg150tr')
  expect([co.codes.includes('ventes_voir'), co.codes.includes('sav_gerer')], 'Given : Commercial ventes_voir sans sav_gerer').toEqual([true, false])
  expect(tr.codes.includes('sav_gerer'), 'Given : Technicien responsable avec sav_gerer').toBe(true)
  // Chantier sans ticket, du devis du Commercial (lecture par `ventes_voir`), titulaire = Technicien responsable.
  const o = await chantierDe(page.request, m, 'ADRG150', co, 'installe', tr)
  try {
    /** Fiche chantier ouverte depuis /chantiers, onglet « Interventions », section « Tickets SAV » rendue. */
    async function sectionTickets(s, passe) {
      await charger(s, `/chantiers?id=${o.chantier}`, passe)
      const fiche = s.p.getByRole('dialog')
      await expect(fiche.getByText(`Chantier — ${o.ref}`).first(), `${passe}${s.c.nomRole} : fiche ouverte`).toBeVisible(V)
      await fiche.getByRole('tab', { name: 'Interventions' }).click()
      await expect(fiche.getByText('Tickets SAV', { exact: true }).first(), `${passe}${s.c.nomRole} : section « Tickets SAV » affichée`).toBeVisible(V)
      await expect(fiche.getByText('Aucun ticket SAV sur ce chantier.'), `${passe}${s.c.nomRole} : liste des tickets (aucun ticket)`).toBeVisible(V)
      await expect(fiche.getByText(/Le suivi détaillé \(interventions, historique\) se fait dans l.écran « Tickets SAV »/), `${passe}${s.c.nomRole} : renvoi vers l'écran « Tickets SAV »`).toBeVisible(V)
      await calme(s.p)
      return fiche
    }
    // Commercial : ni formulaire (Type / Équipement concerné / Description) ni « Ouvrir un ticket ».
    const c = await ecranDe(page, suivi, testInfo, co)
    for (const passe of PASSES) {
      const fiche = await sectionTickets(c, passe)
      await expect(fiche.getByRole('button', { name: 'Ouvrir un ticket' }), `${passe}Commercial : pas de « Ouvrir un ticket »`).toHaveCount(0)
      await expect(fiche.getByText('Équipement concerné', { exact: true }), `${passe}Commercial : pas de champ « Équipement concerné »`).toHaveCount(0)
      await expect(fiche.locator('#tk-type'), `${passe}Commercial : pas de champ « Type » du ticket`).toHaveCount(0)
      await expect(fiche.getByPlaceholder('Symptôme / demande'), `${passe}Commercial : pas de champ « Description » du ticket`).toHaveCount(0)
      console.log(`[ADRG150] ${passe}Commercial fiche ${o.ref} : ${J(c.reseau)} ; console ${J(c.consoles)}`)
    }
    // Témoin Technicien responsable : le formulaire et le bouton.
    const t = await ecranDe(page, suivi, testInfo, tr)
    for (const passe of PASSES) {
      const fiche = await sectionTickets(t, passe)
      await expect(fiche.getByRole('button', { name: 'Ouvrir un ticket' }), `${passe}Technicien responsable : « Ouvrir un ticket »`).toBeVisible(V)
      await expect(fiche.getByText('Équipement concerné', { exact: true }), `${passe}Technicien responsable : champ « Équipement concerné »`).toBeVisible(V)
      await expect(fiche.locator('#tk-type'), `${passe}Technicien responsable : champ « Type » du ticket`).toBeVisible(V)
      await expect(fiche.getByPlaceholder('Symptôme / demande'), `${passe}Technicien responsable : champ « Description » du ticket`).toBeVisible(V)
      expect(refus(t.reseau), `${passe}Technicien responsable : aucune réponse refusée`).toEqual([])
    }
  } finally {
    await nettoyerChantier(o)
  }
})

// ── PF4-ADRG151-planification-ma-journee : menu et routes /planification et /ma-journee sous `installation_voir` ───
const CALENDRIER = /^\/installations\/interventions\/calendrier\/$/
const TOURNEE = /^\/installations\/interventions\/ma-tournee\/$/
const CHARGE = /^\/installations\/interventions\/plan-de-charge\/$/
etape('PF4-ADRG151-planification-ma-journee', ['ADRG151'], async ({ page, suivi, testInfo }) => {
  const cr = await compteDe('Commercial responsable', 'adrg151cr')
  const tr = await compteDe('Technicien responsable', 'adrg151tr')
  expect(cr.codes.includes('installation_voir'), `Given : Commercial responsable sans installation_voir ${J(cr.codes.filter((x) => x.startsWith('installation')))}`).toBe(false)
  expect(tr.codes.includes('installation_voir'), 'Given : Technicien responsable avec installation_voir').toBe(true)
  const lectures = (reseau) => [...appels(reseau, CALENDRIER), ...appels(reseau, TOURNEE), ...appels(reseau, CHARGE)]
  // Commercial responsable : menu de l'app Chantiers sans « Planification » ni « Ma journée » ; ouverture directe des
  // deux routes sans aucune lecture ni 403.
  const s = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of PASSES) {
    await charger(s, '/chantiers', passe)
    const nav = s.p.getByRole('navigation', { name: /^Navigation / })
    await expect(nav.getByRole('link', { name: 'Chantiers', exact: true }), `${passe}Commercial responsable : menu de l'app Chantiers rendu`).toBeVisible(V)
    await calme(s.p)
    await expect(nav.getByRole('link', { name: 'Planification', exact: true }), `${passe}Commercial responsable : aucune entrée « Planification »`).toHaveCount(0)
    await expect(nav.getByRole('link', { name: 'Ma journée', exact: true }), `${passe}Commercial responsable : aucune entrée « Ma journée »`).toHaveCount(0)
    await expect(s.p.locator('a[href="/planification"], a[href="/ma-journee"]'), `${passe}Commercial responsable : aucun lien /planification ni /ma-journee`).toHaveCount(0)
  }
  for (const route of ['/planification', '/ma-journee']) {
    for (const passe of PASSES) {
      await charger(s, route, passe)
      await calme(s.p)
      const corps = ((await s.p.locator('body').innerText()).replace(/\s+/g, ' ')).slice(0, 300)
      console.log(`[ADRG151] ${passe}Commercial responsable ${route} → ${s.p.url()} : « ${corps} » ; ${J(s.reseau)}`)
      expect(lectures(s.reseau), `${passe}Commercial responsable ${route} : aucune lecture calendrier / ma-tournee / plan-de-charge`).toEqual([])
      expect(refus(s.reseau), `${passe}Commercial responsable ${route} : aucune réponse refusée (aucune 403)`).toEqual([])
      await expect(s.p.getByText('Accès refusé (403)').first(), `${passe}Commercial responsable ${route} : le routeur affiche l'écran de refus`).toBeVisible(V)
    }
  }
  // Témoin Technicien responsable : les deux entrées de menu, calendrier et tournée chargés (200).
  const t = await ecranDe(page, suivi, testInfo, tr)
  for (const passe of PASSES) {
    await charger(t, '/chantiers', passe)
    const nav = t.p.getByRole('navigation', { name: /^Navigation / })
    await expect(nav.getByRole('link', { name: 'Chantiers', exact: true }), `${passe}Technicien responsable : menu de l'app Chantiers rendu`).toBeVisible(V)
    await expect(nav.getByRole('link', { name: 'Planification', exact: true }), `${passe}Technicien responsable : entrée « Planification »`).toBeVisible(V)
    await expect(nav.getByRole('link', { name: 'Ma journée', exact: true }), `${passe}Technicien responsable : entrée « Ma journée »`).toBeVisible(V)
  }
  for (const passe of PASSES) {
    const cal = reponse(t.p, CALENDRIER)
    await charger(t, '/planification', passe)
    expect((await cal).status(), `${passe}Technicien responsable /planification : calendrier lu`).toBe(200)
    await expect(t.p.getByText('Accès refusé (403)'), `${passe}Technicien responsable /planification : pas d'écran de refus`).toHaveCount(0)
    expect(refus(t.reseau), `${passe}Technicien responsable /planification : aucune réponse refusée`).toEqual([])
  }
  for (const passe of PASSES) {
    const tour = reponse(t.p, TOURNEE)
    await charger(t, '/ma-journee', passe)
    expect((await tour).status(), `${passe}Technicien responsable /ma-journee : tournée lue`).toBe(200)
    await expect(t.p.getByText('Accès refusé (403)'), `${passe}Technicien responsable /ma-journee : pas d'écran de refus`).toHaveCount(0)
    expect(refus(t.reseau), `${passe}Technicien responsable /ma-journee : aucune réponse refusée`).toEqual([])
  }
})
