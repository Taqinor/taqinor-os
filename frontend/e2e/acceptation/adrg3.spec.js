// Rejeu en direct du lot 3 du groupe ADRG (parcours PF4 « droits de la grille », dossier
// docs/audits/2026-11-10-parcours-PF4.md) : ADRG22, 39, 40, 47, 66, 87 (SAV), ADRG102 (sécurité),
// ADRG24, 32, 34, 35, 36, 37 (stock), ADRG76 (transverse). Chaque étape joue les RÔLES LIVRÉS du
// registre (rôles système de la société de demo_admin relus par leur nom, jamais un rôle fabriqué) :
// geste refusé par la vraie route sous un compte connecté (+ relecture : rien d'écrit), geste légitime
// inchangé, et l'écran rendu sous le même rôle (bouton absent / présent). Société = celle de demo_admin.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG22', 'ADRG39', 'ADRG40', 'ADRG47', 'ADRG66', 'ADRG87', 'ADRG102',
  'ADRG24', 'ADRG32', 'ADRG34', 'ADRG35', 'ADRG36', 'ADRG37', 'ADRG76'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
// Onglets des rôles : fermés APRÈS l'étape (ses oracles, dont le 8, relisent chaque page encore ouverte).
const OUVERTS = []
test.afterEach(async () => { for (const c of OUVERTS.splice(0)) await c.close().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const J = JSON.stringify
const aujourdhui = () => new Date().toISOString().slice(0, 10)

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société (registre, `init_roles`) ; `null` = compte hérité
 *  « responsable » sans rôle fin. Renvoie {username, id}. */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
r = ${nomRole === null ? 'None' : `Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True).pk`}
u = compte(${J(username)}, role=r, societe=${SOC})
${nomRole === null ? "u.role_id = None; u.role_legacy = 'responsable'; u.save()" : ''}
sortie(u.id)`)
  return { username, id }
}
/** Contexte API connecté par la vraie route `/token/`. */
async function apiDe(testInfo, c) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: c.username, password: MDP_ESSAI })
  return ctx
}
/** Onglet navigateur connecté sous le compte `c`, observé par les oracles. */
async function ecranDe(page, suivi, testInfo, c) {
  const ctx = await page.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block' })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  OUVERTS.push(ctx)
  const p = suivi.surveiller(await ctx.newPage())
  return { ctx, p }
}
/** Ouvre `url` et attend la réponse de liste `re` (la donnée est chargée : une absence vaut alors preuve). */
async function ouvrir(p, url, re) {
  const charge = re ? p.waitForResponse((r) => re.test(new URL(r.url()).pathname) && r.request().method() === 'GET', V) : null
  await p.goto(url)
  if (charge) expect((await charge).status(), `chargement ${url}`).toBeLessThan(400)
  await p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
}
async function refus(rep, code, quoi) {
  const t = await rep.text()
  expect(rep.status(), `${quoi} : ${t.slice(0, 240)}`).toBe(403)
  if (code) expect(t, `${quoi} : code du droit`).toContain(code)
}
async function passe(rep, quoi, attendus = [200, 201, 204]) {
  const t = rep.status() === 204 ? '' : await rep.text()
  expect(attendus, `${quoi} → ${rep.status()} ${t.slice(0, 240)}`).toContain(rep.status())
  if (!t) return null
  try { return JSON.parse(t) } catch { return t }
}
const bouton = (p, nom) => p.getByRole('button', { name: nom })
/** Contextes API seulement (les onglets des rôles sont fermés par `afterEach`). */
const fermer = async (...xs) => { for (const x of xs) if (x && typeof x.dispose === 'function') await x.dispose().catch(() => undefined) }
const clientCrm = async (r, m) => lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADRG3 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `adrg3_${m}@example.invalid` } }), 'client')
const produitApi = async (r, nom) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: '1000.00', prix_achat: '600.00' } }), 'produit')

// ── SAV ────────────────────────────────────────────────────────────────────────────────────────────

etape('PF4.4-ADRG22', ['ADRG22'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const te = await compteDe('Technicien', 'adrg22te')
  const co = await compteDe('Commercial', 'adrg22co')
  const re = await compteDe('Responsable', 'adrg22re')
  const cl = await clientCrm(r, m)
  const tickets = []
  for (const s of ['a', 'b']) tickets.push(await lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG22 ${m} ${s}` } }), 'ticket'))
  // Portée : technicien responsable = le Technicien d'essai, créé par le Commercial d'essai (les deux voient les tickets).
  await py(`from apps.sav.models import Ticket
Ticket.objects.filter(pk__in=${J(tickets.map((t) => t.id))}).update(technicien_responsable_id=${te.id}, created_by_id=${co.id})
sortie(1)`)
  const refs = tickets.map((t) => t.reference || t.numero || `ADRG22 ${m}`)

  /** Liste : sélectionne les deux tickets, rend les libellés des actions groupées (en ligne + menu « Plus »). */
  async function actionsGroupees(p) {
    await ouvrir(p, '/sav', /\/sav\/tickets\/?$/)
    await p.getByPlaceholder('Rechercher (référence, client, chantier, description)…').fill(refs[0] === refs[1] ? `ADRG22 ${m}` : String(m))
    for (const ref of refs) {
      const ligne = p.getByRole('row').filter({ hasText: ref }).first()
      await expect(ligne, `ligne ${ref}`).toBeVisible(V)
      await ligne.getByRole('checkbox').first().check()
    }
    const barre = p.locator('[aria-label="2 ligne(s) sélectionnée(s)"]')
    await expect(barre, 'barre d’actions groupées').toBeVisible(V)
    const libelles = (await barre.getByRole('button').allInnerTexts()).map((x) => x.trim())
    const plus = barre.getByRole('button', { name: /^Plus$/ })
    if (await plus.count()) {
      await plus.click()
      libelles.push(...(await p.getByRole('menuitem').allInnerTexts()).map((x) => x.trim()))
      await p.keyboard.press('Escape')
    }
    return libelles
  }
  /** Fiche : ouverte par le lien profond `?id=` ; rend le panneau. */
  async function fiche(p) {
    await ouvrir(p, `/sav?id=${tickets[0].id}`, /\/sav\/tickets\/?$/)
    // ≥ 1280 px : panneau latéral `<aside aria-label="Détail du ticket …">` ; en dessous, tiroir (dialog).
    const d = p.locator('aside[aria-label^="Détail du ticket"], [role="dialog"]').filter({ has: p.locator('label', { hasText: /^Technicien responsable/ }) }).first()
    await expect(d, 'fiche ticket').toBeVisible(V)
    return d
  }
  const champ = (d, libelle) => d.locator('label', { hasText: new RegExp(`^${libelle}`) }).first().locator('xpath=..').getByRole('combobox').first()

  // Technicien (sav_gerer sans sav_reassign) : aucune « Assigner à … », technicien en lecture, transitions présentes.
  const t1 = await ecranDe(page, suivi, testInfo, te)
  const libT = await actionsGroupees(t1.p)
  expect(libT.filter((x) => /Assigner à/.test(x)), `Technicien : actions groupées ${J(libT)}`).toEqual([])
  const dT = await fiche(t1.p)
  await expect(champ(dT, 'Technicien responsable'), 'Technicien : « Technicien responsable » en lecture').toBeDisabled()
  await expect(champ(dT, 'Statut'), 'Technicien : transitions présentes').toBeEnabled()
  await expect(bouton(dT, /Mettre à jour/), 'Technicien : enregistrer présent').toBeVisible()
  // Commercial (sav_voir sans sav_gerer) : aucun geste d'écriture du ticket.
  const c1 = await ecranDe(page, suivi, testInfo, co)
  const libC = await actionsGroupees(c1.p)
  expect(libC.filter((x) => /Assigner à|^Annuler$|^Priorité/.test(x)), `Commercial : actions groupées ${J(libC)}`).toEqual([])
  const dC = await fiche(c1.p)
  await expect(champ(dC, 'Statut'), 'Commercial : statut en lecture').toBeDisabled()
  await expect(champ(dC, 'Technicien responsable'), 'Commercial : technicien en lecture').toBeDisabled()
  for (const n of [/Mettre à jour/, /Annuler le ticket/, /^Noter$/, /Planifier une intervention/, /Ajouter une intervention/]) {
    await expect(bouton(dC, n), `Commercial : pas de « ${n} »`).toHaveCount(0)
  }
  // Relecture après rechargement : mêmes états à l'écran.
  const dT2 = await fiche(t1.p)
  await expect(champ(dT2, 'Technicien responsable'), 'Technicien relu : technicien en lecture').toBeDisabled()
  await expect(bouton(dT2, /Mettre à jour/), 'Technicien relu : enregistrer présent').toBeVisible()
  const dC2 = await fiche(c1.p)
  await expect(champ(dC2, 'Statut'), 'Commercial relu : statut en lecture').toBeDisabled()
  await expect(bouton(dC2, /Mettre à jour/), 'Commercial relu : pas de « Mettre à jour »').toHaveCount(0)
  const libC2 = await actionsGroupees(c1.p)
  expect(libC2.filter((x) => /Assigner à|^Annuler$|^Priorité/.test(x)), `Commercial relu : actions groupées ${J(libC2)}`).toEqual([])
  // Témoin : le Responsable (sav_reassign) garde « Assigner à … » et le sélecteur éditable.
  const r1 = await ecranDe(page, suivi, testInfo, re)
  const libR = await actionsGroupees(r1.p)
  expect(libR.some((x) => /Assigner à/.test(x)), `Responsable : actions groupées ${J(libR)}`).toBeTruthy()
  const dR = await fiche(r1.p)
  await expect(champ(dR, 'Technicien responsable'), 'Responsable : sélecteur éditable').toBeEnabled()
  // Persistance : rendu seul, les tickets relus sont inchangés.
  const relus = await py(`from apps.sav.models import Ticket
sortie(sorted(Ticket.objects.filter(pk__in=${J(tickets.map((t) => t.id))}).values_list('technicien_responsable_id', flat=True)))`)
  expect(relus, 'tickets relus inchangés').toEqual([te.id, te.id])
  await fermer(t1.ctx, c1.ctx, r1.ctx)
}, { ecart: { base: 'FAIL', raison: "frontend/src/pages/sav/TicketsPage.jsx::TicketDetail charge à l'ouverture de la fiche, pour tout rôle, les LECTURES sav/tickets/<id>/checklist|prets-equipement|pieces|pieces-unifiees|pieces-compatibles et installations/interventions/?ticket= ; un compte de lecture de l'étape (rôle livré sans le droit de ces routes) reçoit 403 + console.error (oracles 2-3). Défaut antérieur, hors ADRG22 (qui ne garde que les gestes d'ÉCRITURE, aucune lecture changée) : avant ADRG22 la même fiche échouait déjà sur ces 403." } })

/** Équipement en service (API admin) ; `proprietaire` = compte qui doit le VOIR (portée sav : créé par lui). */
async function equipement(r, m, prefixe, proprietaire = null) {
  const p = await produitApi(r, `Onduleur ${prefixe} ${m}`)
  const serie = `${prefixe}-${m}`
  const eq = await lireJson(await r.post(`${API}/sav/equipements/`, { ...T, data: { produit: p.id, numero_serie: serie, date_pose: aujourdhui() } }), 'équipement')
  if (proprietaire) {
    await py(`from apps.sav.models import Equipement
Equipement.objects.filter(pk=${eq.id}).update(created_by_id=${proprietaire.id})
sortie(1)`)
  }
  return { eq, serie }
}
async function ficheEquipement(p, serie) {
  await ouvrir(p, '/equipements', /\/sav\/equipements\/?$/)
  await p.getByPlaceholder('Rechercher (série, produit, chantier, client)…').fill(serie)
  const ligne = p.getByRole('row').filter({ hasText: serie }).first()
  await expect(ligne, `ligne ${serie}`).toBeVisible(V)
  await ligne.getByText(serie).first().click()
  const d = p.getByRole('dialog').filter({ has: p.getByRole('button', { name: /Mettre à jour/ }) }).last()
  await expect(d, 'fiche équipement ouverte').toBeVisible(V)
  return d
}

etape('PF4.2-ADRG39', ['ADRG39'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const { eq } = await equipement(r, m, 'ADRG39')
  const cat = await lireJson(await r.post(`${API}/sav/categories-equipement/`, { ...T, data: { nom: `Cat ADRG39 ${m}` } }), 'catégorie')
  const etatEq = () => py(`from apps.sav.models import Equipement, CategorieEquipement
e = Equipement.objects.get(pk=${eq.id}); c = CategorieEquipement.objects.get(pk=${cat.id})
sortie([e.mis_au_rebut, e.motif_rebut or '', c.nom, CategorieEquipement.objects.filter(company_id=${SOC}).count()])`)
  const avant = await etatEq()
  for (const nom of ['Commercial responsable', 'Technicien', 'Responsable']) {
    const c = await compteDe(nom, 'adrg39')
    const x = await apiDe(testInfo, c)
    await refus(await x.post(`${API}/sav/equipements/${eq.id}/mettre-au-rebut/`, { ...T, data: { motif: 'Casse définitive' } }), null, `${nom} rebut`)
    await refus(await x.post(`${API}/sav/equipements/${eq.id}/reactiver-rebut/`, { ...T, data: {} }), null, `${nom} réactiver`)
    await refus(await x.post(`${API}/sav/categories-equipement/`, { ...T, data: { nom: `Pirate ${m}` } }), null, `${nom} catégorie POST`)
    await refus(await x.patch(`${API}/sav/categories-equipement/${cat.id}/`, { ...T, data: { nom: `Pirate ${m}` } }), null, `${nom} catégorie PATCH`)
    expect(await etatEq(), `${nom} : équipement et catégorie relus inchangés`).toEqual(avant)
    await fermer(x)
  }
  // Légitimes inchangés : Technicien responsable, Directeur, Administrateur, compte hérité responsable.
  for (const [i, nom] of ['Technicien responsable', 'Directeur', 'Administrateur', null].entries()) {
    const c = await compteDe(nom, 'adrg39ok')
    const x = await apiDe(testInfo, c)
    const { eq: sien } = await equipement(r, `${m}${i}`, 'ADRG39OK', c)
    await passe(await x.post(`${API}/sav/equipements/${sien.id}/mettre-au-rebut/`, { ...T, data: { motif: 'Casse définitive' } }), `${nom ?? 'hérité'} rebut`)
    await passe(await x.post(`${API}/sav/equipements/${sien.id}/reactiver-rebut/`, { ...T, data: {} }), `${nom ?? 'hérité'} réactiver`)
    await passe(await x.post(`${API}/sav/categories-equipement/`, { ...T, data: { nom: `Cat ${nom ?? 'hérité'} ${m}` } }), `${nom ?? 'hérité'} catégorie`)
    await fermer(x)
  }
  // Écran : la fiche n'offre plus « Mettre au rebut » au Commercial responsable ; le Technicien responsable l'a.
  const vuCr = await compteDe('Commercial responsable', 'adrg39cr')
  const fCr = await equipement(r, m, 'ADRG39CR', vuCr)
  const cr = await ecranDe(page, suivi, testInfo, vuCr)
  await expect(bouton(await ficheEquipement(cr.p, fCr.serie), /Mettre au rebut/), 'Commercial responsable : pas de « Mettre au rebut »').toHaveCount(0)
  await expect(bouton(await ficheEquipement(cr.p, fCr.serie), /Mettre au rebut/), 'Commercial responsable relu après rechargement').toHaveCount(0)
  const vuTr = await compteDe('Technicien responsable', 'adrg39tr')
  const fTr = await equipement(r, m, 'ADRG39TR', vuTr)
  const tr = await ecranDe(page, suivi, testInfo, vuTr)
  await expect(bouton(await ficheEquipement(tr.p, fTr.serie), /Mettre au rebut/), 'Technicien responsable : « Mettre au rebut »').toBeVisible(V)
  await fermer(cr.ctx, tr.ctx)
  await py(`from apps.sav.models import CategorieEquipement
CategorieEquipement.objects.filter(company_id=${SOC}, nom__endswith=${J(` ${m}`)}).delete()
sortie(1)`).catch(() => null)
}, { ecart: { base: 'FAIL', raison: "frontend/src/pages/sav/EquipementsPage.jsx::EquipementDetail lit à l'ouverture de la fiche GET sav/equipements/<id>/downtime/ et /releves-compteur/, deux @action réservées à l'administrateur (backend/django_core/apps/sav/views.py::EquipementViewSet.downtime / .releves_compteur, permission_classes=[IsAdminRole], XSAV16/17, posées les 11-12/10/2026) : tout rôle non administrateur (Commercial responsable ET Technicien responsable) reçoit 403 + console.error (oracles 2-3). Défaut antérieur, hors ADRG39 (qui ne touche que rebut/réactivation/catégories) : avant ADRG39 la même fiche échouait déjà sur ces 403." } })

etape('PF4.2-ADRG40', ['ADRG40'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const cl = await clientCrm(r, m)
  const autre = await py(`sortie(U.objects.get(username='demo_tech').id)`)
  const equipe = await py(`from apps.sav.models import EquipeMaintenance
sortie(EquipeMaintenance.objects.create(company_id=${SOC}, nom=${J(`Équipe ADRG40 ${m}`)}).pk)`)
  const prev = []
  for (const s of ['a', 'b']) prev.push((await lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'preventif', description: `ADRG40 ${m} ${s}` } }), 'ticket préventif')).id)
  const etat = () => py(`from apps.sav.models import Ticket
sortie([list(Ticket.objects.filter(pk__in=${J(prev)}).order_by('pk').values_list('technicien_responsable_id', 'date_tournee')), Ticket.objects.filter(company_id=${SOC}, description__startswith=${J(`ADRG40 ${m}`)}).count()])`)
  const te = await compteDe('Technicien', 'adrg40te')
  const x = await apiDe(testInfo, te)
  const avant = await etat()
  await refus(await x.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui(), technicien_id: autre } }), 'sav_reassign', 'Technicien tournée avec technicien')
  await refus(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} tech`, technicien_responsable: autre } }), 'sav_reassign', 'Technicien ticket affecté')
  await refus(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} equipe`, equipe } }), 'sav_reassign', 'Technicien ticket à une équipe')
  expect(await etat(), 'après les 403 : tickets relus inchangés, aucun ticket créé').toEqual(avant)
  // Sans technicien ni équipe : le Technicien planifie et crée.
  const sans = await passe(await x.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui() } }), 'Technicien tournée sans technicien')
  expect(sans.tickets_planifies, 'tournée sans technicien : 2 tickets').toBe(2)
  await passe(await x.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} libre` } }), 'Technicien ticket non affecté')
  await fermer(x)
  // Légitimes : Responsable, Commercial responsable, compte hérité responsable.
  for (const nom of ['Responsable', 'Commercial responsable', null]) {
    const y = await apiDe(testInfo, await compteDe(nom, 'adrg40ok'))
    await passe(await y.post(`${API}/sav/contrats-maintenance/planifier-tournee/`, { ...T, data: { ticket_ids: prev, date_tournee: aujourdhui(), technicien_id: autre } }), `${nom ?? 'hérité'} tournée avec technicien`)
    await passe(await y.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG40 ${m} ${nom ?? 'herite'}`, technicien_responsable: autre } }), `${nom ?? 'hérité'} ticket affecté`)
    await fermer(y)
  }
  // Écran : l'onglet Tournée n'offre plus le choix du technicien au Technicien ; le Responsable l'a.
  async function tournee(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/sav/contrats', /\/sav\/contrats-maintenance\/?$/)
    await e.p.getByRole('radio', { name: 'Tournée' }).or(e.p.getByRole('button', { name: 'Tournée', exact: true })).or(e.p.getByRole('tab', { name: 'Tournée' })).first().click()
    await expect(e.p.getByLabel('Date de tournée'), 'onglet Tournée rendu').toBeVisible(V)
    return e
  }
  const t1 = await tournee(te)
  await expect(t1.p.getByText('Technicien (optionnel)'), 'Technicien : pas de choix du technicien').toHaveCount(0)
  await t1.p.reload()
  await t1.p.getByRole('radio', { name: 'Tournée' }).or(t1.p.getByRole('button', { name: 'Tournée', exact: true })).or(t1.p.getByRole('tab', { name: 'Tournée' })).first().click()
  await expect(t1.p.getByLabel('Date de tournée'), 'Tournée relue après rechargement').toBeVisible(V)
  await expect(t1.p.getByText('Technicien (optionnel)'), 'Technicien relu : pas de choix du technicien').toHaveCount(0)
  const r1 = await tournee(await compteDe('Responsable', 'adrg40re'))
  await expect(r1.p.getByLabel('Technicien (optionnel)'), 'Responsable : choix du technicien').toBeVisible(V)
  await fermer(t1.ctx, r1.ctx)
}, { ecart: { base: 'FAIL', raison: "frontend/src/pages/sav/ContratsMaintenance.jsx (WIR230, 26/08/2026, l. ~317) appelle GET /api/django/users/ au montage de l'écran pour TOUT rôle ; le Technicien livré (sans users_voir) reçoit 403 + console.error (oracles 2-3). Défaut antérieur, hors ADRG40 (qui ne touche que le sélecteur « Technicien (optionnel) » et technicien_id) : avant ADRG40 la même étape échouait déjà sur ce 403." } })

etape('PF4.4-ADRG47', ['ADRG47'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  // Système supervisé visible du Commercial : vente portée par lui (lead + devis), chantier réceptionné au parc, config noop.
  const co = await compteDe('Commercial', 'adrg47co')
  const xc = await apiDe(testInfo, co)
  const lead = await lireJson(await xc.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG47 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg47_${m}@example.invalid` } }), 'lead')
  const prod = await produitApi(r, `Onduleur réseau ADRG47 ${m}`)
  const d = await lireJson(await xc.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await xc.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADRG47' } }), 'accepter')
  await fermer(xc)
  const inst = await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
from apps.monitoring.models import MonitoringConfig
d = Devis.objects.get(pk=${d.id})
inst = Installation.objects.filter(devis=d).first()
if inst is None:
    from apps.installations.services import create_installation_from_devis
    res = create_installation_from_devis(d, U.objects.get(username='demo_admin'), d.company)
    inst = res[0] if isinstance(res, tuple) else res
Installation.objects.filter(pk=inst.pk).update(statut=Installation.Statut.RECEPTIONNE, parc_actif=True, annule=False)
MonitoringConfig.objects.get_or_create(company_id=inst.company_id, installation=inst, defaults=dict(provider='noop'))
sortie(dict(id=inst.pk, ref=inst.reference))`)
  const choix = new RegExp(`${inst.ref}|#${inst.id}\\b`)
  async function systeme(p) {
    const s = p.getByRole('combobox', { name: /Choisir un système (supervisé|installé)/ }).first()
    await expect(s, 'sélecteur de système').toBeVisible(V)
    await s.click()
    await p.getByRole('option', { name: choix }).first().click()
  }
  const ECRITURES = [/Synchroniser maintenant/, /Saisir un relevé/, /Enregistrer un nettoyage/, /Nouvelle garantie/]
  async function supervision(c, attendu) {
    const e = await ecranDe(page, suivi, testInfo, c)
    const vus = []
    await ouvrir(e.p, '/production', /\/installations\/chantiers\/?$/)
    await systeme(e.p)
    await expect(e.p.getByText('Supervision automatique').first(), 'production : système chargé').toBeVisible(V)
    await e.p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
    for (const n of ECRITURES.slice(0, 2)) vus.push([String(n), await e.p.getByText(n).count()])
    await ouvrir(e.p, '/production/nettoyages', /\/monitoring\/configs\/?$/)
    await systeme(e.p)
    await e.p.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => undefined)
    vus.push([String(ECRITURES[2]), await e.p.getByText(ECRITURES[2]).count()])
    await ouvrir(e.p, '/production/garanties', /\/monitoring\/warranties\/?$/)
    vus.push([String(ECRITURES[3]), await bouton(e.p, ECRITURES[3]).count()])
    for (const [n, k] of vus) {
      if (attendu) expect(k, `${c.username} : « ${n} » présent`).toBeGreaterThan(0)
      else expect(k, `${c.username} : « ${n} » absent`).toBe(0)
    }
    return e
  }
  const ec = await supervision(co, false)
  await supervision(co, false) // relecture après rechargement : mêmes écrans rouverts, toujours aucun geste
  const ed = await supervision(await compteDe('Directeur', 'adrg47di'), true)
  await fermer(ec.ctx, ed.ctx)
  await py(`from apps.monitoring.models import MonitoringConfig
from apps.installations.models import Installation
MonitoringConfig.objects.filter(installation_id=${inst.id}).delete(); Installation.objects.filter(pk=${inst.id}).update(parc_actif=False)
sortie(1)`).catch(() => null)
})

etape('PF4.3-ADRG66', ['ADRG66'], async ({ page, suivi, testInfo }) => {
  async function importer(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/equipements', /\/sav\/equipements\/?$/)
    await expect(bouton(e.p, /Étiquettes QR internes/), 'écran Équipements rendu').toBeVisible(V)
    return { e, n: await bouton(e.p, /^Importer$/).count() }
  }
  const vuCo = await compteDe('Commercial', 'adrg66co')
  const co = await importer(vuCo)
  expect(co.n, 'Commercial : pas de « Importer »').toBe(0)
  expect((await importer(vuCo)).n, 'Commercial relu après rechargement : pas de « Importer »').toBe(0)
  const cr = await importer(await compteDe('Commercial responsable', 'adrg66cr'))
  expect(cr.n, 'Commercial responsable : pas de « Importer »').toBe(0)
  const tr = await importer(await compteDe('Technicien responsable', 'adrg66tr'))
  expect(tr.n, 'Technicien responsable : « Importer »').toBe(1)
  await fermer(co.e.ctx, cr.e.ctx, tr.e.ctx)
})

etape('PF4.4-ADRG87', ['ADRG87'], async ({ page, suivi, testInfo }) => {
  // L'écran n'a pas de bouton « Nouveau problème » : ses gestes d'écriture sont « Créer le problème » (regroupements),
  // et sur un problème ouvert par « Gérer » : « Lier un ticket », « Enregistrer le problème », « Supprimer ce problème ».
  const m = marque()
  const prob = await lireJson(await page.request.post(`${API}/sav/problemes/`, { ...T, data: { titre: `ADRG87 ${m}` } }), 'problème')
  const ECRITURE = /^(Lier un ticket|Enregistrer le problème|Supprimer ce problème|Créer le problème)$/
  const nb = () => py(`from apps.sav.models import Probleme
sortie(Probleme.objects.filter(company_id=${SOC}).count())`)
  async function gestes(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/sav/problemes', /\/sav\/problemes\/?$/)
    await expect(e.p.getByRole('heading', { name: 'Problèmes', exact: true }), 'écran Problèmes rendu').toBeVisible(V)
    await e.p.getByRole('row').filter({ hasText: `ADRG87 ${m}` }).getByRole('button', { name: 'Gérer' }).click()
    const panneau = e.p.locator('section[aria-label^="Problème "]').filter({ hasText: `ADRG87 ${m}` })
    expect(prob.id, 'problème créé').toBeTruthy()
    await expect(panneau, 'problème ouvert').toBeVisible(V)
    await expect(bouton(panneau, /^Fermer$/).first(), 'panneau rendu').toBeVisible(V)
    return { e, n: await e.p.getByRole('button', { name: ECRITURE }).count() }
  }
  // Rôle fin sans sav_probleme_gerer : la route refuse (rien de créé) et l'écran n'offre aucun geste d'écriture.
  const crc = await compteDe('Commercial responsable', 'adrg87cr')
  const x = await apiDe(testInfo, crc)
  const avant = await nb()
  await refus(await x.post(`${API}/sav/problemes/`, { ...T, data: { titre: `Pirate ADRG87 ${m}` } }), null, 'Commercial responsable crée un problème')
  expect(await nb(), 'aucun problème créé').toBe(avant)
  await fermer(x)
  const cr = await gestes(crc)
  expect(cr.n, 'Commercial responsable : aucun geste d’écriture').toBe(0)
  expect((await gestes(crc)).n, 'Commercial responsable relu après rechargement : aucun geste d’écriture').toBe(0)
  // Porteur du code et compte hérité responsable (repli palier) : gestes présents.
  const tr = await gestes(await compteDe('Technicien responsable', 'adrg87tr'))
  expect(tr.n, 'Technicien responsable : gestes d’écriture présents').toBeGreaterThan(0)
  const he = await gestes(await compteDe(null, 'adrg87he'))
  expect(he.n, 'compte hérité responsable : gestes d’écriture présents').toBeGreaterThan(0)
})

// ── Sécurité : liens publics de tableau de bord ───────────────────────────────────────────────────

etape('PF4.5-ADRG102', ['ADRG102'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const a = await compteDe('Commercial responsable', 'adrg102a')
  const b = await compteDe('Commercial', 'adrg102b')
  const xa = await apiDe(testInfo, a)
  const xb = await apiDe(testInfo, b)
  const perso = await passe(await xa.post(`${API}/core/dashboards/`, { ...T, data: { titre: `Perso ADRG102 ${m}`, partage: false } }), 'A crée son tableau personnel')
  const lienA = await passe(await xa.post(`${API}/core/dashboards-partages/`, { ...T, data: { dashboard: perso.id } }), 'A publie son tableau')
  const liens = () => py(`from core.models import PartageDashboard
sortie(sorted(PartageDashboard.objects.filter(dashboard_id=${perso.id}).values_list('id', 'actif')))`)
  const avant = await liens()
  const p1 = await xb.post(`${API}/core/dashboards-partages/`, { ...T, data: { dashboard: perso.id } })
  expect(p1.status(), `B POST le tableau de A : ${(await p1.text()).slice(0, 200)}`).toBe(404)
  const p2 = await xb.patch(`${API}/core/dashboards-partages/${lienA.id}/`, { ...T, data: { actif: false } })
  expect(p2.status(), 'B PATCH le lien de A').toBe(404)
  const p3 = await xb.delete(`${API}/core/dashboards-partages/${lienA.id}/`, T)
  expect(p3.status(), 'B DELETE le lien de A').toBe(404)
  expect(await liens(), 'liens de A relus inchangés (actif, aucun créé)').toEqual(avant)
  // Le propriétaire garde la main ; un tableau partagé reste publiable par B.
  const l2 = await passe(await xa.post(`${API}/core/dashboards-partages/`, { ...T, data: { dashboard: perso.id } }), 'A crée', [201])
  await passe(await xa.patch(`${API}/core/dashboards-partages/${l2.id}/`, { ...T, data: { actif: false } }), 'A révoque', [200])
  await passe(await xa.delete(`${API}/core/dashboards-partages/${l2.id}/`, T), 'A supprime', [204])
  const commun = await passe(await xa.post(`${API}/core/dashboards/`, { ...T, data: { titre: `Commun ADRG102 ${m}`, partage: true } }), 'A crée un tableau partagé')
  await passe(await xb.post(`${API}/core/dashboards-partages/`, { ...T, data: { dashboard: commun.id } }), 'B publie le tableau partagé', [201])
  // Écran Rapports → Partage de tableaux : le lien de A n'apparaît pas à un collègue ; A le voit.
  const lien = (p) => p.getByText(new RegExp(lienA.token.slice(0, 16)))
  const ea = await ecranDe(page, suivi, testInfo, a)
  await ouvrir(ea.p, '/reporting/dashboards/partage', /\/core\/dashboards-partages\/?$/)
  await expect(lien(ea.p).first(), 'A voit son lien').toBeVisible(V)
  const e2 = await ecranDe(page, suivi, testInfo, await compteDe('Commercial responsable', 'adrg102c'))
  await ouvrir(e2.p, '/reporting/dashboards/partage', /\/core\/dashboards-partages\/?$/)
  await expect(e2.p.getByRole('heading', { name: 'Partage de tableaux de bord' }), 'écran rendu').toBeVisible(V)
  await expect(lien(e2.p), 'collègue : le lien de A n’apparaît pas').toHaveCount(0)
  await ouvrir(e2.p, '/reporting/dashboards/partage', /\/core\/dashboards-partages\/?$/)
  await expect(e2.p.getByRole('heading', { name: 'Partage de tableaux de bord' }), 'écran relu').toBeVisible(V)
  await expect(lien(e2.p), 'collègue relu après rechargement : lien de A absent').toHaveCount(0)
  await expect(lien(ea.p).first(), 'A voit toujours son lien').toBeVisible(V)
  await fermer(xa, xb, ea.ctx, e2.ctx)
})

// ── Stock ─────────────────────────────────────────────────────────────────────────────────────────

etape('PF4.4-ADRG24', ['ADRG24'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const prod = await produitApi(page.request, `Panneau ADRG24 ${m}`)
  async function exports(c, avecSelection) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/mouvements', /\/stock\/mouvements\/?$/)
    const mouvements = await bouton(e.p, /Exporter Excel/).count()
    await ouvrir(e.p, '/stock/fournisseurs/conformite', null)
    await expect(e.p.getByRole('heading', { name: 'Conformité fournisseurs' }), 'conformité rendue').toBeVisible(V)
    const conformite = await bouton(e.p, /Exporter en Excel/).count()
    let masse = null
    if (avecSelection) {
      await ouvrir(e.p, '/stock', /\/stock\/produits\/?$/)
      await e.p.getByPlaceholder('Chercher partout…').fill(prod.nom)
      await e.p.getByRole('checkbox', { name: `Sélectionner ${prod.nom}` }).check(V)
      const barre = e.p.getByRole('region', { name: 'Actions produits en masse' })
      await expect(barre, 'barre de masse des produits').toBeVisible(V)
      masse = await bouton(barre, /Exporter Excel/).count()
    }
    return { e, mouvements, conformite, masse }
  }
  const vuRe = await compteDe('Responsable', 'adrg24re')
  const re = await exports(vuRe, true)
  expect([re.mouvements, re.conformite, re.masse], 'Responsable : aucun export serveur (mouvements, conformité, masse)').toEqual([0, 0, 0])
  const re2 = await exports(vuRe, true)
  expect([re2.mouvements, re2.conformite, re2.masse], 'Responsable relu après rechargement').toEqual([0, 0, 0])
  const cr = await exports(await compteDe('Commercial responsable', 'adrg24cr'), false)
  expect([cr.mouvements, cr.conformite], 'Commercial responsable : aucun export serveur').toEqual([0, 0])
  const tr = await exports(await compteDe('Technicien responsable', 'adrg24tr'), true)
  expect([tr.mouvements, tr.conformite, tr.masse], 'Technicien responsable : les trois exports présents').toEqual([1, 1, 1])
  await fermer(re.e.ctx, cr.e.ctx, tr.e.ctx)
})

etape('PF4.2-ADRG32', ['ADRG32'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const an = 2300 + Math.floor(Math.random() * 600)
  const ids = await py(`import datetime
from decimal import Decimal
from apps.stock.models import Fournisseur, AccordRFAFournisseur, BudgetDepartement
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`F-ADRG32 ${m}`)})
a = AccordRFAFournisseur.objects.create(company_id=${SOC}, fournisseur=f, periode_debut=datetime.date(2026, 1, 1), periode_fin=datetime.date(2026, 12, 31), seuil_ca_achat=Decimal('50000'), taux_pct=Decimal('3'))
b = BudgetDepartement.objects.create(company_id=${SOC}, annee=${an}, montant_alloue=Decimal('1000'))
sortie(dict(f=f.pk, a=a.pk, b=b.pk))`)
  const etat = () => py(`from apps.stock.models import AccordRFAFournisseur, BudgetDepartement
sortie([AccordRFAFournisseur.objects.filter(company_id=${SOC}).count(), BudgetDepartement.objects.filter(company_id=${SOC}).count(), AccordRFAFournisseur.objects.get(pk=${ids.a}).note, BudgetDepartement.objects.get(pk=${ids.b}).note])`)
  let n = 0
  const gestes = async (x) => {
    n += 1
    const f = await py(`from apps.stock.models import Fournisseur
sortie(Fournisseur.objects.create(company_id=${SOC}, nom=${J(`F-ADRG32 ${m} ${n}`)}).pk)`)
    return {
      rfa_post: await x.post(`${API}/stock/accords-rfa-fournisseur/`, { ...T, data: { fournisseur: f, periode_debut: '2026-01-01', periode_fin: '2026-12-31', seuil_ca_achat: '1000', taux_pct: '3' } }),
      rfa_patch: await x.patch(`${API}/stock/accords-rfa-fournisseur/${ids.a}/`, { ...T, data: { note: `n${n}` } }),
      budget_post: await x.post(`${API}/stock/budgets-departement/`, { ...T, data: { periodicite: 'annuelle', annee: 2040 + n, mois: 0, montant_alloue: '500.00' } }),
      budget_patch: await x.patch(`${API}/stock/budgets-departement/${ids.b}/`, { ...T, data: { note: `n${n}` } }),
    }
  }
  const avant = await etat()
  for (const nom of ['Commercial responsable', 'Technicien responsable', 'Technicien', 'Responsable', 'Admin Ventes']) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg32'))
    for (const [g, rep] of Object.entries(await gestes(x))) await refus(rep, 'achats_commander', `${nom} ${g}`)
    expect(await etat(), `${nom} : accords et budgets relus inchangés`).toEqual(avant)
    await fermer(x)
  }
  for (const nom of ['Directeur', 'Administrateur', null]) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg32ok'))
    for (const [g, rep] of Object.entries(await gestes(x))) await passe(rep, `${nom ?? 'hérité'} ${g}`, [200, 201])
    await fermer(x)
  }
  // Écran RFA : pas de création sans le droit ; le Directeur l'a.
  async function rfa(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/negoce/rfa', /\/stock\/accords-rfa-fournisseur\/?$/)
    await expect(e.p.getByRole('heading', { name: 'Remises arrière (RFA)' }), 'écran RFA rendu').toBeVisible(V)
    return { e, n: await e.p.getByText('Nouvel accord', { exact: true }).count() }
  }
  const vuCr = await compteDe('Commercial responsable', 'adrg32cr')
  const cr = await rfa(vuCr)
  expect(cr.n, 'Commercial responsable : pas de « Nouvel accord »').toBe(0)
  expect((await rfa(vuCr)).n, 'Commercial responsable relu après rechargement').toBe(0)
  const di = await rfa(await compteDe('Directeur', 'adrg32di'))
  expect(di.n, 'Directeur : « Nouvel accord »').toBeGreaterThan(0)
  await fermer(cr.e.ctx, di.e.ctx)
})

etape('PF4.2-ADRG34', ['ADRG34'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const dep = await py(`import datetime
from decimal import Decimal
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.stock.services_consignation import creer_depot_consignation
c = Client.objects.create(company_id=${SOC}, nom=${J(`Consigne ${m}`)}, prenom='Client', email=${J(`adrg34_${m}@example.invalid`)})
p = Produit.objects.create(company_id=${SOC}, nom=${J(`Panneau ADRG34 ${m}`)}, sku=${J(`SKU-ADRG34-${m}`)}, prix_vente=Decimal('1500.00'), prix_achat=Decimal('900.00'), tva=Decimal('20.00'), quantite_stock=10)
d = creer_depot_consignation(company=c.company, user=U.objects.get(username='demo_admin'), client_id=c.id, produit_id=p.id, quantite=4, date_depot=datetime.date.today(), adresse_site=${J(`Site ADRG34 ${m}`)})
sortie(dict(id=d.pk, client=c.pk))`)
  const etat = () => py(`from apps.stock.models import DepotConsignation
from apps.ventes.models import Facture
sortie([str(DepotConsignation.objects.get(pk=${dep.id}).quantite_consommee_declaree), Facture.objects.filter(company_id=${SOC}).count()])`)
  const corps = { ...T, data: { quantite: 1, date_declaration: aujourdhui() } }
  const avant = await etat()
  for (const nom of ['Technicien', 'Technicien responsable']) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg34'))
    await refus(await x.post(`${API}/stock/consignations/${dep.id}/declarer-consommation/`, corps), 'ventes_creer', `${nom} déclarer`)
    expect(await etat(), `${nom} : dépôt et factures relus inchangés`).toEqual(avant)
    await fermer(x)
  }
  for (const nom of ['Directeur', null]) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg34ok'))
    const ok = await passe(await x.post(`${API}/stock/consignations/${dep.id}/declarer-consommation/`, corps), `${nom ?? 'hérité'} déclarer`, [201])
    expect(ok.facture_id, `${nom ?? 'hérité'} : facture brouillon`).toBeTruthy()
    await fermer(x)
  }
  // Écran Consignations : « Déclarer » absent au Technicien, présent au Directeur (le dépôt reste actif : 2 restants).
  async function declarer(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/negoce/consignations', /\/stock\/consignations\/?$/)
    await expect(e.p.getByText(`Site ADRG34 ${m}`).first(), 'dépôt affiché').toBeVisible(V)
    return { e, n: await bouton(e.p, 'Déclarer la consommation').count() }
  }
  const vuTe = await compteDe('Technicien', 'adrg34te')
  const te = await declarer(vuTe)
  expect(te.n, 'Technicien : pas de « Déclarer »').toBe(0)
  expect((await declarer(vuTe)).n, 'Technicien relu après rechargement : pas de « Déclarer »').toBe(0)
  const di = await declarer(await compteDe('Directeur', 'adrg34di'))
  expect(di.n, 'Directeur : « Déclarer »').toBeGreaterThan(0)
  await fermer(te.e.ctx, di.e.ctx)
})

const N = 999999
const ENTREPOT = [
  ['post', 'lots-entrepot/'], ['patch', `lots-entrepot/${N}/`], ['post', `lots-entrepot/${N}/sortir/`],
  ['post', 'consignations/'], ['patch', `consignations/${N}/`],
  ['post', 'vagues-picking/'], ['post', `vagues-picking/${N}/lancer/`], ['post', `vagues-picking/${N}/configurer-liberation/`],
  ['post', `vagues-picking/${N}/lignes/${N}/prelever/`],
  ['post', 'unites-logistiques/'], ['post', `unites-logistiques/${N}/lignes/`], ['post', `unites-logistiques/${N}/controler-scan/`],
  ['post', `unites-logistiques/${N}/deplacer/`], ['post', `unites-logistiques/${N}/sceller/`], ['post', 'unites-logistiques/import-asn/'],
  ['post', 'expeditions/'], ['post', `expeditions/${N}/generer-etiquette/`],
  ['post', 'plans-chargement/'], ['post', `plans-chargement/${N}/unites/`],
  ['post', 'retours-client/'], ['post', `retours-client/${N}/receptionner/`], ['post', `retours-client/${N}/inspecter/`],
  ['post', 'blocages-qualite/'], ['post', `blocages-qualite/${N}/lever/`], ['post', 'blocages-qualite/lever-quarantaine/'],
  ['post', 'taches-reappro-interne/'], ['post', `taches-reappro-interne/${N}/executer/`],
  ['post', 'casiers-a-reapprovisionner/'],
]
const compteModeles = (noms) => py(`from django.apps import apps
sortie([apps.get_model('stock', n).objects.count() for n in ${J(noms)}])`)

etape('PF4.2-ADRG35', ['ADRG35'], async ({ page, suivi, testInfo }) => {
  const MODELES = ['MouvementStock', 'LotEntrepot', 'DepotConsignation', 'VaguePicking', 'UniteLogistique', 'ExpeditionTransporteur',
    'PlanChargement', 'RetourClient', 'BlocageQualite', 'TacheReapproInterne']
  const avant = await compteModeles(MODELES)
  const cr = await compteDe('Commercial responsable', 'adrg35cr')
  const x = await apiDe(testInfo, cr)
  for (const [methode, route] of ENTREPOT) await refus(await x[methode](`${API}/stock/${route}`, { ...T, data: {} }), 'stock_mouvement', `Commercial responsable ${methode} ${route}`)
  await fermer(x)
  expect(await compteModeles(MODELES), 'après les 403 : aucun mouvement ni objet d’entrepôt écrit').toEqual(avant)
  for (const nom of ['Technicien', null]) {
    const y = await apiDe(testInfo, await compteDe(nom, 'adrg35ok'))
    for (const [methode, route] of ENTREPOT) {
      const rep = await y[methode](`${API}/stock/${route}`, { ...T, data: {} })
      expect(rep.status(), `${nom ?? 'hérité'} ${methode} ${route} passe la garde : ${(await rep.text()).slice(0, 160)}`).not.toBe(403)
    }
    await fermer(y)
  }
  // Écran Picking : aucun bouton d'écriture au Commercial responsable ; le Technicien a « Nouvelle vague ».
  async function picking(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/entrepot/picking', /\/stock\/vagues-picking\/?$/)
    await expect(e.p.getByRole('heading', { name: 'Picking' }), 'écran Picking rendu').toBeVisible(V)
    return { e, n: await e.p.getByText('Nouvelle vague', { exact: true }).count(), b: await bouton(e.p, /^(Lancer|Prélever|Créer la vague)/).count() }
  }
  const e1 = await picking(cr)
  expect([e1.n, e1.b], 'Commercial responsable : ni « Nouvelle vague » ni geste de vague').toEqual([0, 0])
  const e1b = await picking(cr)
  expect([e1b.n, e1b.b], 'Commercial responsable relu après rechargement').toEqual([0, 0])
  const e2 = await picking(await compteDe('Technicien', 'adrg35te'))
  expect(e2.n, 'Technicien : « Nouvelle vague »').toBeGreaterThan(0)
  await fermer(e1.e.ctx, e2.e.ctx)
})

const REFERENTIELS = ['incidents-qualite-fournisseur/', 'casiers-hazmat/', 'nomenclatures-code-barres/', 'regles-code-barres/',
  'dossiers-onboarding-fournisseur/', 'documents-fournisseur/', 'profils-saisonniers/', 'plans-echantillonnage/',
  'seuils-reappro-casier/', 'alertes-rappel/', 'rendez-vous-transporteur/']
const ECRITURES_REF = [...REFERENTIELS.map((r) => ['post', r]), ['patch', `profils-saisonniers/${N}/`], ['post', `alertes-rappel/${N}/cloturer/`]]
const SUPPRESSIONS_REF = ['nomenclatures-code-barres', 'regles-code-barres', 'dossiers-onboarding-fournisseur', 'documents-fournisseur', 'profils-saisonniers']

etape('PF4.2-ADRG36', ['ADRG36'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const MODELES = ['IncidentQualiteFournisseur', 'CompatibiliteHazmatCasier', 'NomenclatureCodeBarres', 'RegleCodeBarres',
    'DossierOnboardingFournisseur', 'DocumentFournisseur', 'ProfilSaisonnier', 'PlanEchantillonnage', 'SeuilReapproCasier',
    'AlerteRappel', 'RendezVousTransporteur']
  // Une nomenclature réelle : la suppression refusée la laisse présente.
  const nomenclature = await py(`from apps.stock.models import NomenclatureCodeBarres
sortie(NomenclatureCodeBarres.objects.create(company_id=${SOC}, nom=${J(`Nomenclature ADRG36 ${m}`)}).pk)`)
  const avant = await compteModeles(MODELES)
  const te = await compteDe('Technicien', 'adrg36te')
  for (const nom of ['Commercial responsable', 'Technicien']) {
    const x = await apiDe(testInfo, nom === 'Technicien' ? te : await compteDe(nom, 'adrg36'))
    for (const [methode, route] of ECRITURES_REF) await refus(await x[methode](`${API}/stock/${route}`, { ...T, data: {} }), 'stock_modifier', `${nom} ${methode} ${route}`)
    await fermer(x)
  }
  expect(await compteModeles(MODELES), 'après les 403 : aucun référentiel écrit').toEqual(avant)
  for (const nom of ['Technicien responsable', null]) {
    const y = await apiDe(testInfo, await compteDe(nom, 'adrg36ok'))
    for (const [methode, route] of ECRITURES_REF) {
      const rep = await y[methode](`${API}/stock/${route}`, { ...T, data: {} })
      expect(rep.status(), `${nom ?? 'hérité'} ${methode} ${route} passe la garde : ${(await rep.text()).slice(0, 160)}`).not.toBe(403)
    }
    for (const s of SUPPRESSIONS_REF) await refus(await y.delete(`${API}/stock/${s}/${N}/`, T), null, `${nom ?? 'hérité'} DELETE ${s}`)
    await refus(await y.delete(`${API}/stock/nomenclatures-code-barres/${nomenclature}/`, T), null, `${nom ?? 'hérité'} DELETE nomenclature réelle`)
    await fermer(y)
  }
  expect(await py(`from apps.stock.models import NomenclatureCodeBarres
sortie(NomenclatureCodeBarres.objects.filter(pk=${nomenclature}).exists())`), 'nomenclature relue : présente').toBe(true)
  const di = await apiDe(testInfo, await compteDe('Directeur', 'adrg36di'))
  for (const s of SUPPRESSIONS_REF) {
    const rep = await di.delete(`${API}/stock/${s}/${N}/`, T)
    expect(rep.status(), `Directeur DELETE ${s} jamais 403`).not.toBe(403)
  }
  await passe(await di.delete(`${API}/stock/nomenclatures-code-barres/${nomenclature}/`, T), 'Directeur supprime la nomenclature', [204])
  await fermer(di)
  // Écran Quais : aucun bouton de référentiel au Technicien ; le Technicien responsable a « Nouveau rendez-vous ».
  async function quais(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/entrepot/quais', /\/stock\/rendez-vous-transporteur\/?$/)
    await expect(e.p.getByRole('heading', { name: 'Quais et rendez-vous' }), 'écran Quais rendu').toBeVisible(V)
    return { e, n: await e.p.getByText('Nouveau rendez-vous', { exact: true }).count() }
  }
  const e1 = await quais(te)
  expect(e1.n, 'Technicien : pas de « Nouveau rendez-vous »').toBe(0)
  expect((await quais(te)).n, 'Technicien relu après rechargement : pas de « Nouveau rendez-vous »').toBe(0)
  const e2 = await quais(await compteDe('Technicien responsable', 'adrg36tr'))
  expect(e2.n, 'Technicien responsable : « Nouveau rendez-vous »').toBeGreaterThan(0)
  await fermer(e1.e.ctx, e2.e.ctx)
})

etape('PF4.2-ADRG37', ['ADRG37'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  let i = 0
  const objets = () => {
    i += 1
    return py(`from decimal import Decimal
from apps.stock.models import Produit, ConditionnementProduit, PrixFournisseur, Fournisseur
p, _ = Produit.objects.get_or_create(company_id=${SOC}, sku=${J(`SKU-ADRG37-${m}`)}, defaults=dict(nom=${J(`Câble ADRG37 ${m}`)}, prix_vente=Decimal('100.00'), prix_achat=Decimal('60.00')))
c = ConditionnementProduit.objects.create(company_id=${SOC}, produit=p, nom=${J(`Carton ADRG37 ${m} `)} + str(${i}), facteur=Decimal('10'))
f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`F-ADRG37 ${m} `)} + str(${i}))
x = PrixFournisseur.objects.create(company_id=${SOC}, produit=p, fournisseur=f, prix_achat=Decimal('800.00'))
sortie(dict(c=c.pk, x=x.pk, nom=c.nom))`)
  }
  const presents = (o) => py(`from apps.stock.models import ConditionnementProduit, PrixFournisseur
sortie([ConditionnementProduit.objects.filter(pk=${o.c}).exists(), PrixFournisseur.objects.filter(pk=${o.x}).exists()])`)
  for (const [nom, attendu] of [['Technicien responsable', 403], ['Responsable', 403], [null, 403], ['Directeur', 204], ['Administrateur', 204]]) {
    const o = await objets()
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg37'))
    for (const url of [`${API}/stock/conditionnements/${o.c}/`, `${API}/stock/prix-fournisseurs/${o.x}/`]) {
      const rep = await x.delete(url, T)
      expect(rep.status(), `${nom ?? 'hérité'} DELETE ${url}`).toBe(attendu)
    }
    expect(await presents(o), `${nom ?? 'hérité'} : objets relus`).toEqual(attendu === 403 ? [true, true] : [false, false])
    await fermer(x)
  }
  // Écran Conditionnements : « Supprimer » absent au Responsable (« Modifier » reste), présent au Directeur.
  const o = await objets()
  async function ligne(c) {
    const e = await ecranDe(page, suivi, testInfo, c)
    await ouvrir(e.p, '/stock/conditionnements', /\/stock\/conditionnements\/?$/)
    await e.p.getByPlaceholder('Rechercher (conditionnement, produit)…').fill(o.nom)
    const l = e.p.getByRole('row').filter({ hasText: o.nom }).first()
    await expect(l, 'conditionnement listé').toBeVisible(V)
    return { e, sup: await l.getByRole('button', { name: 'Supprimer' }).count(), mod: await l.getByRole('button', { name: 'Modifier' }).count() }
  }
  const vuRe = await compteDe('Responsable', 'adrg37re')
  const re = await ligne(vuRe)
  expect([re.sup, re.mod > 0], 'Responsable : pas de « Supprimer », « Modifier » présent').toEqual([0, true])
  const re2 = await ligne(vuRe)
  expect([re2.sup, re2.mod > 0], 'Responsable relu après rechargement').toEqual([0, true])
  const di = await ligne(await compteDe('Directeur', 'adrg37di'))
  expect(di.sup, 'Directeur : « Supprimer »').toBeGreaterThan(0)
  await fermer(re.e.ctx, di.e.ctx)
})

// ── Transverse : exports planifiés et rapports personnalisés ──────────────────────────────────────

etape('PF4.3-ADRG76', ['ADRG76'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const rapport = await py(`from apps.reporting.models import RapportDefinition
sortie(RapportDefinition.objects.create(company_id=${SOC}, owner=U.objects.get(username='demo_admin'), titre=${J(`Stock ADRG76 ${m}`)}, dataset='stock_produits', spec={'select': ['id']}, partage='societe').pk)`)
  const extraits = () => py(`from core.models import ScheduledExport
sortie(ScheduledExport.objects.filter(company_id=${SOC}).count())`)
  const avant = await extraits()
  const corps = (qui) => ({ ...T, data: { titre: `Stock ADRG76 ${qui} ${m}`, dataset: 'stock_produits', cron: '0 2 * * *' } })
  for (const nom of ['Responsable', 'Commercial responsable']) {
    const x = await apiDe(testInfo, await compteDe(nom, 'adrg76'))
    await refus(await x.post(`${API}/core/scheduled-exports/`, corps(nom)), null, `${nom} planifie un extrait stock`)
    await refus(await x.get(`${API}/reporting/rapport-definitions/${rapport}/export/?format=csv`, T), null, `${nom} exporte le rapport stock`)
    expect(await extraits(), `${nom} : aucun extrait créé`).toBe(avant)
    await fermer(x)
  }
  const di = await apiDe(testInfo, await compteDe('Directeur', 'adrg76di'))
  await passe(await di.post(`${API}/core/scheduled-exports/`, corps('Directeur')), 'Directeur planifie', [201])
  await passe(await di.get(`${API}/reporting/rapport-definitions/${rapport}/export/?format=csv`, T), 'Directeur exporte', [200])
  await fermer(di)
  // Écran Paramètres → Exports planifiés : le Responsable est refusé sur le jeu stock, rien de créé.
  const e = await ecranDe(page, suivi, testInfo, await compteDe('Responsable', 'adrg76re'))
  suivi.attendre(/\/api\/django\/core\/scheduled-exports\/?$/, 403)
  await ouvrir(e.p, '/parametres?onglet=exports_planifies', /\/core\/scheduled-exports\/?$/)
  const titre = `Ecran ADRG76 ${m}`
  await e.p.getByPlaceholder('Titre (ex. Ventes du mois vers le comptable)').fill(titre)
  await e.p.getByPlaceholder('Jeu de données').fill('stock_produits')
  await e.p.getByPlaceholder('Planification cron (ex. 0 6 * * 1)').fill('0 2 * * *')
  const [rep] = await Promise.all([
    e.p.waitForResponse((x) => /\/core\/scheduled-exports\/?$/.test(new URL(x.url()).pathname) && x.request().method() === 'POST', V),
    bouton(e.p, /Créer l'export/).click(),
  ])
  expect(rep.status(), 'écran : création refusée').toBe(403)
  await ouvrir(e.p, '/parametres?onglet=exports_planifies', /\/core\/scheduled-exports\/?$/)
  await expect(e.p.getByText(titre), 'relu : aucun extrait à ce titre').toHaveCount(0)
  expect(await extraits(), 'extraits de la société : seul celui du Directeur ajouté').toBe(avant + 1)
  await fermer(e.ctx)
})
