// Preuves en direct du groupe ADRG, lot 13 (vague d'acceptation 8, runner GitHub, 17/11/2026) : correctifs de la
// vague 7 — ADRG142 (prix fournisseurs de la fiche produit sous `prix_achat_voir`), ADRG143 (listes de l'éditeur
// d'accès GED sous `ged_gouvernance`), ADRG144 (badges de l'accueil sous un code `reporting_*`), ADRG145 (tableau de
// bord de /reporting sous la lecture des ventes) — et les tâches qu'ils rendent enfin prouvables : ADRG37 (fiche
// produit), ADRG73 (rôle qui ATTEINT /reporting sans `reporting_export` : Admin RH), ADRG80 (fiche document sans 403).
// Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo), plus deux
// rôles PERSONNALISÉS nommés par la preuve qu'ils rendent discriminante : « Responsable + prix_achat_voir » (ADRG142 :
// « rejouée avec un rôle porteur du code et de stock_modifier » — aucun rôle système non administrateur ne porte
// `prix_achat_voir`) et « Admin RH + ventes_voir » (ADRG73 : tableau chargé, seul le code d'export manque). Connexion
// par la vraie route `/token/` dans un navigateur à part ; chaque réponse de l'API est relevée (« onglet réseau ») et
// chaque `console.error` de la page : les clauses « aucun appel X », « sans 403 », « console propre » sont affirmées
// sur ces relevés, en plus des oracles. Données propres (API de demo_admin ou shell Django), retirées en fin d'étape ;
// chaque écran est relu après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG142', 'ADRG37', 'ADRG145', 'ADRG73', 'ADRG144', 'ADRG143', 'ADRG80'])
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
const rolesPerso = []
test.afterAll(async () => {
  if (comptes.length) {
    await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
  }
  if (rolesPerso.length) {
    await py(`from apps.roles.models import Role
U.objects.filter(role_id__in=${J(rolesPerso)}).update(role_id=None, is_active=False)
Role.objects.filter(pk__in=${J(rolesPerso)}).delete()
sortie(1)`).catch(() => null)
  }
})

/** Compte d'essai : rôle SYSTÈME `nomRole`, rôle de pk `rolePk`, ou (nomRole null, sans pk) compte HÉRITÉ
 *  « responsable » sans rôle fin ; {username, id, nomRole, codes} (codes du rôle relus en base). */
async function compteDe(nomRole, prefixe, rolePk = null) {
  const username = `${prefixe}_${marque()}`
  const herite = nomRole === null && !rolePk
  const x = await py(`from apps.roles.models import Role
r = ${herite ? 'None' : (rolePk ? `Role.objects.get(pk=${rolePk})` : `Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)`)}
u = compte(${J(username)}, role=(r.pk if r else None), societe=${SOC})
${herite ? "u.role_id = None; u.role_legacy = 'responsable'; u.save()" : ''}
sortie(dict(id=u.id, codes=sorted((r.permissions if r else None) or [])))`)
  comptes.push(username)
  return { username, id: x.id, codes: x.codes, nomRole: nomRole ?? 'hérité responsable' }
}
/** Rôle PERSONNALISÉ (est_systeme=False) = codes du rôle système `base` + `ajouts` ; renvoie son pk. */
async function rolePersonnalise(base, ajouts, nom) {
  const pk = await py(`from apps.roles.models import Role
b = Role.objects.get(company_id=${SOC}, nom=${J(base)}, est_systeme=True)
r = Role.objects.create(company_id=${SOC}, nom=${J(nom)}, permissions=sorted(set((b.permissions or []) + ${J(ajouts)})))
sortie(r.pk)`)
  rolesPerso.push(pk)
  return pk
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
const chemin = (l) => l.split(' ')[1].split('?')[0]
/** Lignes de `reseau` dont le chemin (sans requête) correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
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
const bouton = (zone, nom) => zone.getByRole('button', { name: nom })

/** 403 qui NOMME le code manquant (`droit_manquant`). */
async function refusNomme(res, code, quoi) {
  const corps = await res.text()
  expect(res.status(), `${quoi} : ${corps.slice(0, 240)}`).toBe(403)
  expect(corps, `${quoi} : le refus nomme ${code}`).toContain(code)
  expect(corps, `${quoi} : code droit_manquant`).toContain('droit_manquant')
}

// ───────────────────────── Stock : fiche produit ─────────────────────────

/** Produit + `n` prix fournisseurs (fournisseurs propres) + un conditionnement ; noms relus. */
async function produitAPrix(m, prefixe, prix) {
  return py(`from decimal import Decimal
from apps.stock.models import Produit, ConditionnementProduit, PrixFournisseur, Fournisseur
p = Produit.objects.create(company_id=${SOC}, sku=${J(`SKU-${prefixe}-${m}`)}, nom=${J(`Câble ${prefixe} ${m}`)}, prix_vente=Decimal('100.00'), prix_achat=Decimal('60.00'))
c = ConditionnementProduit.objects.create(company_id=${SOC}, produit=p, nom=${J(`Carton ${prefixe} ${m}`)}, facteur=Decimal('10'))
lignes = []
for i, montant in enumerate(${J(prix)}):
    f = Fournisseur.objects.create(company_id=${SOC}, nom=${J(`F-${prefixe} ${m} `)} + str(i))
    x = PrixFournisseur.objects.create(company_id=${SOC}, produit=p, fournisseur=f, prix_achat=Decimal(montant))
    lignes.append(dict(id=x.pk, fournisseur=f.pk, nom=f.nom))
sortie(dict(produit=p.pk, nom=p.nom, cond=c.pk, cond_nom=c.nom, lignes=lignes))`)
}
const nettoyerProduit = (o) => py(`from apps.stock.models import Produit, ConditionnementProduit, PrixFournisseur, Fournisseur
PrixFournisseur.objects.filter(produit_id=${o.produit}).delete()
ConditionnementProduit.objects.filter(produit_id=${o.produit}).delete()
Fournisseur.objects.filter(pk__in=${J(o.lignes.map((l) => l.fournisseur))}).delete()
Produit.objects.filter(pk=${o.produit}).delete()
sortie(1)`).catch(() => null)

/** Stock › catalogue : cherche le produit, ouvre « Éditer » ; renvoie le dialogue de la fiche (chargée, calme). */
async function ficheEdition(s, nom, passe) {
  await charger(s, '/stock', passe)
  await s.p.getByPlaceholder('Chercher partout…').fill(nom, V)
  const ligne = s.p.getByRole('row').filter({ hasText: nom }).first()
  await expect(ligne, `${s.c.nomRole} : produit listé au catalogue`).toBeVisible(V)
  await bouton(ligne, "Plus d'actions sur la ligne").click()
  await s.p.getByRole('menuitem', { name: 'Éditer' }).click()
  const form = s.p.getByRole('dialog').filter({ has: s.p.locator('#pf-vente') })
  await expect(form, `${s.c.nomRole} : fiche produit ouverte en édition`).toBeVisible(V)
  await expect(form.getByRole('button', { name: 'Mettre à jour' }), `${s.c.nomRole} : fiche en mode édition`).toBeVisible(V)
  await calme(s.p)
  return form
}
const sectionPrix = (form) => form.locator('section').filter({ hasText: 'Prix fournisseurs (interne)' })
const PRIX_FOURN = (id) => new RegExp(`^/stock/produits/${id}/prix-fournisseurs/$`)

// ── PF4.2 — ADRG142 : prix fournisseurs de la fiche produit ni chargés ni affichés sans `prix_achat_voir` ─────────
etape('PF4.2-ADRG142-fiche-produit', ['ADRG142'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const o = await produitAPrix(m, 'ADRG142', ['800.00', '750.00'])
  try {
    const re = await compteDe('Responsable', 'adrg142re')
    const di = await compteDe('Directeur', 'adrg142di')
    expect([re.codes.includes('stock_modifier'), re.codes.includes('prix_achat_voir')], 'Given : Responsable stock_modifier sans prix_achat_voir').toEqual([true, false])
    expect(di.codes.includes('prix_achat_voir'), 'Given : Directeur avec prix_achat_voir').toBe(true)
    // Responsable : fiche en édition sans aucun appel prix-fournisseurs ni section des prix fournisseurs.
    const s = await ecranDe(page, suivi, testInfo, re)
    for (const passe of PASSES) {
      const form = await ficheEdition(s, o.nom, passe)
      console.log(`[ADRG142] ${passe}Responsable fiche ${o.produit} : ${J(s.reseau)}`)
      expect(appels(s.reseau, PRIX_FOURN(o.produit)), `${passe}Responsable : aucun GET stock/produits/${o.produit}/prix-fournisseurs/`).toEqual([])
      await expect(form.getByText('Prix fournisseurs (interne)'), `${passe}Responsable : aucune section des prix fournisseurs`).toHaveCount(0)
      expect(refus(s.reseau), `${passe}Responsable : aucune réponse refusée (aucune 403)`).toEqual([])
    }
    // Directeur : la section et ses deux lignes (lues par l'appel prix-fournisseurs, 200).
    const d = await ecranDe(page, suivi, testInfo, di)
    for (const passe of PASSES) {
      const lu = reponse(d.p, PRIX_FOURN(o.produit))
      const form = await ficheEdition(d, o.nom, passe)
      const rep = await lu
      expect(rep.status(), `${passe}Directeur : prix fournisseurs lus`).toBe(200)
      const corps = await rep.json()
      expect((Array.isArray(corps) ? corps : corps.results || []).length, `${passe}Directeur : deux prix servis`).toBe(2)
      const section = sectionPrix(form)
      await expect(section, `${passe}Directeur : section des prix fournisseurs`).toBeVisible(V)
      for (const [l, montant] of [[o.lignes[0], /800[,.]00/], [o.lignes[1], /750[,.]00/]]) {
        const tr = section.locator('tr').filter({ hasText: l.nom })
        await expect(tr, `${passe}Directeur : ligne ${l.nom}`).toBeVisible(V)
        await expect(tr, `${passe}Directeur : prix de ${l.nom}`).toContainText(montant)
      }
      expect(refus(d.reseau), `${passe}Directeur : aucune réponse refusée`).toEqual([])
    }
  } finally {
    await nettoyerProduit(o)
  }
})

// ── PF4.2 — ADRG37 : supprimer un conditionnement / un prix fournisseur réservé à l'administrateur ; « Supprimer »
// retiré de Conditionnements ET de la fiche produit (rôle porteur de `prix_achat_voir` + `stock_modifier`) ─────────
etape('PF4.2-ADRG37-suppression', ['ADRG37'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const crees = []
  const objets = async (suffixe) => { const o = await produitAPrix(`${m}${suffixe}`, 'ADRG37', ['800.00']); crees.push(o); return o }
  const presents = (o) => py(`from apps.stock.models import ConditionnementProduit, PrixFournisseur
sortie([ConditionnementProduit.objects.filter(pk=${o.cond}).exists(), PrixFournisseur.objects.filter(pk=${o.lignes[0].id}).exists()])`)
  try {
    const perso = await rolePersonnalise('Responsable', ['prix_achat_voir'], `Responsable + prix_achat_voir ADRG37 ${m}`)
    const comptesRole = {}
    for (const [cle, nom, pk] of [['tr', 'Technicien responsable'], ['re', 'Responsable'], ['he', null], ['pe', 'Responsable + prix_achat_voir', perso],
      ['di', 'Directeur'], ['ad', 'Administrateur']]) {
      comptesRole[cle] = await compteDe(nom, `adrg37${cle}`, pk || null)
    }
    const pe = comptesRole.pe
    expect([pe.codes.includes('prix_achat_voir'), pe.codes.includes('stock_modifier'), pe.codes.includes('stock_supprimer'), pe.codes.includes('roles_gerer')],
      'Given : rôle personnalisé prix_achat_voir + stock_modifier, sans stock_supprimer ni roles_gerer (non administrateur)').toEqual([true, true, false, false])
    for (const cle of ['tr', 're']) {
      expect([comptesRole[cle].codes.includes('stock_modifier'), comptesRole[cle].codes.includes('stock_supprimer')], `Given : ${comptesRole[cle].nomRole} stock_modifier sans stock_supprimer`).toEqual([true, false])
    }
    // Route : DELETE 403 aux non-administrateurs (objets relus présents), 204 au Directeur et à l'Administrateur.
    for (const [cle, attendu] of [['tr', 403], ['re', 403], ['he', 403], ['pe', 403], ['di', 204], ['ad', 204]]) {
      const c = comptesRole[cle]
      const o = await objets(cle)
      const x = await apiDe(testInfo, c)
      for (const url of [`${API}/stock/conditionnements/${o.cond}/`, `${API}/stock/prix-fournisseurs/${o.lignes[0].id}/`]) {
        const rep = await x.delete(url, T)
        expect(rep.status(), `${c.nomRole} DELETE ${url} : ${rep.status() === 204 ? '' : (await rep.text()).slice(0, 200)}`).toBe(attendu)
      }
      expect(await presents(o), `${c.nomRole} : objets relus après le DELETE`).toEqual(attendu === 403 ? [true, true] : [false, false])
    }
    // Création et modification inchangées pour le Responsable (`stock_modifier`).
    const ore = await objets('mod')
    const xre = await apiDe(testInfo, comptesRole.re)
    const patch = await xre.patch(`${API}/stock/conditionnements/${ore.cond}/`, { ...T, data: { facteur: '12' } })
    expect(patch.status(), `Responsable modifie le conditionnement : ${(await patch.text()).slice(0, 200)}`).toBe(200)
    const cree = await xre.post(`${API}/stock/conditionnements/`, { ...T, data: { produit: ore.produit, nom: `Palette ADRG37 ${m}`, facteur: '40' } })
    expect(cree.status(), `Responsable crée un conditionnement : ${(await cree.text()).slice(0, 200)}`).toBe(201)
    const [facteur, nCond] = await py(`from apps.stock.models import ConditionnementProduit
sortie([str(ConditionnementProduit.objects.get(pk=${ore.cond}).facteur), ConditionnementProduit.objects.filter(produit_id=${ore.produit}).count()])`)
    expect(Number(facteur), 'relu : facteur du conditionnement modifié à 12').toBe(12)
    expect(nCond, 'relu : conditionnement créé par le Responsable (2 sur le produit)').toBe(2)

    // Écran Stock › Conditionnements : pas de « Supprimer » (« Modifier » reste) au Responsable et au Technicien
    // responsable, présent au Directeur ; relu après rechargement.
    const oc = await objets('ecr')
    async function ligneCond(s, passe) {
      const lu = reponse(s.p, /^\/stock\/conditionnements\/$/)
      await charger(s, '/stock/conditionnements', passe)
      expect((await lu).status(), `${passe}${s.c.nomRole} : conditionnements lus`).toBe(200)
      await s.p.getByPlaceholder('Rechercher (conditionnement, produit)…').fill(oc.cond_nom)
      const l = s.p.getByRole('row').filter({ hasText: oc.cond_nom }).first()
      await expect(l, `${passe}${s.c.nomRole} : conditionnement listé`).toBeVisible(V)
      return { sup: await l.getByRole('button', { name: 'Supprimer' }).count(), mod: await l.getByRole('button', { name: 'Modifier' }).count() }
    }
    for (const cle of ['re', 'tr']) {
      const s = await ecranDe(page, suivi, testInfo, comptesRole[cle])
      for (const passe of PASSES) {
        const r = await ligneCond(s, passe)
        expect([r.sup, r.mod > 0], `${passe}${s.c.nomRole} Conditionnements : pas de « Supprimer », « Modifier » présent`).toEqual([0, true])
        expect(refus(s.reseau), `${passe}${s.c.nomRole} Conditionnements : aucune réponse refusée`).toEqual([])
      }
    }
    const sdi = await ecranDe(page, suivi, testInfo, comptesRole.di)
    expect((await ligneCond(sdi, '')).sup, 'Directeur Conditionnements : « Supprimer » présent').toBeGreaterThan(0)

    // Fiche produit en édition, section « Prix fournisseurs (interne) » :
    //  - Responsable : section absente (ADRG142), aucun appel, aucune 403 ;
    //  - rôle porteur de prix_achat_voir + stock_modifier (non administrateur) : la ligne est chargée et affichée,
    //    « Modifier le prix » présent, « Supprimer » ABSENT — la preuve discriminante ;
    //  - Directeur : « Supprimer » présent sur la même ligne.
    const sre = await ecranDe(page, suivi, testInfo, comptesRole.re)
    for (const passe of PASSES) {
      const form = await ficheEdition(sre, oc.nom, passe)
      expect(appels(sre.reseau, PRIX_FOURN(oc.produit)), `${passe}Responsable fiche : aucun appel prix-fournisseurs`).toEqual([])
      await expect(form.getByText('Prix fournisseurs (interne)'), `${passe}Responsable fiche : pas de section des prix`).toHaveCount(0)
      await expect(sectionPrix(form).getByRole('button', { name: 'Supprimer' }), `${passe}Responsable fiche : pas de « Supprimer »`).toHaveCount(0)
      expect(refus(sre.reseau), `${passe}Responsable fiche : aucune réponse refusée`).toEqual([])
    }
    for (const [cle, sup] of [['pe', 0], ['di', 1]]) {
      const s = await ecranDe(page, suivi, testInfo, comptesRole[cle])
      for (const passe of (cle === 'pe' ? PASSES : [''])) {
        const lu = reponse(s.p, PRIX_FOURN(oc.produit))
        const form = await ficheEdition(s, oc.nom, passe)
        expect((await lu).status(), `${passe}${s.c.nomRole} fiche : prix fournisseurs lus`).toBe(200)
        const tr = sectionPrix(form).locator('tr').filter({ hasText: oc.lignes[0].nom })
        await expect(tr, `${passe}${s.c.nomRole} fiche : ligne du prix fournisseur affichée`).toBeVisible(V)
        await expect(tr.getByRole('button', { name: 'Modifier le prix' }), `${passe}${s.c.nomRole} fiche : « Modifier le prix »`).toHaveCount(1)
        await expect(tr.getByRole('button', { name: 'Supprimer' }), `${passe}${s.c.nomRole} fiche : « Supprimer » ${sup ? 'présent' : 'absent'}`).toHaveCount(sup)
        expect(refus(s.reseau), `${passe}${s.c.nomRole} fiche : aucune réponse refusée`).toEqual([])
      }
    }
  } finally {
    for (const o of crees) await nettoyerProduit(o)
  }
})

// ───────────────────────── Reporting ─────────────────────────
const DASHBOARD = /^\/reporting\/dashboard\/$/
const KPI = /^\/reporting\/reports\/kpi-federes\/$/
const exporter = (p) => p.getByRole('button', { name: /Exporter Excel/ })

// ── PF4.3 — ADRG145 : /reporting ne demande le tableau de bord qu'avec la lecture des ventes ──────────────────────
etape('PF4.3-ADRG145-reporting', ['ADRG145'], async ({ page, suivi, testInfo }) => {
  const rh = await compteDe('Admin RH', 'adrg145rh')
  const di = await compteDe('Directeur', 'adrg145di')
  expect([rh.codes.includes('reporting_voir'), rh.codes.some((c) => c.startsWith('ventes_')), rh.codes.includes('reporting_export')],
    'Given : Admin RH reporting_voir, aucun code ventes_*, sans reporting_export').toEqual([true, false, false])
  const s = await ecranDe(page, suivi, testInfo, rh)
  for (const passe of PASSES) {
    const kpi = reponse(s.p, KPI, 'GET', (u) => !u.searchParams.get('vue'))
    await charger(s, '/reporting', passe)
    const rep = await kpi
    expect(rep.status(), `${passe}Admin RH : KPI fédérés lus`).toBe(200)
    const tuiles = (await rep.json())?.tuiles || []
    await expect(s.p.getByText('Accès refusé (403)'), `${passe}Admin RH : /reporting atteint (pas l'écran de refus)`).toHaveCount(0)
    await expect(s.p.getByText('Tableau réservé aux rôles des ventes'), `${passe}Admin RH : message « tableau réservé »`).toBeVisible(V)
    await expect(exporter(s.p), `${passe}Admin RH : aucun bouton « Exporter Excel »`).toHaveCount(0)
    if (tuiles.length) await expect(s.p.getByText('KPI fédérés').first(), `${passe}Admin RH : carte des KPI fédérés (${tuiles.length} tuiles)`).toBeVisible(V)
    console.log(`[ADRG145] ${passe}Admin RH /reporting (${tuiles.length} tuiles) : ${J(s.reseau)}`)
    expect(appels(s.reseau, DASHBOARD), `${passe}Admin RH : aucun appel reporting/dashboard/`).toEqual([])
    expect(refus(s.reseau), `${passe}Admin RH : aucune réponse refusée (aucune 403)`).toEqual([])
  }
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const tableau = reponse(d.p, DASHBOARD)
    await charger(d, '/reporting', passe)
    expect((await tableau).status(), `${passe}Directeur : tableau de bord servi`).toBe(200)
    await expect(exporter(d.p).first(), `${passe}Directeur : bouton « Exporter Excel »`).toBeVisible(V)
    await expect(bouton(d.p, /Actualiser/).first(), `${passe}Directeur : tableau rendu`).toBeVisible(V)
    await expect(d.p.getByText('Tableau réservé aux rôles des ventes'), `${passe}Directeur : pas de message « réservé »`).toHaveCount(0)
    expect(refus(d.reseau), `${passe}Directeur : aucune réponse refusée`).toEqual([])
  }
})

// ── PF4.3 — ADRG73 : export Excel du tableau de bord sous `reporting_export` (route + bouton de /reporting) ──────
etape('PF4.3-ADRG73-export', ['ADRG73'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const co = await compteDe('Commercial', 'adrg73co')
  const cr = await compteDe('Commercial responsable', 'adrg73cr')
  const rh = await compteDe('Admin RH', 'adrg73rh')
  const pePk = await rolePersonnalise('Admin RH', ['ventes_voir'], `Admin RH + ventes_voir ADRG73 ${m}`)
  const pe = await compteDe('Admin RH + ventes_voir', 'adrg73pe', pePk)
  expect(co.codes.includes('reporting_export'), 'Given : Commercial sans reporting_export').toBe(false)
  expect(cr.codes.includes('reporting_export'), 'Given : Commercial responsable avec reporting_export').toBe(true)
  expect([rh.codes.includes('reporting_export'), pe.codes.includes('reporting_export'), pe.codes.includes('ventes_voir')],
    'Given : Admin RH et Admin RH + ventes_voir sans reporting_export').toEqual([false, false, true])
  // Route : Commercial 403 `droit_manquant` nommant reporting_export sur l'export, 200 sur le JSON.
  const aco = await apiDe(testInfo, co)
  await refusNomme(await aco.get(`${API}/reporting/dashboard/?export=xlsx`, T), 'reporting_export', 'Commercial export xlsx')
  expect((await aco.get(`${API}/reporting/dashboard/`, T)).status(), 'Commercial : JSON 200').toBe(200)
  // Même refus pour le rôle qui lit les ventes sans le code d'export (tableau 200).
  const ape = await apiDe(testInfo, pe)
  await refusNomme(await ape.get(`${API}/reporting/dashboard/?export=xlsx`, T), 'reporting_export', 'Admin RH + ventes_voir export xlsx')
  expect((await ape.get(`${API}/reporting/dashboard/`, T)).status(), 'Admin RH + ventes_voir : JSON 200').toBe(200)
  // Commercial responsable : un classeur PK….
  const acr = await apiDe(testInfo, cr)
  const x = await acr.get(`${API}/reporting/dashboard/?export=xlsx`, T)
  expect(x.status(), 'Commercial responsable : export 200').toBe(200)
  expect((await x.body()).subarray(0, 2).toString(), 'classeur PK…').toBe('PK')
  // Écran /reporting, rôle qui ATTEINT l'écran sans reporting_export (Admin RH, ADRG145) : pas de bouton, aucune 403.
  const s = await ecranDe(page, suivi, testInfo, rh)
  for (const passe of PASSES) {
    await charger(s, '/reporting', passe)
    await expect(s.p.getByText('Accès refusé (403)'), `${passe}Admin RH : /reporting atteint`).toHaveCount(0)
    await expect(s.p.getByText('Reporting & Analytics').first(), `${passe}Admin RH : écran Reporting rendu`).toBeVisible(V)
    await expect(exporter(s.p), `${passe}Admin RH : aucun bouton « Exporter Excel »`).toHaveCount(0)
    console.log(`[ADRG73] ${passe}Admin RH /reporting : ${J(s.reseau)}`)
    expect(refus(s.reseau), `${passe}Admin RH : aucune réponse refusée (aucune 403)`).toEqual([])
  }
  // Écran /reporting, tableau CHARGÉ mais sans reporting_export (Admin RH + ventes_voir) : seul le code d'export
  // décide du bouton.
  const t = await ecranDe(page, suivi, testInfo, pe)
  for (const passe of PASSES) {
    const tableau = reponse(t.p, DASHBOARD)
    await charger(t, '/reporting', passe)
    expect((await tableau).status(), `${passe}Admin RH + ventes_voir : tableau de bord servi`).toBe(200)
    await expect(bouton(t.p, /Actualiser/).first(), `${passe}Admin RH + ventes_voir : tableau rendu`).toBeVisible(V)
    await expect(exporter(t.p), `${passe}Admin RH + ventes_voir : aucun bouton « Exporter Excel »`).toHaveCount(0)
    console.log(`[ADRG73] ${passe}Admin RH + ventes_voir /reporting : ${J(t.reseau)}`)
    expect(appels(t.reseau, DASHBOARD).filter((l) => l.includes('export=')), `${passe}Admin RH + ventes_voir : aucun export demandé`).toEqual([])
    expect(refus(t.reseau), `${passe}Admin RH + ventes_voir : aucune réponse refusée`).toEqual([])
  }
  // Commercial responsable : bouton présent, et il télécharge le classeur (GET ?export=xlsx → 200).
  const r = await ecranDe(page, suivi, testInfo, cr)
  for (const passe of PASSES) {
    const tableau = reponse(r.p, DASHBOARD)
    await charger(r, '/reporting', passe)
    expect((await tableau).status(), `${passe}Commercial responsable : tableau de bord servi`).toBe(200)
    await expect(exporter(r.p).first(), `${passe}Commercial responsable : bouton « Exporter Excel »`).toBeVisible(V)
  }
  const [exp] = await Promise.all([
    reponse(r.p, DASHBOARD, 'GET', (u) => u.searchParams.get('export') === 'xlsx'),
    exporter(r.p).first().click(),
  ])
  expect(exp.status(), 'Commercial responsable : export depuis l\'écran').toBe(200)
})

// ── PF4.4 — ADRG144 : badges de l'accueil /apps demandés seulement aux rôles qui lisent le module reporting ───────
etape('PF4.4-ADRG144-badges', ['ADRG144'], async ({ page, suivi, testInfo }) => {
  const ct = await compteDe('Commercial terrain', 'adrg144ct')
  const vi = await compteDe('Viewer', 'adrg144vi')
  const di = await compteDe('Directeur', 'adrg144di')
  expect(ct.codes.some((c) => c.startsWith('reporting_')), `Given : Commercial terrain sans code reporting_* ${J(ct.codes)}`).toBe(false)
  expect(vi.codes.every((c) => c.endsWith('_voir') || c.endsWith('_view') || c.startsWith('records_scope')), 'Given : Viewer lecture seule').toBe(true)
  for (const c of [ct, vi]) {
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of PASSES) {
      await charger(s, '/apps', passe)
      await expect(s.p.locator('.home-menu-cell').first(), `${passe}${c.nomRole} /apps : tuiles rendues`).toBeVisible(V)
      await calme(s.p)
      console.log(`[ADRG144] ${passe}${c.nomRole} /apps : ${J(s.reseau)}`)
      expect(appels(s.reseau, KPI), `${passe}${c.nomRole} : aucun appel reporting/reports/kpi-federes/`).toEqual([])
      await expect(s.p.locator('.home-menu-tile-badge'), `${passe}${c.nomRole} : tuiles sans badge`).toHaveCount(0)
      expect(refus(s.reseau), `${passe}${c.nomRole} /apps : aucune réponse refusée (aucune 403)`).toEqual([])
    }
  }
  // Directeur : badges lus (200) et posés sur les tuiles de leurs apps.
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    const lu = reponse(d.p, KPI, 'GET', (u) => u.searchParams.get('vue') === 'badges')
    await charger(d, '/apps', passe)
    const rep = await lu
    expect(rep.status(), `${passe}Directeur : badges lus`).toBe(200)
    const badges = ((await rep.json())?.badges || []).filter((b) => b?.app && typeof b.valeur === 'number')
    await expect(d.p.locator('.home-menu-cell').first(), `${passe}Directeur /apps : tuiles rendues`).toBeVisible(V)
    const poses = []
    for (const b of badges) {
      const tuile = d.p.locator(`.home-menu-cell[data-app="${b.app}"]`)
      if (!(await tuile.count())) continue
      await expect(tuile.locator('.home-menu-tile-badge'), `${passe}Directeur : badge de ${b.app}`).toContainText(String(b.valeur))
      poses.push(b.app)
    }
    console.log(`[ADRG144] ${passe}Directeur badges ${J(badges)} posés sur ${J(poses)}`)
    expect(poses.length, `${passe}Directeur : au moins un badge posé sur une tuile ${J(badges)}`).toBeGreaterThan(0)
    expect(refus(d.reseau), `${passe}Directeur /apps : aucune réponse refusée`).toEqual([])
  }
})

// ───────────────────────── GED ─────────────────────────
const PDF = Buffer.from('%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n')

/** Armoire + dossier + document PDF (une version) par demo_admin. */
async function dossierGed(r, m, prefixe) {
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab ${prefixe} ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos ${prefixe} ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Plan ${prefixe} ${m}`, folder: dos.id } }), 'document')
  await lireJson(await r.post(`${GED}/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: { name: 'plan.pdf', mimeType: 'application/pdf', buffer: PDF } } }), 'version PDF')
  return { cab, dos, doc }
}

/** Ouvre /ged, choisit l'armoire (sélecteur présent dès 2 armoires) puis le dossier ; attend la ligne du document. */
async function ouvrirDossierGed(p, { cab, dos, doc }) {
  await p.goto('/ged')
  const choix = p.getByRole('combobox', { name: 'Choisir le cabinet' })
  await expect(p.getByRole('tree', { name: 'Dossiers' }).or(choix).first()).toBeVisible(V)
  if (await choix.count()) {
    await choix.click()
    await p.getByRole('option', { name: cab.nom, exact: true }).click()
  }
  await p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
  await expect(p.getByRole('button', { name: `Aperçu de ${doc.nom}` }), 'document listé').toBeVisible(V)
}
const USERS_ROLES = /^\/(auth\/)?(users|roles)\/$/
const TIMELINE = (id) => new RegExp(`^/ged/documents/${id}/timeline/$`)
const EFFECTIFS = (id) => new RegExp(`^/ged/documents/${id}/permissions-effectives/$`)

// ── PF4.2 — ADRG143 : panneau d'un document GED sans users/ ni roles/ hors `ged_gouvernance` ────────────────────
etape('PF4.2-ADRG143-panneau-document', ['ADRG143'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const g = await dossierGed(page.request, m, 'ADRG143')
  const co = await compteDe('Commercial', 'adrg143co')
  const di = await compteDe('Directeur', 'adrg143di')
  expect([co.codes.includes('ged_voir'), co.codes.includes('ged_gouvernance')], 'Given : Commercial ged_voir sans ged_gouvernance').toEqual([true, false])
  expect(di.codes.includes('ged_gouvernance'), 'Given : Directeur avec ged_gouvernance').toBe(true)
  // Commercial : panneau « Détails » (Timeline + Accès) lu, aucun appel users/ ni roles/, console propre.
  const s = await ecranDe(page, suivi, testInfo, co)
  for (const passe of PASSES) {
    s.reseau.length = 0
    s.consoles.length = 0
    await ouvrirDossierGed(s.p, g)
    const tl = reponse(s.p, TIMELINE(g.doc.id))
    const ef = reponse(s.p, EFFECTIFS(g.doc.id))
    await bouton(s.p, `Détails de ${g.doc.nom}`).click()
    expect((await tl).status(), `${passe}Commercial : chronologie lue`).toBe(200)
    expect((await ef).status(), `${passe}Commercial : accès effectifs lus`).toBe(200)
    const panneau = s.p.getByRole('dialog').filter({ hasText: g.doc.nom })
    await expect(panneau.getByTestId('ged-timeline').or(panneau.getByText('Aucune activité')).first(), `${passe}Commercial : chronologie affichée`).toBeVisible(V)
    await panneau.getByRole('tab', { name: /Accès/ }).click()
    await expect(panneau.getByTestId('ged-acl').or(panneau.getByText("Aucune règle d'accès")).first(), `${passe}Commercial : accès effectifs affichés`).toBeVisible(V)
    await expect(panneau.getByText(/Gérer les droits d.accès/), `${passe}Commercial : rubrique des droits d'accès`).toBeVisible(V)
    await expect(panneau.getByRole('combobox', { name: 'Type de principal' }), `${passe}Commercial : pas d'éditeur d'accès`).toHaveCount(0)
    await calme(s.p)
    console.log(`[ADRG143] ${passe}Commercial fiche document : ${J(s.reseau)} ; console ${J(s.consoles)}`)
    expect(appels(s.reseau, USERS_ROLES), `${passe}Commercial : aucun GET users/ ni roles/`).toEqual([])
    expect(refus(s.reseau), `${passe}Commercial : aucune réponse refusée (aucune 403)`).toEqual([])
    expect(s.consoles, `${passe}Commercial : console sans erreur`).toEqual([])
    await s.p.keyboard.press('Escape')
  }
  // Directeur : l'éditeur d'accès avec ses listes d'utilisateurs (le Commercial y figure) et de rôles.
  const d = await ecranDe(page, suivi, testInfo, di)
  for (const passe of PASSES) {
    d.reseau.length = 0
    await ouvrirDossierGed(d.p, g)
    const us = reponse(d.p, /^\/(auth\/)?users\/$/)
    const ro = reponse(d.p, /^\/(auth\/)?roles\/$/)
    await bouton(d.p, `Détails de ${g.doc.nom}`).click()
    expect((await us).status(), `${passe}Directeur : utilisateurs lus`).toBe(200)
    expect((await ro).status(), `${passe}Directeur : rôles lus`).toBe(200)
    const panneau = d.p.getByRole('dialog').filter({ hasText: g.doc.nom })
    await panneau.getByRole('tab', { name: /Accès/ }).click()
    await expect(panneau.getByRole('combobox', { name: 'Type de principal' }), `${passe}Directeur : éditeur d'accès`).toBeVisible(V)
    await panneau.getByRole('combobox', { name: 'Choisir un utilisateur' }).click()
    await expect(d.p.getByRole('option', { name: co.username, exact: true }), `${passe}Directeur : liste des utilisateurs remplie`).toBeVisible(V)
    await d.p.keyboard.press('Escape')
    await panneau.getByRole('combobox', { name: 'Type de principal' }).click()
    await d.p.getByRole('option', { name: 'Rôle', exact: true }).click()
    await panneau.getByRole('combobox', { name: 'Choisir un rôle' }).click()
    await expect(d.p.getByRole('option', { name: 'Commercial', exact: true }), `${passe}Directeur : liste des rôles remplie`).toBeVisible(V)
    await d.p.keyboard.press('Escape')
    expect(refus(d.reseau), `${passe}Directeur : aucune réponse refusée`).toEqual([])
    await d.p.keyboard.press('Escape')
  }
})

// ── PF4.2 — ADRG80 : ACL, règles d'ACL par métadonnée et tampons sous `ged_gouvernance` ───────────────────────
etape('PF4.2-ADRG80-ged-gouvernance', ['ADRG80'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const g = await dossierGed(r, m, 'ADRG80')
  const co = await compteDe('Commercial', 'adrg80co')
  const di = await compteDe('Directeur', 'adrg80di')
  expect(co.codes.includes('ged_gouvernance'), 'Given : Commercial sans ged_gouvernance').toBe(false)
  expect(di.codes.includes('ged_gouvernance'), 'Given : Directeur avec ged_gouvernance').toBe(true)
  const rolePk = await py(`from apps.roles.models import Role
sortie(Role.objects.get(company_id=${SOC}, nom='Viewer', est_systeme=True).pk)`)
  const tampon = `ADRG80 ${m}`
  const nomRegle = `Règle ADRG80 ${m}`
  const corps = {
    'acls/': { document: g.doc.id, utilisateur: co.id, niveau: 'lecture' },
    'regles-acl-metadonnee/': { nom: nomRegle, role: rolePk, niveau: 'lecture',
      condition_group: { op: 'and', conditions: [{ field: 'type', operator: 'eq', value: `adrg80-${m}` }] } },
    'tampons-societe/': { libelle: tampon },
  }
  const compter = () => py(`from apps.ged.models import AclGed, RegleAclMetadonnee, TamponSociete
sortie([AclGed.objects.filter(document_id=${g.doc.id}).count(), RegleAclMetadonnee.objects.filter(nom=${J(nomRegle)}).count(), TamponSociete.objects.filter(libelle=${J(tampon)}).count()])`)
  try {
    // Route : Commercial 403 aux trois écritures, lectures 200 ; persistance : rien créé.
    const aco = await apiDe(testInfo, co)
    for (const [route, body] of Object.entries(corps)) {
      const x = await aco.post(`${API}/ged/${route}`, { ...T, data: body })
      expect(x.status(), `Commercial POST ${route} : ${(await x.text()).slice(0, 200)}`).toBe(403)
      expect((await aco.get(`${API}/ged/${route}`, T)).status(), `Commercial GET ${route} (lecture inchangée)`).toBe(200)
    }
    expect(await compter(), 'persistance : rien créé par le Commercial').toEqual([0, 0, 0])
    // Écrans : /ged/regles-acl (Commercial : écran de refus de l'application, aucune saisie ; Directeur : écran des
    // règles avec « Nouvelle règle ») et la fiche document (onglet Accès : saisie d'un droit au seul Directeur),
    // sans aucune réponse refusée ; relus après rechargement.
    for (const [c, gouv] of [[co, false], [di, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        const regles = gouv ? reponse(s.p, /^\/ged\/regles-acl-metadonnee\/$/) : null
        await charger(s, '/ged/regles-acl', passe)
        if (gouv) {
          expect((await regles).status(), `${passe}${c.nomRole} : règles lues`).toBe(200)
          await expect(s.p.getByText("Règles d'accès par métadonnée").first(), `${passe}${c.nomRole} : écran des règles`).toBeVisible(V)
        } else {
          await expect(s.p.getByText('Accès refusé (403)').first(), `${passe}${c.nomRole} /ged/regles-acl : écran de refus`).toBeVisible(V)
        }
        await calme(s.p)
        console.log(`[ADRG80] ${passe}${c.nomRole} /ged/regles-acl → ${s.p.url()} : ${J(s.reseau)}`)
        await expect(bouton(s.p, /Nouvelle règle/), `${passe}${c.nomRole} : « Nouvelle règle »`).toHaveCount(gouv ? 1 : 0)
        expect(refus(s.reseau), `${passe}${c.nomRole} /ged/regles-acl : aucune réponse refusée`).toEqual([])
      }
      for (const passe of PASSES) {
        s.reseau.length = 0
        await ouvrirDossierGed(s.p, g)
        await bouton(s.p, `Détails de ${g.doc.nom}`).click()
        const panneau = s.p.getByRole('dialog').filter({ hasText: g.doc.nom })
        await panneau.getByRole('tab', { name: /Accès/ }).click()
        await expect(panneau.getByText(/Gérer les droits d.accès/).first(), `${passe}${c.nomRole} : fiche document (droits d'accès)`).toBeVisible(V)
        await calme(s.p)
        await expect(panneau.getByRole('combobox', { name: 'Type de principal' }), `${passe}${c.nomRole} : saisie d'un droit d'accès`).toHaveCount(gouv ? 1 : 0)
        await expect(panneau.getByRole('button', { name: 'Ajouter', exact: true }), `${passe}${c.nomRole} : bouton « Ajouter » un droit`).toHaveCount(gouv ? 1 : 0)
        console.log(`[ADRG80] ${passe}${c.nomRole} fiche document : ${J(s.reseau)}`)
        expect(refus(s.reseau), `${passe}${c.nomRole} fiche document : aucune réponse refusée`).toEqual([])
        await s.p.keyboard.press('Escape')
      }
    }
    // Témoin Directeur : 201 aux trois ; relu : une ligne de chaque.
    const adi = await apiDe(testInfo, di)
    for (const [route, body] of Object.entries(corps)) {
      const x = await adi.post(`${API}/ged/${route}`, { ...T, data: body })
      expect(x.status(), `Directeur POST ${route} : ${(await x.text()).slice(0, 200)}`).toBe(201)
    }
    expect(await compter(), 'relu : une ligne de chaque créée par le Directeur').toEqual([1, 1, 1])
  } finally {
    await py(`from apps.ged.models import AclGed, RegleAclMetadonnee, TamponSociete
AclGed.objects.filter(document_id=${g.doc.id}).delete()
RegleAclMetadonnee.objects.filter(nom=${J(nomRegle)}).delete()
TamponSociete.objects.filter(libelle=${J(tampon)}).delete()
sortie(1)`).catch(() => null)
  }
})
