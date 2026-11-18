// Preuves en direct du groupe ALEC, lot 11 (17/11/2026) : ALEC55 (compteurs et taux d'acceptation de la période des
// deux tableaux de bord bornés à la portée du rôle) et ALEC56 (montants du tableau « Mes équipes » masqués hors
// portée). Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo) :
// deux « Commercial » (A, B) et un « Directeur ». Connexion par la vraie route `/token/` dans un navigateur à part ;
// chaque réponse de l'API est relevée (« onglet réseau ») et chaque `console.error` de la page. Les données sont
// créées par l'API de chaque compte (devis, lead) puis posées « envoyé » / « accepté » par le shell Django (aucune
// route d'envoi sans effet de bord WhatsApp), et retirées en fin d'étape ; chaque écran est relu après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ALEC', ['ALEC55', 'ALEC56'])
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

/** Compte d'essai : rôle SYSTÈME `nomRole` ; {username, id, nomRole, codes} (codes du rôle relus en base). */
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
 *  réponse de l'API relevée dans `reseau` (« MÉTHODE chemin?requête → statut »), chaque console.error dans
 *  `consoles`. La page demo_admin de l'étape est refermée : la capture montre l'écran du rôle joué. */
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
/** Réponses refusées (4xx/5xx) relevées. */
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
/** Attend une réponse (chemin relatif à l'API = `re`, `filtre(url)` en plus). */
const reponse = (p, re, methode = 'GET', filtre = () => true) => p.waitForResponse((r) => {
  const u = new URL(r.url())
  return re.test(u.pathname.slice(API.length)) && r.request().method() === methode && filtre(u)
}, T)
/** Ouvre `url` (ou recharge) en vidant les relevés ; attend le calme. */
async function charger(s, url, passe) {
  s.reseau.length = 0
  s.consoles.length = 0
  if (passe) await s.p.reload(); else await s.p.goto(url)
  await calme(s.p)
}
const PASSES = ['', 'relu après rechargement : ']
/** Pourcentage tel que rendu : Q2C affiche la valeur servie telle quelle (« 33.3 % »), l'accueil l'arrondit à l'entier
 *  (`formatPercent`, espaces insécables possibles) — on compare donc au texte de la carte, espaces normalisés. */
const normaliser = (t) => String(t ?? '').replace(/[\s\u00a0\u202f]+/g, ' ').trim()
const tauxQ2C = (p) => p.getByText("Taux d'acceptation").first().locator('xpath=..').locator('xpath=..')
const tauxAccueil = (p) => p.getByText(/signés sur/).locator('xpath=..').locator('.font-display')
const lire = async (ctx, url, quoi) => lireJson(await ctx.get(`${API}${url}`, T), quoi)

/** Client (société démo) créé par demo_admin : les devis d'essai le référencent. */
async function creerClient(r, m, prefixe) {
  return lireJson(await r.post(`${API}/crm/clients/`, {
    ...T, data: { nom: `${prefixe} ${m}`, prenom: 'Acceptation', email: `${prefixe.toLowerCase()}_${m}@example.test`, telephone: telephoneMobileUnique() },
  }), 'client')
}

// ── PF6 — ALEC55 : envoyés / acceptés / taux de la période bornés à la portée du rôle, sur les deux tableaux de bord ──
const Q2C = /^\/ventes\/dashboard\/$/
const REPORTING = /^\/reporting\/dashboard\/$/
etape('PF6-ALEC55-compteurs-periode', ['ALEC55'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const a = await compteDe('Commercial', 'alec55a')
  const b = await compteDe('Commercial', 'alec55b')
  const di = await compteDe('Directeur', 'alec55di')
  const admin = page.request
  const client = await creerClient(admin, m, 'ALEC55')
  const crees = []
  try {
    // Référence de la société : lue AVANT de créer les devis de l'étape (la démo en porte déjà d'autres).
    const adi = await apiDe(testInfo, di)
    const avantQ = (await lire(adi, '/ventes/dashboard/', 'Q2C Directeur avant')).devis
    const avantR = (await lire(adi, '/reporting/dashboard/', 'reporting Directeur avant')).conversion
    expect(avantQ.envoyes_periode, 'baseline : Q2C et reporting comptent les mêmes envoyés').toBe(avantR.nb_envoyes_periode)

    // Devis créés par l'API de CHAQUE compte (created_by = le compte), puis posés envoyé / accepté.
    const creer = async (c, statut) => {
      const x = await apiDe(testInfo, c)
      const d = await lireJson(await x.post(`${API}/ventes/devis/`, { ...T, data: { client: client.id, taux_tva: '20.00' } }), `devis de ${c.username}`)
      crees.push(d.id)
      return { id: d.id, statut }
    }
    const devis = [await creer(b, 'envoye'), await creer(b, 'accepte'), await creer(a, 'envoye')]
    await py(`from apps.ventes.models import Devis
now = timezone.now()
for pk, st in ${J(devis.map((d) => [d.id, d.statut]))}:
    Devis.objects.filter(pk=pk).update(statut=st, date_envoi=now, date_acceptation=(now.date() if st == 'accepte' else None))
sortie(1)`)

    // A (Commercial) : Quote-to-cash puis Tableau de bord, et le tunnel de /reporting : SES seuls devis (1 / 0 / 0 %).
    const sa = await ecranDe(page, suivi, testInfo, a)
    for (const passe of PASSES) {
      const lu = reponse(sa.p, Q2C, 'GET', (u) => !u.search)
      await charger(sa, '/reporting/quote-to-cash', passe)
      const rep = await lu
      expect(rep.status(), `${passe}A Q2C : tableau lu`).toBe(200)
      const d = (await rep.json()).devis
      expect([d.envoyes_periode, d.acceptes_periode, d.taux_acceptation_pct], `${passe}A : JSON ventes/dashboard/ (envoyés, acceptés, taux)`).toEqual([1, 0, 0])
      await expect(sa.p.getByText("Taux d'acceptation").first(), `${passe}A : écran Quote-to-cash rendu`).toBeVisible(V)
      await expect(sa.p.getByText('0 / 1 devis envoyés'), `${passe}A Q2C : « 0 / 1 devis envoyés »`).toBeVisible(V)
      await expect(tauxQ2C(sa.p), `${passe}A Q2C : taux affiché = taux servi (${d.taux_acceptation_pct} %, 0 pour A)`).toContainText(`${d.taux_acceptation_pct} %`, V)
      expect(normaliser(await tauxQ2C(sa.p).innerText()), `${passe}A Q2C : le taux affiché est « 0 % »`).toMatch(/(^|\s)0 %(\s|$)/)
      expect(refus(sa.reseau), `${passe}A Q2C : aucune réponse refusée`).toEqual([])
    }
    for (const passe of PASSES) {
      const lu = reponse(sa.p, Q2C, 'GET', (u) => !u.searchParams.get('mine'))
      await charger(sa, '/dashboard', passe)
      const rep = await lu
      expect(rep.status(), `${passe}A Dashboard : Quote-to-cash lu`).toBe(200)
      const d = (await rep.json()).devis
      expect([d.envoyes_periode, d.acceptes_periode, d.taux_acceptation_pct], `${passe}A : JSON du Dashboard (envoyés, acceptés, taux)`).toEqual([1, 0, 0])
      await expect(sa.p.getByText('Conversion devis → signé').first(), `${passe}A Dashboard : carte de conversion`).toBeVisible(V)
      await expect(sa.p.getByText(/0 signés sur 1 devis émis/), `${passe}A Dashboard : « 0 signés sur 1 devis émis »`).toBeVisible(V)
      await expect(tauxAccueil(sa.p), `${passe}A Dashboard : taux affiché = taux servi (${d.taux_acceptation_pct} %)`).toBeVisible(V)
      expect(normaliser(await tauxAccueil(sa.p).innerText()), `${passe}A Dashboard : taux affiché « ${Math.round(d.taux_acceptation_pct)} % »`).toBe(`${Math.round(d.taux_acceptation_pct)} %`)
      expect(refus(sa.reseau), `${passe}A Dashboard : aucune réponse refusée`).toEqual([])
    }
    // `reporting/dashboard/` : le rôle Commercial n'a pas d'écran /reporting (« Accès refusé (403) » à la route) ; la
    // réponse de l'API est lue au nom de A, deux fois (lecture pure, rien à persister).
    const aa = await apiDe(testInfo, a)
    for (const passe of PASSES) {
      const c = (await lire(aa, '/reporting/dashboard/', 'reporting A')).conversion
      expect([c.nb_envoyes_periode, c.nb_acceptes_periode, c.taux_acceptation_pct], `${passe}A : JSON reporting/dashboard/ (envoyés, acceptés, taux)`).toEqual([1, 0, 0])
    }

    // Témoin — Directeur : les chiffres de la société, +3 envoyés / +1 accepté par rapport à la référence.
    const sd = await ecranDe(page, suivi, testInfo, di)
    for (const passe of PASSES) {
      const lu = reponse(sd.p, Q2C, 'GET', (u) => !u.search)
      await charger(sd, '/reporting/quote-to-cash', passe)
      const d = (await (await lu).json()).devis
      expect([d.envoyes_periode, d.acceptes_periode], `${passe}Directeur : Q2C +3 envoyés, +1 accepté`).toEqual([avantQ.envoyes_periode + 3, avantQ.acceptes_periode + 1])
      const attendu = Math.round((d.acceptes_periode / d.envoyes_periode) * 1000) / 10
      expect(d.taux_acceptation_pct, `${passe}Directeur : taux = acceptés ÷ envoyés de la société`).toBeCloseTo(attendu, 1)
      await expect(sd.p.getByText(`${d.acceptes_periode} / ${d.envoyes_periode} devis envoyés`), `${passe}Directeur Q2C : compteurs de la société à l'écran`).toBeVisible(V)
      await expect(tauxQ2C(sd.p), `${passe}Directeur Q2C : taux affiché = taux servi (${d.taux_acceptation_pct} %)`).toContainText(`${d.taux_acceptation_pct} %`, V)
      expect(refus(sd.reseau), `${passe}Directeur Q2C : aucune réponse refusée`).toEqual([])
    }
    // Directeur — Tableau de bord (accueil) : la carte de conversion rend les chiffres de la société servis par Q2C.
    for (const passe of PASSES) {
      const lu = reponse(sd.p, Q2C, 'GET', (u) => !u.searchParams.get('mine'))
      await charger(sd, '/dashboard', passe)
      const rep = await lu
      expect(rep.status(), `${passe}Directeur Dashboard : Quote-to-cash lu`).toBe(200)
      const d = (await rep.json()).devis
      expect([d.envoyes_periode, d.acceptes_periode], `${passe}Directeur Dashboard : JSON +3 envoyés, +1 accepté`).toEqual([avantQ.envoyes_periode + 3, avantQ.acceptes_periode + 1])
      await expect(sd.p.getByText('Conversion devis → signé').first(), `${passe}Directeur Dashboard : carte de conversion`).toBeVisible(V)
      await expect(sd.p.getByText(`${d.acceptes_periode} signés sur ${d.envoyes_periode} devis émis`), `${passe}Directeur Dashboard : compteurs de la société à l'écran`).toBeVisible(V)
      expect(normaliser(await tauxAccueil(sd.p).innerText()), `${passe}Directeur Dashboard : taux affiché = taux servi arrondi`).toBe(`${Math.round(d.taux_acceptation_pct)} %`)
      expect(refus(sd.reseau), `${passe}Directeur Dashboard : aucune réponse refusée`).toEqual([])
    }
    for (const passe of PASSES) {
      const lu = reponse(sd.p, REPORTING)
      await charger(sd, '/reporting', passe)
      const c = (await (await lu).json()).conversion
      expect([c.nb_envoyes_periode, c.nb_acceptes_periode], `${passe}Directeur : reporting +3 envoyés, +1 accepté`).toEqual([avantR.nb_envoyes_periode + 3, avantR.nb_acceptes_periode + 1])
      expect(refus(sd.reseau), `${passe}Directeur /reporting : aucune réponse refusée`).toEqual([])
    }
  } finally {
    await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J(crees)}).delete()
sortie(1)`).catch(() => null)
    await admin.delete(`${API}/crm/clients/${client.id}/`, T).catch(() => null)
  }
})

// ── PF6 — ALEC56 : carte « Mes équipes » du Dashboard, montants masqués pour une équipe hors de la portée du rôle ──
const EQUIPES = /^\/crm\/equipes\/statistiques\/$/
const MONTANTS = ['ca_signe_mois', 'cible_ca_signe_mois', 'pipeline_ouvert_valeur', 'pipeline_pondere', 'avancement_pct']
etape('PF6-ALEC56-mes-equipes', ['ALEC56'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const a = await compteDe('Commercial', 'alec56a')
  const b = await compteDe('Commercial', 'alec56b')
  const di = await compteDe('Directeur', 'alec56di')
  const admin = page.request
  const equipes = []
  const nomE1 = `E1 ALEC56 ${m}`
  const nomE2 = `E2 ALEC56 ${m}`
  let devisId = null
  let leadId = null
  try {
    for (const [nom, membre] of [[nomE1, a], [nomE2, b]]) {
      const e = await lireJson(await admin.post(`${API}/crm/equipes/`, { ...T, data: { nom, membres: [membre.id], actif: true } }), `équipe ${nom}`)
      equipes.push(e.id)
    }
    const [e1, e2] = equipes
    // Un devis de B signé ce mois (lead de B, une ligne 1 000 HT = 1 200 TTC), créé par l'API de B.
    const x = await apiDe(testInfo, b)
    const client = await creerClient(admin, m, 'ALEC56')
    const lead = await lireJson(await x.post(`${API}/crm/leads/`, {
      ...T, data: { nom: `ALEC56 lead ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' },
    }), 'lead de B')
    leadId = lead.id
    const devis = await lireJson(await x.post(`${API}/ventes/devis/`, { ...T, data: { lead: lead.id, client: client.id, taux_tva: '20.00', mode_installation: 'residentiel' } }), 'devis de B')
    devisId = devis.id
    await py(`from decimal import Decimal
from apps.crm.models import Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
Lead.objects.filter(pk=${lead.id}).update(owner_id=${b.id})
p = Produit.objects.create(company_id=${SOC}, sku=${J(`SKU-ALEC56-${m}`)}, nom=${J(`Panneau ALEC56 ${m}`)}, prix_vente=Decimal('1000.00'), tva=Decimal('20.00'))
LigneDevis.objects.create(devis_id=${devis.id}, produit=p, designation='Panneau', quantite=Decimal('1'), prix_unitaire=Decimal('1000.00'), taux_tva=Decimal('20.00'))
Devis.objects.filter(pk=${devis.id}).update(statut='accepte', date_envoi=timezone.now(), date_acceptation=timezone.now().date())
sortie(1)`)

    const carte = (s, nom) => s.p.locator('div.rounded-lg.border').filter({ has: s.p.getByText(nom, { exact: true }) }).first()
    // valeur affichée sous le libellé (frère suivant du libellé dans la cellule de la carte)
    const cellule = (c, libelle) => c.getByText(libelle, { exact: true }).locator('xpath=following-sibling::div[1]')
    // A (Commercial) : « Mes équipes » du Dashboard — E1 ses montants, E2 nom + effectif et « — » à la place des montants.
    const sa = await ecranDe(page, suivi, testInfo, a)
    for (const passe of PASSES) {
      const lu = reponse(sa.p, EQUIPES)
      await charger(sa, '/dashboard', passe)
      const rep = await lu
      expect(rep.status(), `${passe}A : statistiques d'équipes lues`).toBe(200)
      const parId = Object.fromEntries(((await rep.json()).equipes || []).map((e) => [e.id, e]))
      expect(parId[e1], `${passe}A : E1 servie`).toBeTruthy()
      expect(parId[e2], `${passe}A : E2 servie (nom et effectif)`).toBeTruthy()
      // avancement_pct reste null sans cible mensuelle (aucune n'est posée ici) : seuls les quatre montants chiffrés sont exigés.
      for (const k of MONTANTS.filter((x) => x !== 'avancement_pct')) expect(parId[e1][k], `${passe}A : E1 ${k} servi (non nul)`).not.toBeNull()
      expect([parId[e2].nom, parId[e2].nb_membres], `${passe}A : E2 garde nom et nb_membres`).toEqual([nomE2, 1])
      for (const k of MONTANTS) expect(parId[e2][k], `${passe}A : JSON E2 ${k} = null`).toBeNull()
      await expect(sa.p.getByText('Mes équipes').first(), `${passe}A : carte « Mes équipes »`).toBeVisible(V)
      const c1 = carte(sa, nomE1)
      const c2 = carte(sa, nomE2)
      await expect(c1, `${passe}A : équipe E1 affichée`).toBeVisible(V)
      await expect(c2, `${passe}A : équipe E2 affichée`).toBeVisible(V)
      await expect(c2, `${passe}A : E2 affiche son effectif`).toContainText('1 membre(s)')
      await expect(cellule(c1, 'CA signé (mois)'), `${passe}A : E1 montre son CA signé`).toContainText(/\d/)
      await expect(cellule(c1, 'CA signé (mois)'), `${passe}A : E1 CA signé sans « — »`).not.toContainText('—')
      await expect(cellule(c2, 'CA signé (mois)'), `${passe}A : E2 CA signé = « — »`).toContainText('—')
      await expect(cellule(c2, 'CA signé (mois)'), `${passe}A : E2 CA signé sans chiffre`).not.toContainText(/\d/)
      await expect(cellule(c2, 'Pondéré'), `${passe}A : E2 pondéré = « — »`).toContainText('—')
      await expect(cellule(c2, 'Pondéré'), `${passe}A : E2 pondéré sans chiffre`).not.toContainText(/\d/)
      expect(refus(sa.reseau), `${passe}A Dashboard : aucune réponse refusée`).toEqual([])
    }
    // Témoin — Directeur : les montants de E2 (le devis signé de B, 1 200 TTC) à l'écran et dans le JSON.
    const sd = await ecranDe(page, suivi, testInfo, di)
    for (const passe of PASSES) {
      const lu = reponse(sd.p, EQUIPES)
      await charger(sd, '/dashboard', passe)
      const rep = await lu
      expect(rep.status(), `${passe}Directeur : statistiques d'équipes lues`).toBe(200)
      const ligne = ((await rep.json()).equipes || []).find((e) => e.id === e2)
      expect(ligne, `${passe}Directeur : E2 servie`).toBeTruthy()
      for (const k of ['ca_signe_mois', 'cible_ca_signe_mois', 'pipeline_ouvert_valeur', 'pipeline_pondere']) {
        expect(ligne[k], `${passe}Directeur : E2 ${k} présent`).not.toBeNull()
      }
      expect(Number(ligne.ca_signe_mois), `${passe}Directeur : E2 CA signé = le devis de B`).toBe(1200)
      const c2 = carte(sd, nomE2)
      await expect(c2, `${passe}Directeur : équipe E2 affichée`).toBeVisible(V)
      await expect(cellule(c2, 'CA signé (mois)'), `${passe}Directeur : E2 CA signé chiffré`).toContainText(/1\s?200/)
      await expect(cellule(c2, 'CA signé (mois)'), `${passe}Directeur : E2 CA signé sans « — »`).not.toContainText('—')
      expect(refus(sd.reseau), `${passe}Directeur Dashboard : aucune réponse refusée`).toEqual([])
    }
  } finally {
    await py(`from apps.crm.models import EquipeCommerciale, Lead
from apps.ventes.models import Devis
Devis.objects.filter(pk=${J(devisId)}).delete()
Lead.objects.filter(pk=${J(leadId)}).delete()
EquipeCommerciale.objects.filter(pk__in=${J(equipes)}).delete()
sortie(1)`).catch(() => null)
  }
})
