// Preuves en direct du groupe ADRG, lot 12 (vague d'acceptation 6, runner GitHub) : GED, chantiers, stock,
// facturation, SAV et fiche lead — ADRG75, 80, 99, 106, 107, 108, 114, 115, 116, 117, 121.
// Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo ; un seul rôle
// PERSONNALISÉ, celui qu'ADRG107 nomme : `stock_voir` + `stock_modifier`), connectés par la vraie route `/token/` dans
// un navigateur à part ; chaque réponse de l'API est relevée (« onglet réseau ») pour affirmer les clauses « aucune
// requête 403 ». Données propres créées par l'API de demo_admin ou le shell Django, retirées en fin d'étape ; clause
// de persistance = relecture en base ou par l'API, écran relu après rechargement.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { connexionApi, assurerSessionPage, lireJson, telephoneMobileUnique, isoDansJours } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG75', 'ADRG80', 'ADRG99', 'ADRG106', 'ADRG107', 'ADRG108', 'ADRG114', 'ADRG115',
  'ADRG116', 'ADRG117', 'ADRG121'])
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
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` (ou du rôle de pk `rolePk`) ; {username, id, nomRole, codes}. */
async function compteDe(nomRole, prefixe, rolePk = null) {
  const username = `${prefixe}_${marque()}`
  const x = await py(`from apps.roles.models import Role
r = Role.objects.get(pk=${rolePk}) if ${rolePk ? 'True' : 'False'} else Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
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
 *  réponse de l'API relevée dans `reseau`. La page demo_admin de l'étape est refermée (capture = écran du rôle). */
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
      for (const [k, v] of Object.entries(extra)) localStorage.setItem(k, v)
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
  p.on('response', (r) => {
    const u = new URL(r.url())
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)}${u.search} → ${r.status()}`)
  })
  return { ctx, p, reseau, api: ctx.request, c }
}
const chemin = (l) => l.split(' ')[1].split('?')[0]
const appels = (reseau, re) => reseau.filter((l) => re.test(chemin(l)))
const refus = (reseau) => reseau.filter((l) => / → [45]\d\d$/.test(l))
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
const reponse = (p, re, methode = 'GET') => p.waitForResponse((r) => re.test(new URL(r.url()).pathname.slice(API.length)) && r.request().method() === methode, T)
async function charger(s, url, passe) {
  s.reseau.length = 0
  if (passe) await s.p.reload(); else await s.p.goto(url)
  await calme(s.p)
}
const PASSES = ['', 'relu après rechargement : ']
const bouton = (zone, nom) => zone.getByRole('button', { name: nom })

/** Libellés des entrées du menu ouvert (Radix) ; menu refermé ensuite. Menu vide toléré (aucune entrée). */
async function entreesMenu(p) {
  const menu = p.getByRole('menu')
  await menu.first().waitFor({ state: 'visible', timeout: 15_000 }).catch(() => undefined)
  const textes = (await menu.getByRole('menuitem').allInnerTexts().catch(() => [])).map((x) => x.replace(/\s+/g, ' ').trim())
  await p.keyboard.press('Escape')
  return textes
}

/** 403 qui NOMME le code manquant. */
async function refusNomme(res, code, quoi) {
  const corps = await res.text()
  expect(res.status(), `${quoi} : ${corps.slice(0, 240)}`).toBe(403)
  expect(corps, `${quoi} : le refus nomme ${code}`).toContain(code)
}

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

// ── PF4.2 — ADRG75 : extraire / verrouiller un document sous `ged_gerer` ─────────────────────────────────────
etape('PF4.2-ADRG75', ['ADRG75'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const g = await dossierGed(r, m, 'ADRG75')
  const nom = g.doc.nom
  const vi = await compteDe('Viewer', 'adrg75vi')
  const te = await compteDe('Technicien', 'adrg75te')
  expect(vi.codes.includes('ged_gerer'), 'Given : Viewer sans ged_gerer').toBe(false)
  expect(te.codes.includes('ged_gerer'), 'Given : Technicien avec ged_gerer').toBe(true)
  // Écran /ged : boutons « Extraire » et « Verrouiller (avertissement) » selon le droit (relu après rechargement).
  for (const [c, gere] of [[vi, false], [te, true]]) {
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of PASSES) {
      s.reseau.length = 0
      await ouvrirDossierGed(s.p, g)
      await calme(s.p)
      await expect(bouton(s.p, `Extraire ${nom}`), `${passe}${c.nomRole} : « Extraire »`).toHaveCount(gere ? 1 : 0)
      await bouton(s.p, `Plus d'actions pour ${nom}`).click()
      const menu = await entreesMenu(s.p)
      expect(menu.some((x) => /^Verrouiller \(avertissement\)/.test(x)), `${passe}${c.nomRole} : « Verrouiller (avertissement) » ${J(menu)}`).toBe(gere)
      expect(refus(s.reseau), `${passe}${c.nomRole} : aucune réponse refusée sur /ged`).toEqual([])
    }
  }
  // Route : Viewer 403 aux deux poses ; persistance : document ni extrait ni verrouillé.
  const avi = await apiDe(testInfo, vi)
  const ate = await apiDe(testInfo, te)
  const DOC = `${API}/ged/documents/${g.doc.id}`
  for (const geste of ['check-out', 'verrouiller']) {
    const x = await avi.post(`${DOC}/${geste}/`, { ...T, data: {} })
    expect(x.status(), `Viewer ${geste} : ${(await x.text()).slice(0, 200)}`).toBe(403)
  }
  const relu = await lireJson(await r.get(`${DOC}/`, T), 'document relu')
  expect([relu.is_locked, relu.est_verrouille_avertissement], 'persistance : ni extrait ni verrouillé après les refus').toEqual([false, false])
  // Libérer reste ouvert au Viewer (idempotent sur un document libre).
  for (const geste of ['check-in', 'deverrouiller']) {
    const x = await avi.post(`${DOC}/${geste}/`, { ...T, data: {} })
    expect(x.status(), `Viewer ${geste} (libérer) : ${(await x.text()).slice(0, 200)}`).toBe(200)
  }
  // Témoin Technicien : 200 aux deux poses, puis il libère ses propres verrous (200).
  for (const [pose, leve, champ] of [['check-out', 'check-in', 'is_locked'], ['verrouiller', 'deverrouiller', 'est_verrouille_avertissement']]) {
    const x = await ate.post(`${DOC}/${pose}/`, { ...T, data: {} })
    expect(x.status(), `Technicien ${pose} : ${(await x.text()).slice(0, 200)}`).toBe(200)
    expect((await lireJson(await r.get(`${DOC}/`, T), 'relu'))[champ], `relu : ${champ} posé par le Technicien`).toBe(true)
    const y = await ate.post(`${DOC}/${leve}/`, { ...T, data: {} })
    expect(y.status(), `Technicien ${leve} : ${(await y.text()).slice(0, 200)}`).toBe(200)
    expect((await lireJson(await r.get(`${DOC}/`, T), 'relu'))[champ], `relu : ${champ} levé`).toBe(false)
  }
})

// ── PF4.2 — ADRG80 : ACL, règles d'ACL par métadonnée et tampons sous `ged_gouvernance` ───────────────────────
etape('PF4.2-ADRG80', ['ADRG80'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const g = await dossierGed(r, m, 'ADRG80')
  const co = await compteDe('Commercial', 'adrg80co')
  const di = await compteDe('Directeur', 'adrg80di')
  expect(co.codes.includes('ged_gouvernance'), 'Given : Commercial sans ged_gouvernance').toBe(false)
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
    const aco = await apiDe(testInfo, co)
    for (const [route, body] of Object.entries(corps)) {
      const x = await aco.post(`${API}/ged/${route}`, { ...T, data: body })
      expect(x.status(), `Commercial POST ${route} : ${(await x.text()).slice(0, 200)}`).toBe(403)
      expect((await aco.get(`${API}/ged/${route}`, T)).status(), `Commercial GET ${route} (lecture inchangée)`).toBe(200)
    }
    expect(await compter(), 'persistance : rien créé par le Commercial').toEqual([0, 0, 0])
    // Écrans au Commercial : /ged/regles-acl sans « Nouvelle règle », fiche document sans saisie de droit d'accès.
    for (const [c, gouv] of [[co, false], [di, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        const regles = gouv ? reponse(s.p, /^\/ged\/regles-acl-metadonnee\/$/) : null
        s.reseau.length = 0
        if (passe) await s.p.reload(); else await s.p.goto('/ged/regles-acl')
        if (gouv) {
          expect((await regles).status(), `${passe}${c.nomRole} : règles lues`).toBe(200)
          await expect(s.p.getByText("Règles d'accès par métadonnée").first(), `${passe}${c.nomRole} : écran des règles`).toBeVisible(V)
        } else {
          // Le Commercial (palier normal) n'entre pas sur l'écran des règles (route GED avancée) : écran de refus de
          // l'application, aucune saisie de règle.
          await expect(s.p.getByText('Accès refusé (403)').first(), `${passe}${c.nomRole} /ged/regles-acl : écran de refus`).toBeVisible(V)
        }
        await calme(s.p)
        console.log(`[ADRG80] ${passe}${c.nomRole} /ged/regles-acl → ${s.p.url()} : ${J(s.reseau)}`)
        await expect(bouton(s.p, /Nouvelle règle/), `${passe}${c.nomRole} : « Nouvelle règle »`).toHaveCount(gouv ? 1 : 0)
        expect(refus(s.reseau), `${passe}${c.nomRole} : aucune réponse refusée`).toEqual([])
      }
      s.reseau.length = 0
      await ouvrirDossierGed(s.p, g)
      await bouton(s.p, `Détails de ${g.doc.nom}`).click()
      await expect(s.p.getByText(/Gérer les droits d.accès/).first(), `${c.nomRole} : fiche document (droits d'accès)`).toBeVisible(V)
      await calme(s.p)
      await expect(s.p.getByRole('combobox', { name: 'Type de principal' }), `${c.nomRole} : saisie d'un droit d'accès`).toHaveCount(gouv ? 1 : 0)
      expect(refus(s.reseau), `${c.nomRole} fiche document : aucune réponse refusée`).toEqual([])
    }
    // Témoin Directeur : 201 aux trois.
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

// ───────────────────────── Chantiers ─────────────────────────

// ── PF4.2 — ADRG99 : (ré)affecter le technicien responsable sous `technicien_assign` (route, Kanban, liste) ─────
etape('PF4.2-ADRG99', ['ADRG99'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const tr = await compteDe('Technicien responsable', 'adrg99tr')
  const te = await compteDe('Technicien', 'adrg99te')
  const te2 = await compteDe('Technicien', 'adrg99tf')
  expect(te.codes.includes('technicien_assign'), 'Given : Technicien sans technicien_assign').toBe(false)
  await py(`U.objects.filter(pk__in=[${te.id}, ${te2.id}]).update(supervisor_id=${tr.id})
sortie(1)`)
  const ids = await py(`from apps.installations.models import Installation
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG99-${m}', statut='planifie', technicien_responsable_id=${te.id})
sortie(dict(chantier=i.pk, ref=i.reference))`)
  const relu = () => py(`from apps.installations.models import Installation
from apps.notifications.models import Notification
i = Installation.objects.get(pk=${ids.chantier})
sortie([i.technicien_responsable_id, i.acces_instructions, Notification.objects.filter(recipient_id=${te2.id}).count()])`)
  const URL_CH = `${API}/installations/chantiers/${ids.chantier}/`
  try {
    const ate = await apiDe(testInfo, te)
    const notifAvant = (await relu())[2]
    await refusNomme(await ate.patch(URL_CH, { ...T, data: { technicien_responsable: te2.id } }), 'technicien_assign', 'Technicien réaffecte')
    const apres = await relu()
    expect(apres[0], 'persistance : titulaire inchangé').toBe(te.id)
    expect(apres[2], 'aucune notification au collègue').toBe(notifAvant)
    const acces = `Portail bleu ${m}`
    const ok = await ate.patch(URL_CH, { ...T, data: { acces_instructions: acces } })
    expect(ok.status(), `Technicien modifie l'accès : ${(await ok.text()).slice(0, 200)}`).toBe(200)
    expect((await relu()).slice(0, 2), 'relu : accès modifié, titulaire inchangé').toEqual([te.id, acces])
    // Écran Chantiers : Kanban (sélecteur « Installateur ») puis liste (action groupée « Réassigner l'installateur »).
    for (const [c, assigne] of [[te, false], [tr, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c, { 'taqinor.chantiers.view': 'kanban' })
      for (const passe of PASSES) {
        await charger(s, '/chantiers', passe)
        await expect(s.p.getByText(ids.ref).first(), `${passe}${c.nomRole} Kanban : carte du chantier`).toBeVisible(V)
        const sel = s.p.getByRole('combobox', { name: 'Installateur' })
        if (assigne) await expect(sel.first(), `${passe}${c.nomRole} Kanban : sélecteur « Installateur »`).toBeVisible(V)
        else await expect(sel, `${passe}${c.nomRole} Kanban : aucun sélecteur « Installateur »`).toHaveCount(0)
        expect(refus(s.reseau), `${passe}${c.nomRole} Kanban : aucune réponse refusée`).toEqual([])
      }
      for (const passe of PASSES) {
        // Vue « Liste » choisie à l'écran (le script d'init du contexte remet « kanban » à chaque chargement).
        await charger(s, '/chantiers', passe)
        await s.p.getByRole('radio', { name: 'Liste', exact: true }).click()
        const ligne = s.p.getByRole('row').filter({ hasText: ids.ref }).first()
        await expect(ligne, `${passe}${c.nomRole} liste : ligne du chantier`).toBeVisible(V)
        await ligne.getByRole('checkbox').first().check()
        const barre = s.p.getByRole('region', { name: 'Actions en masse' }).first()
        await expect(bouton(barre, 'Changer le statut'), `${passe}${c.nomRole} liste : barre d'actions groupées`).toBeVisible(V)
        await expect(bouton(barre, "Réassigner l'installateur"), `${passe}${c.nomRole} liste : « Réassigner l'installateur »`).toHaveCount(assigne ? 1 : 0)
        expect(refus(s.reseau), `${passe}${c.nomRole} liste : aucune réponse refusée`).toEqual([])
      }
    }
    // Témoin : le Technicien responsable réaffecte (200, relu).
    const atr = await apiDe(testInfo, tr)
    const re = await atr.patch(URL_CH, { ...T, data: { technicien_responsable: te2.id } })
    expect(re.status(), `Technicien responsable réaffecte : ${(await re.text()).slice(0, 200)}`).toBe(200)
    expect((await relu())[0], 'relu : réaffecté').toBe(te2.id)
  } finally {
    await py(`from apps.installations.models import Installation
try:
    Installation.objects.filter(pk=${ids.chantier}).delete()
except Exception:
    Installation.objects.filter(pk=${ids.chantier}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

// ── PF4.4 — ADRG117 : types d'intervention de la fiche chantier lus seulement avec `intervention_gerer` ──────────
const TYPES_ITV = /^\/installations\/types-intervention\/$/
etape('PF4.4-ADRG117', ['ADRG117'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const co = await compteDe('Commercial', 'adrg117co')
  const te = await compteDe('Technicien', 'adrg117te')
  expect(co.codes.some((x) => x.startsWith('installation_')), 'Given : Commercial sans code installation_*').toBe(false)
  expect(te.codes.includes('intervention_gerer'), 'Given : Technicien avec intervention_gerer').toBe(true)
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG117 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg117${m}@example.invalid` } }), 'lead')
  const prod = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADRG117 ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
  const dv = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  // Chantier d'une vente du Commercial (il y entre par l'octroi `ventes_voir`) dont le Technicien est titulaire.
  const ids = await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
Devis.objects.filter(pk=${dv.id}).update(created_by_id=${co.id})
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG117-${m}', statut='installe', created_by_id=${co.id}, technicien_responsable_id=${te.id}, devis_id=${dv.id})
sortie(dict(chantier=i.pk, ref=i.reference))`)
  try {
    const s = await ecranDe(page, suivi, testInfo, co)
    for (const passe of PASSES) {
      await charger(s, `/chantiers?id=${ids.chantier}`, passe)
      const fiche = s.p.getByRole('dialog')
      await expect(fiche.getByText(`Chantier — ${ids.ref}`).first(), `${passe}Commercial : fiche du chantier de sa vente`).toBeVisible(V)
      await calme(s.p)
      console.log(`[ADRG117] ${passe}Commercial fiche chantier : ${J(s.reseau)}`)
      expect(appels(s.reseau, TYPES_ITV), `${passe}Commercial : aucun GET types-intervention/`).toEqual([])
      expect(refus(s.reseau), `${passe}Commercial : aucune réponse refusée`).toEqual([])
    }
    // Témoin Technicien : types lus (200) et proposés dans le champ « Type » du formulaire d'intervention.
    const t = await ecranDe(page, suivi, testInfo, te)
    const types = reponse(t.p, TYPES_ITV)
    await charger(t, `/chantiers?id=${ids.chantier}`, '')
    const rt = await types
    expect(rt.status(), 'Technicien : types d\'intervention lus').toBe(200)
    const corps = await rt.json()
    const lignes = Array.isArray(corps) ? corps : (corps.results ?? [])
    expect(lignes.length, 'Technicien : types gérés servis').toBeGreaterThan(0)
    const fiche = t.p.getByRole('dialog')
    await expect(fiche.getByText(`Chantier — ${ids.ref}`).first(), 'Technicien : fiche ouverte').toBeVisible(V)
    await fiche.getByRole('tab', { name: /Interventions/ }).first().click()
    const champ = fiche.locator('#iv-type')
    await champ.scrollIntoViewIfNeeded()
    await champ.click()
    await expect(t.p.getByRole('option', { name: lignes[0].libelle, exact: true }).first(),
      `Technicien : type géré « ${lignes[0].libelle} » proposé`).toBeVisible(V)
    await t.p.keyboard.press('Escape')
  } finally {
    await py(`from apps.installations.models import Installation
try:
    Installation.objects.filter(pk=${ids.chantier}).delete()
except Exception:
    Installation.objects.filter(pk=${ids.chantier}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── Stock ─────────────────────────

/** Ouvre le menu de ligne du produit `nom` au catalogue (recherche « Chercher partout… ») ; libellés du menu. */
async function menuProduit(s, nom) {
  await s.p.getByPlaceholder('Chercher partout…').fill(nom)
  const ligne = s.p.getByRole('row').filter({ hasText: nom }).first()
  await expect(ligne, `${s.c.nomRole} : produit listé`).toBeVisible(V)
  await bouton(ligne, "Plus d'actions sur la ligne").click()
  return entreesMenu(s.p)
}

// ── PF4.4 — ADRG106 : boutons « Supprimer » du stock selon `stock_supprimer` (ou administrateur) ────────────────
etape('PF4.4-ADRG106', ['ADRG106'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const av = await compteDe('Admin Ventes', 'adrg106av')
  const re = await compteDe('Responsable', 'adrg106re')
  expect(av.codes.includes('stock_supprimer'), 'Given : Admin Ventes avec stock_supprimer').toBe(true)
  expect([re.codes.includes('stock_modifier'), re.codes.includes('stock_supprimer')], 'Given : Responsable stock_modifier sans stock_supprimer').toEqual([true, false])
  const nomMarque = `Marque ADRG106 ${m}`
  const nomProduit = `Câble ADRG106 ${m}`
  const x = await py(`from apps.stock.models import Marque, Produit, Fournisseur, ContactFournisseur, DocumentConformiteFournisseur
co = ${SOC}
ma = Marque.objects.create(company_id=co, nom=${J(nomMarque)})
p = Produit.objects.create(company_id=co, nom=${J(nomProduit)}, prix_vente='100.00', prix_achat='60.00')
f = Fournisseur.objects.create(company_id=co, nom=${J(`Fournisseur ADRG106 ${m}`)})
ct = ContactFournisseur.objects.create(company_id=co, fournisseur=f, nom=${J(`Contact ADRG106 ${m}`)})
d = DocumentConformiteFournisseur.objects.create(company_id=co, fournisseur=f, reference=${J(`REF-ADRG106-${m}`)})
sortie(dict(marque=ma.pk, produit=p.pk, fournisseur=f.pk, contact=ct.pk, doc=d.pk))`)
  try {
    for (const [c, supprime] of [[re, false], [av, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        // Catégories & marques.
        await charger(s, '/stock/categories', passe)
        await expect(s.p.getByText('Marques produit').first(), `${passe}${c.nomRole} : écran catégories & marques`).toBeVisible(V)
        const ligneMarque = s.p.locator('div.flex.items-center').filter({ has: s.p.locator(`input[value="${nomMarque}"]`) }).last()
        await expect(ligneMarque, `${passe}${c.nomRole} : marque listée`).toBeVisible(V)
        await expect(bouton(ligneMarque, 'Supprimer la marque'), `${passe}${c.nomRole} : « Supprimer la marque »`).toHaveCount(supprime ? 1 : 0)
        if (supprime) await expect(bouton(s.p, 'Supprimer la catégorie').first(), `${passe}${c.nomRole} : « Supprimer la catégorie »`).toBeVisible(V)
        else await expect(bouton(s.p, 'Supprimer la catégorie'), `${passe}${c.nomRole} : aucun « Supprimer la catégorie »`).toHaveCount(0)
        expect(refus(s.reseau), `${passe}${c.nomRole} catégories : aucune réponse refusée`).toEqual([])
      }
      // Catalogue : « Supprimer » au menu de la ligne.
      await charger(s, '/stock', '')
      const menu = await menuProduit(s, nomProduit)
      expect(menu.some((t) => /^Supprimer$/.test(t)), `${c.nomRole} catalogue : « Supprimer » ${J(menu)}`).toBe(supprime)
      // Fiche 360 du fournisseur : contacts et pièces de conformité.
      await charger(s, `/stock/fournisseurs/${x.fournisseur}/360`, '')
      await s.p.getByRole('tab', { name: /Contacts/ }).click()
      const panneauC = s.p.getByRole('tabpanel')
      await expect(panneauC.getByText(`Contact ADRG106 ${m}`).first(), `${c.nomRole} : contact listé`).toBeVisible(V)
      await expect(bouton(panneauC, 'Supprimer'), `${c.nomRole} : « Supprimer » d'un contact`).toHaveCount(supprime ? 1 : 0)
      await s.p.getByRole('tab', { name: /Conformité/ }).click()
      const panneauD = s.p.getByRole('tabpanel')
      await expect(panneauD.getByText(`REF-ADRG106-${m}`).first(), `${c.nomRole} : pièce de conformité listée`).toBeVisible(V)
      await expect(bouton(panneauD, 'Supprimer la pièce'), `${c.nomRole} : « Supprimer la pièce »`).toHaveCount(supprime ? 1 : 0)
      await calme(s.p)
      expect(refus(s.reseau), `${c.nomRole} fiche 360 : aucune réponse refusée`).toEqual([])
      if (supprime) {
        // Preuve : l'Admin Ventes supprime la marque inutilisée ⇒ 204, disparue après rechargement.
        await charger(s, '/stock/categories', '')
        const ligneMarque = s.p.locator('div.flex.items-center').filter({ has: s.p.locator(`input[value="${nomMarque}"]`) }).last()
        await bouton(ligneMarque, 'Supprimer la marque').click()
        const dlg = s.p.getByRole('alertdialog').or(s.p.getByRole('dialog')).last()
        const [del] = await Promise.all([
          reponse(s.p, new RegExp(`^/stock/marques/${x.marque}/$`), 'DELETE'),
          bouton(dlg, 'Supprimer').click(),
        ])
        expect(del.status(), 'Admin Ventes : suppression de la marque').toBe(204)
        await s.p.reload()
        await expect(s.p.getByText('Marques produit').first()).toBeVisible(V)
        await calme(s.p)
        await expect(s.p.locator(`input[value="${nomMarque}"]`), 'relu : marque disparue').toHaveCount(0)
        expect(await py(`from apps.stock.models import Marque
sortie(Marque.objects.filter(pk=${x.marque}).exists())`), 'relu en base : marque supprimée').toBe(false)
      }
    }
  } finally {
    await py(`from apps.stock.models import Marque, Produit, Fournisseur
Marque.objects.filter(pk=${x.marque}).delete()
Produit.objects.filter(pk=${x.produit}).delete()
Fournisseur.objects.filter(pk=${x.fournisseur}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── PF4.4 — ADRG107 : « Mettre au rebut » (catalogue + fiche produit) selon `stock_mouvement` ─────────────────────
etape('PF4.4-ADRG107', ['ADRG107'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nomProduit = `Panneau ADRG107 ${m}`
  const x = await py(`from apps.stock.models import Produit
from apps.roles.models import Role
p = Produit.objects.create(company_id=${SOC}, nom=${J(nomProduit)}, prix_vente='900.00', prix_achat='500.00', quantite_stock=5)
r = Role.objects.create(company_id=${SOC}, nom=${J(`Stock sans mouvement ADRG107 ${m}`)}, permissions=['stock_voir', 'stock_modifier'])
sortie(dict(produit=p.pk, role=r.pk))`)
  try {
    const te = await compteDe('Technicien', 'adrg107te')
    const perso = await compteDe('rôle personnalisé stock_voir + stock_modifier', 'adrg107pe', x.role)
    expect([te.codes.includes('stock_mouvement'), te.codes.includes('stock_modifier')], 'Given : Technicien stock_mouvement sans stock_modifier').toEqual([true, false])
    for (const [c, rebut] of [[perso, false], [te, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        await charger(s, '/stock', passe)
        const menu = await menuProduit(s, nomProduit)
        expect(menu.some((t) => /Mettre au rebut/.test(t)), `${passe}${c.nomRole} : « Mettre au rebut » au menu de la ligne ${J(menu)}`).toBe(rebut)
        // Fiche produit.
        await bouton(s.p.getByRole('row').filter({ hasText: nomProduit }).first(), "Plus d'actions sur la ligne").click()
        await s.p.getByRole('menuitem', { name: /Fiche produit/ }).click()
        const fiche = s.p.getByRole('dialog').filter({ hasText: nomProduit }).last()
        await expect(fiche, `${passe}${c.nomRole} : fiche produit ouverte`).toBeVisible(V)
        await expect(bouton(fiche, /Mettre au rebut/), `${passe}${c.nomRole} : « Mettre au rebut » dans la fiche`).toHaveCount(rebut ? 1 : 0)
        await s.p.keyboard.press('Escape')
        expect(refus(s.reseau), `${passe}${c.nomRole} : aucune réponse refusée`).toEqual([])
      }
      if (rebut) {
        // Preuve : le Technicien met une unité au rebut depuis le catalogue ⇒ 201, stock relu diminué d'une unité.
        await charger(s, '/stock', '')
        await menuProduit(s, nomProduit).catch(() => undefined)
        await bouton(s.p.getByRole('row').filter({ hasText: nomProduit }).first(), "Plus d'actions sur la ligne").click()
        await s.p.getByRole('menuitem', { name: /Mettre au rebut/ }).click()
        const dlg = s.p.getByRole('dialog').filter({ hasText: `Mettre au rebut — ${nomProduit}` })
        await expect(dlg, 'Technicien : fenêtre de mise au rebut').toBeVisible(V)
        await expect(dlg.locator('#rebut-qte')).toHaveValue('1')
        await dlg.locator('#rebut-motif').click()
        await s.p.getByRole('option', { name: 'Casse', exact: true }).click()
        const [rep] = await Promise.all([
          reponse(s.p, new RegExp(`^/stock/produits/${x.produit}/rebuter/$`), 'POST'),
          bouton(dlg, 'Mettre au rebut').click(),
        ])
        expect(rep.status(), `Technicien : rebut ${(await rep.text()).slice(0, 200)}`).toBe(201)
        expect(await py(`from apps.stock.models import Produit
sortie(Produit.objects.get(pk=${x.produit}).quantite_stock)`), 'relu : stock diminué d\'une unité').toBe(4)
      }
    }
  } finally {
    await py(`from apps.stock.models import Produit, MouvementStock
U.objects.filter(role_id=${x.role}).update(is_active=False)
try:
    MouvementStock.objects.filter(produit_id=${x.produit}).delete()
    Produit.objects.filter(pk=${x.produit}).delete()
except Exception:
    Produit.objects.filter(pk=${x.produit}).update(archived=True) if hasattr(Produit, 'archived') else None
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── Facturation ─────────────────────────

/** Vente acceptée par demo_admin puis facture du BC émise. */
async function factureEmise(r, m) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG108 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg108${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADRG108 ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: `Client ADRG108 ${m}` } }), 'acceptation')
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
  const brouillon = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  await lireJson(await r.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
  return { devis: d, facture: await lireJson(await r.get(`${API}/ventes/factures/${brouillon.id}/`, T), 'facture relue') }
}

// ── PF4.4 — ADRG108 : échéance d'une facture émise modifiable seulement avec `encaisser` (formulaire) ────────────
etape('PF4.4-ADRG108', ['ADRG108'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const av = await compteDe('Admin Ventes', 'adrg108av')
  const cr = await compteDe('Commercial responsable', 'adrg108cr')
  expect(av.codes.includes('encaisser'), 'Given : Admin Ventes sans encaisser').toBe(false)
  expect(cr.codes.includes('encaisser'), 'Given : Commercial responsable avec encaisser').toBe(true)
  const { devis, facture } = await factureEmise(r, m)
  expect(facture.statut, 'Given : facture émise').not.toBe('brouillon')
  // Portée « soi » des rôles normaux : devis, BC et facture attribués à l'Admin Ventes.
  await py(`from django.db.models import Q
from apps.ventes.models import Devis, Facture, BonCommande
Devis.objects.filter(pk=${devis.id}).update(created_by_id=${av.id})
try:
    BonCommande.objects.filter(devis_id=${devis.id}).update(created_by_id=${av.id})
except Exception:
    pass
Facture.objects.filter(pk=${facture.id}).update(created_by_id=${av.id})
sortie(1)`)
  const URL_F = new RegExp(`^/ventes/factures/${facture.id}/$`)
  const ouvrirForm = async (s, passe) => {
    await charger(s, `/ventes/factures?id=${facture.id}`, passe)
    const form = s.p.getByRole('dialog').filter({ hasText: `Éditer — ${facture.reference}` })
    await expect(form, `${passe}${s.c.nomRole} : formulaire de la facture émise`).toBeVisible(V)
    return form
  }
  const enregistrer = async (s, form) => {
    const [rep] = await Promise.all([
      s.p.waitForResponse((x) => ['PUT', 'PATCH'].includes(x.request().method()) && URL_F.test(new URL(x.url()).pathname.slice(API.length)), T),
      form.locator('button[type="submit"]').click(),
    ])
    return rep
  }
  // Admin Ventes : échéance grisée ; PATCH sans `date_echeance` ; note enregistrée (200) et relue.
  const s = await ecranDe(page, suivi, testInfo, av)
  let form = await ouvrirForm(s, '')
  await expect(form.locator('#fc-echeance'), 'Admin Ventes : « Date d\'échéance » grisée').toBeDisabled()
  const note = `Note ADRG108 ${m}`
  await form.locator('#fc-note').fill(note)
  const rep = await enregistrer(s, form)
  const envoye = rep.request().postDataJSON() || {}
  expect(rep.status(), `Admin Ventes : enregistrement ${(await rep.text()).slice(0, 200)}`).toBe(200)
  expect(Object.keys(envoye).includes('date_echeance'), `Admin Ventes : PATCH sans date_echeance ${J(Object.keys(envoye))}`).toBe(false)
  const relue = await lireJson(await r.get(`${API}/ventes/factures/${facture.id}/`, T), 'facture relue')
  expect([relue.note, relue.date_echeance], 'relu : note enregistrée, échéance inchangée').toEqual([note, facture.date_echeance])
  form = await ouvrirForm(s, 'relu après rechargement : ')
  await expect(form.locator('#fc-echeance'), 'Admin Ventes relu : échéance toujours grisée').toBeDisabled()
  await expect(form.locator('#fc-note'), 'Admin Ventes relu : note relue').toHaveValue(note)
  expect(refus(s.reseau), 'Admin Ventes : aucune réponse refusée').toEqual([])
  // Commercial responsable (encaisser) : échéance modifiable, envoyée et relue.
  await py(`from apps.ventes.models import Facture
Facture.objects.filter(pk=${facture.id}).update(created_by_id=${cr.id})
sortie(1)`)
  const c = await ecranDe(page, suivi, testInfo, cr)
  const f2 = await ouvrirForm(c, '')
  const champ = f2.locator('#fc-echeance')
  await expect(champ, 'Commercial responsable : échéance modifiable').toBeEnabled()
  const nouvelle = isoDansJours(75)
  await champ.fill(nouvelle)
  const rep2 = await enregistrer(c, f2)
  expect(rep2.status(), `Commercial responsable : enregistrement ${(await rep2.text()).slice(0, 200)}`).toBe(200)
  expect((rep2.request().postDataJSON() || {}).date_echeance, 'Commercial responsable : échéance envoyée').toBe(nouvelle)
  expect((await lireJson(await r.get(`${API}/ventes/factures/${facture.id}/`, T), 'relue')).date_echeance, 'relu : échéance modifiée').toBe(nouvelle)
  const f3 = await ouvrirForm(c, 'relu après rechargement : ')
  await expect(f3.locator('#fc-echeance'), 'Commercial responsable relu : échéance relue').toHaveValue(nouvelle)
})

// ───────────────────────── SAV ─────────────────────────

// ── PF4.4 — ADRG114 : `/users/` de Contrats de maintenance lu seulement avec le droit de lister les comptes ──────
const USERS = /^\/users\/$/
etape('PF4.4-ADRG114', ['ADRG114'], async ({ page, suivi, testInfo }) => {
  for (const [nomRole, prefixe] of [['Commercial', 'adrg114co'], ['Technicien', 'adrg114te']]) {
    const c = await compteDe(nomRole, prefixe)
    expect(c.codes.includes('users_gerer'), `Given : ${nomRole} sans users_gerer`).toBe(false)
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of PASSES) {
      await charger(s, '/sav/contrats', passe)
      await s.p.getByRole('radio', { name: 'Tournée' }).click()
      await expect(s.p.getByRole('textbox', { name: 'Date de tournée' }).or(s.p.getByLabel('Date de tournée')).first(),
        `${passe}${nomRole} : onglet Tournée rendu`).toBeVisible(V)
      await calme(s.p)
      console.log(`[ADRG114] ${passe}${nomRole} /sav/contrats : ${J(s.reseau)}`)
      expect(appels(s.reseau, USERS), `${passe}${nomRole} : aucun GET /users/`).toEqual([])
      expect(refus(s.reseau), `${passe}${nomRole} : aucune réponse refusée`).toEqual([])
    }
  }
  // Témoin Directeur : /users/ lu (200), sélecteur du technicien de la tournée rempli.
  const di = await compteDe('Directeur', 'adrg114di')
  const d = await ecranDe(page, suivi, testInfo, di)
  const users = reponse(d.p, USERS)
  await charger(d, '/sav/contrats', '')
  const ru = await users
  expect(ru.status(), 'Directeur : comptes lus').toBe(200)
  await d.p.getByRole('radio', { name: 'Tournée' }).click()
  const sel = d.p.getByRole('combobox', { name: 'Technicien (optionnel)' })
  await expect(sel, 'Directeur : sélecteur du technicien').toBeVisible(V)
  await sel.click()
  await expect.poll(() => d.p.getByRole('option').count(), { message: 'Directeur : sélecteur rempli (au moins un compte)', timeout: 30_000 }).toBeGreaterThan(1)
  await d.p.keyboard.press('Escape')
})

/** Ticket SAV rattaché à un chantier et à un équipement (créé par demo_admin, attribué au Commercial, titulaire le Technicien). */
async function ticketLie(r, m, co, te) {
  const cl = await lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADRG115 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `adrg115_${m}@example.invalid` } }), 'client')
  const x = await py(`from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG115-${m}', statut='installe', client_id=${cl.id}, technicien_responsable_id=${te.id})
p = Produit.objects.create(company_id=${SOC}, nom=${J(`Onduleur ADRG115 ${m}`)}, prix_vente='1000.00', prix_achat='500.00')
e = Equipement.objects.create(company_id=${SOC}, produit=p, numero_serie=${J(`SN-ADRG115-${m}`)}, installation=i)
sortie(dict(installation=i.pk, produit=p.pk, equipement=e.pk))`)
  const t = await lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG115 ${m}`, installation: x.installation, equipement: x.equipement } }), 'ticket')
  await py(`from apps.sav.models import Ticket
Ticket.objects.filter(pk=${t.id}).update(created_by_id=${co.id}, technicien_responsable_id=${te.id}, installation_id=${x.installation}, equipement_id=${x.equipement})
sortie(1)`)
  return { ...x, ticket: t, client: cl }
}

// ── PF4.4 — ADRG115 : lectures de la fiche ticket (pièces, checklist, prêts sous `sav_gerer` ; interventions sous
//    la lecture des chantiers) ─────────────────────────────────────────────────────────────────────────────────────
etape('PF4.4-ADRG115', ['ADRG115'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const co = await compteDe('Commercial', 'adrg115co')
  const te = await compteDe('Technicien', 'adrg115te')
  expect([co.codes.includes('sav_voir'), co.codes.includes('sav_gerer')], 'Given : Commercial sav_voir sans sav_gerer').toEqual([true, false])
  const x = await ticketLie(r, m, co, te)
  const id = x.ticket.id
  const LECTURES = [
    ['pièces', new RegExp(`^/sav/tickets/${id}/pieces/$`)],
    ['pièces unifiées', new RegExp(`^/sav/tickets/${id}/pieces-unifiees/$`)],
    ['pièces compatibles', new RegExp(`^/sav/tickets/${id}/pieces-compatibles/$`)],
    ['checklist', new RegExp(`^/sav/tickets/${id}/checklist/$`)],
    ['prêts d\'équipement', new RegExp(`^/sav/tickets/${id}/prets-equipement/$`)],
    ['interventions', /^\/installations\/interventions\/$/],
  ]
  const fiche = (p) => p.locator('aside[aria-label^="Détail du ticket"], [role="dialog"]').filter({ hasText: 'Checklist de maintenance' }).first()
  try {
    for (const [c, gere] of [[co, false], [te, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        await charger(s, `/sav?id=${id}`, passe)
        const f = fiche(s.p)
        await expect(f, `${passe}${c.nomRole} : fiche du ticket ouverte`).toBeVisible(V)
        for (const titre of ['Pièces consommées', 'Checklist de maintenance', 'Interventions']) {
          await expect(f.getByText(titre, { exact: true }).first(), `${passe}${c.nomRole} : section « ${titre} »`).toBeVisible(V)
        }
        await calme(s.p)
        console.log(`[ADRG115] ${passe}${c.nomRole} fiche ticket : ${J(s.reseau)}`)
        for (const [quoi, re] of LECTURES) {
          const vus = appels(s.reseau, re).filter((l) => quoi !== 'interventions' || /[?&]ticket=/.test(l))
          if (gere) expect(vus.length > 0 && vus.every((l) => l.endsWith('→ 200')), `${passe}${c.nomRole} : ${quoi} lus ${J(vus)}`).toBe(true)
          else expect(vus, `${passe}${c.nomRole} : aucun GET ${quoi}`).toEqual([])
        }
        expect(refus(s.reseau), `${passe}${c.nomRole} : aucune réponse refusée sur la fiche`).toEqual([])
      }
    }
  } finally {
    await py(`from apps.sav.models import Ticket, Equipement
from apps.installations.models import Installation
from apps.stock.models import Produit
Ticket.objects.filter(pk=${id}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

// ── PF4.4 — ADRG116 : journal d'immobilisation et relevés compteur d'un équipement au seul palier administrateur ──
etape('PF4.4-ADRG116', ['ADRG116'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const cr = await compteDe('Commercial responsable', 'adrg116cr')
  const tr = await compteDe('Technicien responsable', 'adrg116tr')
  const di = await compteDe('Directeur', 'adrg116di')
  const serie = `SN-ADRG116-${m}`
  const x = await py(`from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.stock.models import Produit
i = Installation.objects.create(company_id=${SOC}, reference='CHT-ADRG116-${m}', statut='installe', technicien_responsable_id=${tr.id}, created_by_id=${cr.id})
p = Produit.objects.create(company_id=${SOC}, nom=${J(`Onduleur ADRG116 ${m}`)}, prix_vente='1000.00', prix_achat='500.00')
e = Equipement.objects.create(company_id=${SOC}, produit=p, numero_serie=${J(serie)}, installation=i, created_by_id=${cr.id})
sortie(dict(installation=i.pk, produit=p.pk, equipement=e.pk))`)
  const DOWNTIME = new RegExp(`^/sav/equipements/${x.equipement}/downtime/$`)
  const RELEVES = new RegExp(`^/sav/equipements/${x.equipement}/releves-compteur/$`)
  const ouvrir = async (s, passe) => {
    await charger(s, '/equipements', passe)
    await s.p.getByPlaceholder('Rechercher (série, produit, chantier, client)…').fill(serie)
    await s.p.getByRole('row').filter({ hasText: serie }).first().click({ timeout: 60_000 })
    await expect(s.p.getByText('Fiabilité & maintenance').first(), `${passe}${s.c.nomRole} : fiche équipement ouverte`).toBeVisible(V)
    await expect(s.p.getByText('Disponibilité (30 j) :').first(), `${passe}${s.c.nomRole} : disponibilité affichée`).toBeVisible(V)
    await expect(s.p.getByText('MTBF :').first(), `${passe}${s.c.nomRole} : MTBF affiché`).toBeVisible(V)
    await calme(s.p)
  }
  try {
    for (const c of [cr, tr]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of PASSES) {
        await ouvrir(s, passe)
        console.log(`[ADRG116] ${passe}${c.nomRole} fiche équipement : ${J(s.reseau)}`)
        expect(appels(s.reseau, DOWNTIME), `${passe}${c.nomRole} : aucun GET downtime/`).toEqual([])
        expect(appels(s.reseau, RELEVES), `${passe}${c.nomRole} : aucun GET releves-compteur/`).toEqual([])
        await expect(s.p.getByText('Relevés compteur', { exact: true }), `${passe}${c.nomRole} : bloc relevés absent`).toHaveCount(0)
        await expect(s.p.getByText('Immobilisation', { exact: true }), `${passe}${c.nomRole} : bloc immobilisation absent`).toHaveCount(0)
        expect(refus(s.reseau), `${passe}${c.nomRole} : aucune réponse refusée`).toEqual([])
      }
    }
    // Témoin Directeur : les deux lus (200), blocs présents.
    const d = await ecranDe(page, suivi, testInfo, di)
    for (const passe of PASSES) {
      await ouvrir(d, passe)
      for (const [quoi, re] of [['downtime/', DOWNTIME], ['releves-compteur/', RELEVES]]) {
        const vus = appels(d.reseau, re)
        expect(vus.length > 0 && vus.every((l) => l.endsWith('→ 200')), `${passe}Directeur : ${quoi} lu ${J(vus)}`).toBe(true)
      }
      await expect(d.p.getByText('Relevés compteur', { exact: true }).first(), `${passe}Directeur : bloc relevés`).toBeVisible(V)
      await expect(d.p.getByText('Immobilisation', { exact: true }).first(), `${passe}Directeur : bloc immobilisation`).toBeVisible(V)
    }
  } finally {
    await py(`from apps.sav.models import Equipement
from apps.installations.models import Installation
Equipement.objects.filter(pk=${x.equipement}).delete()
try:
    Installation.objects.filter(pk=${x.installation}).delete()
except Exception:
    Installation.objects.filter(pk=${x.installation}).update(annule=True)
sortie(1)`).catch(() => null)
  }
})

// ───────────────────────── Fiche lead ─────────────────────────

/** Lead de `uid` avec un devis ACCEPTÉ sans chantier (le chantier né de l'acceptation est retiré). */
async function leadDevisAccepte(r, m, uid, tag) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG121 ${tag} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg121${tag}${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADRG121 ${tag} ${m}`, prix_vente: '10000.00', prix_achat: '4321.09' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: `Client ADRG121 ${tag} ${m}` } }), 'acceptation')
  const etat = await py(`from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.installations.models import Installation
for i in Installation.objects.filter(devis_id=${d.id}):
    try:
        i.delete()
    except Exception:
        Installation.objects.filter(pk=i.pk).update(devis_id=None)
Lead.objects.filter(pk=${lead.id}).update(owner_id=${uid})
Devis.objects.filter(pk=${d.id}).update(created_by_id=${uid})
sortie(dict(statut=Devis.objects.get(pk=${d.id}).statut, chantiers=Installation.objects.filter(devis_id=${d.id}).count()))`)
  expect(etat, 'Given : devis accepté sans chantier').toEqual({ statut: 'accepte', chantiers: 0 })
  return { lead, devis: d }
}

// ── PF4.4 — ADRG121 : fiche lead en lecture seule sans `crm_modifier` (étape, champs, note, « Créer le chantier ») ──
etape('PF4.4-ADRG121', ['ADRG121'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const vi = await compteDe('Viewer', 'adrg121vi')
  const co = await compteDe('Commercial', 'adrg121co')
  expect(vi.codes.includes('crm_modifier'), 'Given : Viewer sans crm_modifier').toBe(false)
  expect([co.codes.includes('crm_modifier'), co.codes.includes('ventes_creer')], 'Given : Commercial crm_modifier + ventes_creer').toEqual([true, true])
  const COMPOSEUR = 'Écrire une note (appel, commentaire…)'
  /** Fiche du lead : état des gestes d'écriture. */
  const lireFiche = async (s, leadId, passe) => {
    await charger(s, `/crm/leads/${leadId}`, passe)
    const pill = s.p.locator('.lw-stagepill').first()
    await expect(pill, `${passe}${s.c.nomRole} : fiche du lead rendue (pilule d'étape)`).toBeVisible(V)
    await calme(s.p)
    return pill
  }
  // Viewer : lead à devis accepté.
  const v = await leadDevisAccepte(r, m, vi.id, 'vi')
  const sv = await ecranDe(page, suivi, testInfo, vi)
  for (const passe of PASSES) {
    const pill = await lireFiche(sv, v.lead.id, passe)
    await expect(pill, `${passe}Viewer : sélecteur d'étape inerte`).toBeDisabled()
    const champs = sv.p.locator('fieldset[disabled] input, fieldset[disabled] textarea')
    expect(await champs.count(), `${passe}Viewer : champs de la fiche sous un fieldset désactivé`).toBeGreaterThan(0)
    await expect(champs.first(), `${passe}Viewer : champ inerte`).toBeDisabled()
    await sv.p.getByRole('tab', { name: 'Historique', exact: true }).click()
    await expect(sv.p.getByPlaceholder(COMPOSEUR), `${passe}Viewer : aucun composeur de note`).toHaveCount(0)
    await sv.p.getByRole('tab', { name: /devis/i }).first().click()
    await expect(sv.p.getByText(v.devis.reference).first(), `${passe}Viewer : devis accepté listé`).toBeVisible(V)
    await calme(sv.p)
    await expect(bouton(sv.p, /Créer le chantier/), `${passe}Viewer : aucun « Créer le chantier »`).toHaveCount(0)
    console.log(`[ADRG121] ${passe}Viewer fiche : ${J(sv.reseau)}`)
    expect(refus(sv.reseau), `${passe}Viewer : aucune réponse refusée sur la fiche`).toEqual([])
  }
  // Commercial : sur son lead à devis accepté, étape, champs, composeur et « Créer le chantier » offerts.
  const c = await leadDevisAccepte(r, m, co.id, 'co')
  const sc = await ecranDe(page, suivi, testInfo, co)
  const pill = await lireFiche(sc, c.lead.id, '')
  await expect(pill, 'Commercial : sélecteur d\'étape actif').toBeEnabled()
  expect(await sc.p.locator('fieldset[disabled]').count(), 'Commercial : aucun fieldset désactivé').toBe(0)
  await sc.p.getByRole('tab', { name: 'Historique', exact: true }).click()
  await expect(sc.p.getByPlaceholder(COMPOSEUR), 'Commercial : composeur de note').toBeVisible(V)
  await sc.p.getByRole('tab', { name: /devis/i }).first().click()
  await expect(bouton(sc.p, /Créer le chantier/).first(), 'Commercial : « Créer le chantier »').toBeVisible(V)
  // Preuve : le Commercial change l'étape d'un lead neuf et y laisse une note, relues après rechargement.
  const neuf = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG121 neuf ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead neuf')
  await py(`from apps.crm.models import Lead
sortie(Lead.objects.filter(pk=${neuf.id}).update(owner_id=${co.id}))`)
  const p2 = await lireFiche(sc, neuf.id, '')
  await p2.click()
  const [patch] = await Promise.all([
    reponse(sc.p, new RegExp(`^/crm/leads/${neuf.id}/$`), 'PATCH'),
    sc.p.getByRole('menuitem', { name: /Contacté/ }).first().click(),
  ])
  expect(patch.status(), `Commercial : étape changée ${(await patch.text()).slice(0, 200)}`).toBe(200)
  const texteNote = `Note ADRG121 ${m}`
  await sc.p.getByRole('tab', { name: 'Historique', exact: true }).click()
  await sc.p.getByPlaceholder(COMPOSEUR).fill(texteNote)
  const [noter] = await Promise.all([
    reponse(sc.p, new RegExp(`^/crm/leads/${neuf.id}/noter/$`), 'POST'),
    bouton(sc.p, /^Noter$/).click(),
  ])
  expect(noter.status(), `Commercial : note enregistrée ${(await noter.text()).slice(0, 200)}`).toBeLessThan(300)
  const p3 = await lireFiche(sc, neuf.id, 'relu après rechargement : ')
  await expect(p3, 'Commercial relu : étape « Contacté »').toContainText('Contacté')
  await sc.p.getByRole('tab', { name: 'Historique', exact: true }).click()
  await expect(sc.p.getByText(texteNote).first(), 'Commercial relu : note dans l\'historique').toBeVisible(V)
  expect(await py(`from apps.crm.models import Lead
sortie(Lead.objects.get(pk=${neuf.id}).stage)`), 'relu en base : étape CONTACTED').toBe('CONTACTED')
  expect(refus(sc.reseau), 'Commercial : aucune réponse refusée').toEqual([])
})
