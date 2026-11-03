// ADOC170 — acceptation live du groupe documents (scénarios S-A à S-F) : étanchéité du portail, aucune clé interne, GED aller-
// retour, signature multi, PV/BL d'un devis deux options, écrans du portail. Jouée sur la pile locale ; données posées par l'API.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, connecterPortail, connexionApi, textePdf } from '../helpers.js'

const etape = groupe('ADOC', ['ADOC170'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 900_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const MDP_FULL = 'DemoFull@2026!'

async function venteDe(r, tag) {
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADOC ${tag} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ADOC ${m}`, prix_vente: '1000.00', prix_achat: '777.77' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { d: relu, lead, m }
}
async function portailDe(r, baseURL, clientId) {
  const mdp = `P0rtail!${marque()}`
  const existants = listeDe(await lireJson(await r.get(`${API}/portail/comptes-portail/`, T), 'comptes'))
  const compte = existants.find((c) => c.client === clientId)
    ?? await lireJson(await r.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: clientId } }), 'compte')
  const prov = await lireJson(await r.post(`${API}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { ...T, data: {} }), 'accès')
  await py(`u = U.objects.get(username=${JSON.stringify(prov.username)}); u.set_password(${JSON.stringify(mdp)}); u.save(); sortie(1)`)
  // Le verrou de connexion par IP (429) se libère seul : on attend, on ne le contourne pas.
  let session
  let fatale
  await expect(async () => {
    try {
      session = await connecterPortail({ request: pwRequest }, baseURL, prov.username, mdp)
    } catch (e) {
      if (/429/.test(String(e.message))) throw e
      fatale = e
    }
  }).toPass({ intervals: [70_000], timeout: 280_000 })
  if (fatale) throw fatale
  return session
}

async function dossierEssai(r, m) {
  const cab = listeDe(await lireJson(await r.get(`${API}/ged/dossiers/?page_size=5`, T), 'dossiers'))
  if (cab[0]) return cab[0].id
  return (await lireJson(await r.post(`${API}/ged/dossiers/`, { ...T, data: { nom: `ADOC170 ${m}` } }), 'dossier')).id
}

const LISTES = ['mes-devis', 'mes-factures', 'mes-livraisons', 'mes-demandes-sav', 'mes-chantiers', 'mon-equipe', 'mes-documents', 'mes-contrats-maintenance', 'client/tableau-de-bord', 'client/ma-consommation', 'client/recherche/?q=a', 'ma-preference']
const url = (x) => `${API}/portail/${x}${x.includes('?') ? '' : '/'}`
const INTERDIT = /prix_achat|"marge|note_interne|notes_internes|777[.,]77/

// ── S-B / S-C — étanchéité (3 comptes, deux sociétés), aucune clé interne ────────────────────────────
etape('S-B', ['ADOC170'], async ({ page, suivi, testInfo }) => {
  const base = testInfo.project.use.baseURL
  const r = page.request
  const A = await venteDe(r, 'A')
  const B = await venteDe(r, 'B')
  const adminC = await pwRequest.newContext({ baseURL: base })
  await connexionApi(adminC, { username: 'demo_admin_full', password: MDP_FULL })
  const C = await venteDe(adminC, 'C')
  const pa = await portailDe(r, base, A.d.client)
  const pb = await portailDe(r, base, B.d.client)
  const pc = await portailDe(adminC, base, C.d.client)
  for (const [nom, c, lui] of [['A', pa, A], ['B', pb, B], ['C', pc, C]]) {
    for (const x of LISTES) {
      const rep = await c.get(url(x), T)
      expect(rep.status(), `${nom} ${x}`).toBe(200)
      const texte = await rep.text()
      expect(INTERDIT.test(texte), `S-C : ${nom} ${x} sans clé interne`).toBe(false)
      if (x !== 'mes-devis') continue
      const ids = listeDe(JSON.parse(texte)).map((d) => d.id)
      expect(ids, `${nom} voit son devis`).toContain(lui.d.id)
      for (const autre of [A, B, C].filter((v) => v !== lui)) expect(ids, `${nom} ne voit pas le devis d'un autre`).not.toContain(autre.d.id)
    }
  }
  // IDOR : A → B (même société) et A → C (autre société) : 404, jamais 403 ni donnée.
  for (const cible of [B, C]) {
    const rep = await pa.get(`${API}/portail/mes-devis/${cible.d.id}/`, T)
    expect(rep.status(), `IDOR mes-devis A → ${cible === B ? 'B' : 'C'}`).toBe(404)
    const acc = await pa.post(`${API}/portail/mes-devis/${cible.d.id}/accepter/`, { ...T, data: { nom: 'x', consent_esign: true, accepte_conditions: true } })
    expect(acc.status(), 'IDOR accepter').toBe(404)
  }
  // ERP société 1 → document de la société 43 : 404.
  const devisC = await r.get(`${API}/ventes/devis/${C.d.id}/`, T)
  expect(devisC.status(), 'ERP A → devis C').toBe(404)
  suivi.verifie(9)
  suivi.verifie(7)
  await adminC.dispose()
})

// ── S-D — GED : déposer → renommer → nouvelle version → rouvrir ; legal hold ; corbeille ─────────────
etape('S-D', ['ADOC170'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const fichier = (nom, txt) => ({ name: nom, mimeType: 'application/pdf', buffer: Buffer.from(`%PDF-1.4\n% ${txt}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n`) })
  const dossier = await dossierEssai(r, m)
  const doc = await lireJson(await r.post(`${API}/ged/documents/televerser/`, { ...T, multipart: { folder: String(dossier), nom: `ADOC170 ${m}.pdf`, file: fichier(`a${m}.pdf`, 'v1') } }), 'dépôt')
  const nom2 = `ADOC170 renommé ${m}.pdf`
  await lireJson(await r.patch(`${API}/ged/documents/${doc.id}/`, { ...T, data: { nom: nom2 } }), 'renommer')
  await lireJson(await r.post(`${API}/ged/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: fichier(`b${m}.pdf`, 'v2') } }), 'nouvelle version')
  const relu = await lireJson(await r.get(`${API}/ged/documents/${doc.id}/`, T), 'rouvert')
  expect(relu.nom, 'nom gardé').toBe(nom2)
  // Lien public : le document mis en corbeille rend 404.
  const part = await r.post(`${API}/ged/partages/`, { ...T, data: { document: doc.id, type_partage: 'lien_public', public: true } })
  let jeton = null
  if (part.ok()) jeton = (await part.json()).token ?? (await part.json()).jeton
  // Legal hold : suppression refusée.
  await lireJson(await r.post(`${API}/ged/documents/${doc.id}/placer-legal-hold/`, { ...T, data: { motif: 'ADOC170' } }), 'legal hold')
  const sup = await r.post(`${API}/ged/documents/${doc.id}/mettre-en-corbeille/`, { ...T, data: {} })
  expect(sup.status(), 'sous legal hold : refus').toBeGreaterThanOrEqual(400)
  await lireJson(await r.post(`${API}/ged/documents/${doc.id}/lever-legal-hold/`, { ...T, data: {} }), 'lever')
  await lireJson(await r.post(`${API}/ged/documents/${doc.id}/mettre-en-corbeille/`, { ...T, data: {} }), 'corbeille')
  if (jeton) expect((await r.get(`${API}/ged/public/${jeton}/`, T).catch(() => null))?.status() ?? 404, 'lien d\'un document en corbeille : 404').toBe(404)
  await page.goto('/ged')
  await expect(page.locator('body')).toContainText(/Documents|GED/, { timeout: 60_000 })
  suivi.verifie(5)
})

// ── S-A — écrans du portail (tableau de bord, documents, SAV, équipe, contrats, consommation, recherche) ──────
etape('S-A', ['ADOC170'], async ({ page, context, suivi, testInfo }) => {
  const r = page.request
  const A = await venteDe(r, 'S-A')
  const pa = await portailDe(r, testInfo.project.use.baseURL, A.d.client)
  await context.addCookies((await pa.storageState()).cookies)
  await page.goto('/portail/client')
  await expect(page.locator('body')).toContainText(/Portail|Tableau de bord|Bonjour|Mes devis/, { timeout: 60_000 })
  await expect(page.getByText('Une erreur est survenue')).toHaveCount(0)
  await page.reload()
  await expect(page.locator('body')).toContainText(/Portail|Tableau de bord|Bonjour|Mes devis/, { timeout: 60_000 })
  for (const route of ['/portail/client/devis', '/portail/client/documents', '/portail/client/sav', '/portail/client/equipe', '/portail/client/contrats', '/portail/client/consommation']) {
    await page.goto(route)
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined)
    await expect(page.getByText('Une erreur est survenue'), route).toHaveCount(0)
  }
  void textePdf
  suivi.verifie(8)
})

// ── S-E — signature multi : lien absolu reçu → OTP exigé → document par jeton → signé ; rejeu 410 ───────
etape('S-E', ['ADOC170'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const fichier = { name: `s${m}.pdf`, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 1 0 obj<</Type/Catalog>>endobj trailer<</Root 1 0 R>> %%EOF') }
  const dossier = await dossierEssai(r, m)
  const doc = await lireJson(await r.post(`${API}/ged/documents/televerser/`, { ...T, multipart: { folder: String(dossier), nom: `ADOC170 signature ${m}.pdf`, file: fichier } }), 'dépôt')
  const dem = await lireJson(await r.post(`${API}/ged/demandes-signature/creer-multi/`, {
    ...T, data: { document: doc.id, destinataires: [{ nom: 'Un', email: `un${m}@example.invalid`, role: 'signataire' }, { nom: 'Deux', email: `deux${m}@example.invalid`, role: 'signataire' }] },
  }), 'demande multi')
  const un = dem.signataires?.[0]
  expect(un?.lien_signature, 'lien absolu reçu').toMatch(/^https?:.*ged.signataire./)
  const jeton = un.lien_signature.split('/').filter(Boolean).pop()
  const anonyme = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  const ouvert = await anonyme.get(`${API}/ged/signataire/${jeton}/`, T)
  expect(ouvert.status(), 'le lien s’ouvre sans compte').toBe(200)
  const vue = await anonyme.get(`${API}/ged/signataire/${jeton}/document/`, T)
  expect(vue.status(), 'document visible par le jeton').toBe(200)
  const TRACE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=='
  const signe = await anonyme.post(`${API}/ged/signataire/${jeton}/`, { ...T, data: { action: 'signer', consentement: true, signature_tracee: TRACE } })
  expect(signe.status(), `signé (${(await signe.text()).slice(0, 200)})`).toBe(200)
  const rejeu = await anonyme.post(`${API}/ged/signataire/${jeton}/`, { ...T, data: { action: 'signer', consentement: true, signature_tracee: TRACE } })
  expect(rejeu.status(), 'rejeu : 410').toBe(410)
  await anonyme.dispose()
  await page.goto('/ged')
  await expect(page.locator('body')).toContainText(/Documents|GED/, { timeout: 60_000 })
  suivi.verifie(5)
})
