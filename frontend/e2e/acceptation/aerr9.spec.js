// Preuves en direct ÉCRAN du groupe AERR, lot 9 (défauts relevés aux rejeux du 14-15/11) : AERR174 (GED : fermer
// « Versions du document » puis l'aperçu au clavier ne fait plus planter `/ged`) et AERR175 (Factures : « Note de
// débit » puis « Fermer » laisse la liste cliquable à la souris).
// AERR174 rejoue le GESTE D'ORIGINE du run 43641375588 (spec adrg5.spec.js, commit cc1e64c27 : deux
// `keyboard.press('Escape')` enchaînés, sans attente, la fenêtre « Versions » ouverte au-dessus de l'aperçu — d'abord
// sous Viewer, comme la 1re passe de cette spec, puis sous Directeur, rôle de la clause), puis la variante espacée
// (Échap, Versions attendue fermée, Échap). Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur
// nom dans la société démo) : AERR174 connecté par /token/ (comme adrg5.spec.js), AERR175 par l'ÉCRAN de connexion
// (comme aerr6.spec.js). Données propres créées par les vraies routes ; une facture à numéro légal reste sur la base
// jetable du runner. Persistance : n/a (fenêtres et menus) — chaque geste est rejoué après rechargement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, connexionApi, telephoneMobileUnique, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AERR', ['AERR174', 'AERR175'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const V = { timeout: 60_000 }
const J = JSON.stringify
const SOC = `U.objects.get(username='demo_admin').company_id`
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const INIT = () => {
  try {
    localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
    const v = (t) => parts.find((x) => x.type === t).value
    localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
  } catch { /* mode privé */ }
}

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo. */
async function compteDuRole(nomRole, prefixe) {
  const nom = `${prefixe}_${marque()}`
  await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
compte(${J(nom)}, role=r.pk, societe=${SOC})
sortie(1)`)
  return nom
}
/** Écran sous `nom` : contexte neuf (SW bloqué), session par /token/ (`ecran: 'api'`) ou par l'écran de connexion,
 *  visites guidées vues. Relève les erreurs de page (pageerror + console.error) en plus des oracles. */
async function ecran(page, suivi, testInfo, nom, { par = 'ecran' } = {}) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  await ctx.addInitScript(INIT)
  if (par === 'api') await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const p = suivi.surveiller(await ctx.newPage())
  const erreurs = []
  p.on('pageerror', (e) => erreurs.push(`pageerror : ${e.message}`))
  p.on('console', (m) => { if (m.type() === 'error') erreurs.push(`console.error : ${m.text()}`) })
  if (par !== 'api') await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json().catch(() => [])) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T).catch(() => undefined)
    }
  }
  return { p, api: ctx.request, erreurs }
}

// ═══ AERR174 — /ged : « Versions… » au-dessus de l'aperçu, puis Échap, Échap ⇒ aucune erreur, la liste reste ═══
const PDF = (n) => Buffer.from(`%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n% version ${n}\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n`)
etape('PF12.3-AERR174', ['AERR174'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab AERR174 ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos AERR174 ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Plan AERR174 ${m}`, folder: dos.id } }), 'document')
  for (const n of [1, 2]) {
    await lireJson(await r.post(`${GED}/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: { name: `plan-v${n}.pdf`, mimeType: 'application/pdf', buffer: PDF(n) } } }), `version ${n}`)
  }
  expect(await py(`from apps.ged.models import DocumentVersion
sortie(DocumentVersion.objects.filter(document_id=${doc.id}).count())`), 'Given : un document à deux versions').toBe(2)
  for (const [nomRole, prefixe] of [['Viewer', 'aerr174vi'], ['Directeur', 'aerr174di']]) {
    const s = await ecran(page, suivi, testInfo, await compteDuRole(nomRole, prefixe), { par: 'api' })
    const liste = s.p.getByRole('button', { name: `Aperçu de ${doc.nom}` })
    for (const [passe, espace] of [['', false], ['relu après rechargement : ', false], ['Échap espacés : ', true]]) {
      if (passe.startsWith('relu')) await s.p.reload(); else await s.p.goto('/ged')
      const choix = s.p.getByRole('combobox', { name: 'Choisir le cabinet' })
      await expect(s.p.getByRole('tree', { name: 'Dossiers' }).or(choix).first(), `${passe}${nomRole} : GED rendue`).toBeVisible(V)
      if (await choix.count()) {
        await choix.click()
        await s.p.getByRole('option', { name: cab.nom, exact: true }).click()
      }
      await s.p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
      await liste.click()
      const apercu = s.p.getByRole('dialog').filter({ hasText: doc.nom })
      await expect(apercu.getByRole('button', { name: /Versions…/ }), `${passe}${nomRole} : « Versions… » (deux versions)`).toBeVisible(V)
      await apercu.getByRole('button', { name: /Versions…/ }).click()
      const versions = s.p.getByRole('dialog').filter({ has: s.p.getByRole('heading', { name: 'Versions du document' }) })
      await expect(versions.getByText(/\(actuelle\)/), `${passe}${nomRole} : fenêtre « Versions du document » ouverte`).toBeVisible(V)
      s.erreurs.length = 0
      if (espace) {
        await s.p.keyboard.press('Escape')
        await expect(versions, `${passe}${nomRole} : 1er Échap — versions refermées`).toBeHidden()
        await s.p.keyboard.press('Escape')
      } else {
        // GESTE D'ORIGINE (adrg5.spec.js @ cc1e64c27) : deux Échap enchaînés, sans attente.
        await s.p.keyboard.press('Escape')
        await s.p.keyboard.press('Escape')
      }
      await expect(versions, `${passe}${nomRole} : « Versions » refermée`).toBeHidden()
      await expect(s.p.getByRole('dialog'), `${passe}${nomRole} : aperçu refermé (aucune fenêtre)`).toHaveCount(0, { timeout: 30_000 })
      await s.p.waitForTimeout(1500)
      await expect(s.p.getByText('Une erreur est survenue'), `${passe}${nomRole} : pas d'écran « Une erreur est survenue »`).toHaveCount(0)
      await expect(liste, `${passe}${nomRole} : la liste reste affichée (le document est listé)`).toBeVisible()
      console.log(`[AERR174] ${passe}${nomRole} : erreurs relevées ${J(s.erreurs)}`)
      expect(s.erreurs.filter((e) => /TypeError|RouteErrorBoundary/.test(e)), `${passe}${nomRole} : aucune TypeError en console`).toEqual([])
    }
  }
})

// ═══ AERR175 — Factures : « Actions » › « Note de débit » › « Fermer », puis un CLIC SOURIS sur une autre ligne ═══
async function factureDe(cree, admin, m) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: {
    nom: `AERR175 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `aerr175-${m}@example.invalid`,
  } }), 'lead')
  const prod = await lireJson(await admin.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AERR175 ${m}`, prix_vente: '10000.00', prix_achat: '1.00' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: {
    taux_tva: '20.00', remise_globale: '0', lead: l.id,
    lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
  } }), 'devis')
  await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AERR175' } }), 'accepter')
  const rep = await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre: true, remplacer_brouillons: true } }), 'facturer')
  return { id: rep.facture.id, reference: rep.facture.reference, statut: rep.facture.statut }
}
etape('PF12.3-AERR175', ['AERR175'], async ({ page, suivi, testInfo }) => {
  const admin = page.context().request
  const m = marque()
  const { p, api } = await ecran(page, suivi, testInfo, await compteDuRole('Directeur', 'aerr175di'))
  const A = await factureDe(api, admin, `${m}a`)
  const B = await factureDe(api, admin, `${m}b`)
  expect([A.statut, B.statut], 'Given : deux factures émises').toEqual(['emise', 'emise'])
  const ligne = (f) => p.locator(`#facture-row-${f.id}`)
  const actions = (f) => ligne(f).locator('button', { hasText: 'Actions' })
  const boite = (f) => p.getByRole('dialog').filter({ hasText: `Notes de débit — ${f.reference}` })
  const etat = (f) => ligne(f).evaluate((el) => ({
    pointeurs: getComputedStyle(document.body).pointerEvents,
    cachee: Boolean(el.closest('[aria-hidden="true"]')), inerte: Boolean(el.closest('[inert]')),
  }))
  for (const [passe, X, Y] of [['', A, B], ['relu après rechargement : ', B, A]]) {
    if (passe) await p.reload(); else await p.goto('/ventes/factures')
    for (const f of [A, B]) await expect(ligne(f), `${passe}${f.reference} affichée`).toBeVisible({ timeout: 90_000 })
    // « Actions » (souris) › « Note de débit » › « Fermer » sur X.
    await actions(X).click()
    await p.getByRole('menuitem', { name: 'Note de débit' }).click()
    await expect(boite(X), `${passe}boîte « Notes de débit » ouverte sur ${X.reference}`).toBeVisible({ timeout: 30_000 })
    await expect(p.getByRole('menu'), `${passe}le menu « Actions » est refermé dès l'ouverture de la boîte`).toHaveCount(0)
    await boite(X).getByRole('button', { name: 'Fermer' }).click()
    await expect(boite(X), `${passe}boîte de ${X.reference} refermée`).toBeHidden({ timeout: 30_000 })
    // Aucun Échap : le menu ne doit pas être resté ouvert, la page doit rester cliquable.
    await expect(p.getByRole('menu'), `${passe}aucun menu resté ouvert`).toHaveCount(0)
    await expect.poll(async () => (await etat(Y)).pointeurs, { message: `${passe}body sans pointer-events: none`, timeout: 10_000 }).not.toBe('none')
    const e = await etat(Y)
    console.log(`[AERR175] ${passe}ligne ${Y.reference} après « Fermer » : ${J(e)}`)
    expect([e.cachee, e.inerte], `${passe}la ligne ${Y.reference} n'est ni aria-hidden ni inerte`).toEqual([false, false])
    // CLIC SOURIS (pas le clavier) sur l'autre ligne : son menu s'ouvre.
    await actions(Y).click({ timeout: 15_000 })
    await expect(p.getByRole('menuitem', { name: 'Note de débit' }), `${passe}clic souris sur ${Y.reference} : son menu s'ouvre`).toBeVisible({ timeout: 15_000 })
    await p.keyboard.press('Escape')
    await expect(p.getByRole('menu'), `${passe}menu de ${Y.reference} refermé`).toHaveCount(0)
  }
})
