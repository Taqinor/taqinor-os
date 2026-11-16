// Acceptation en direct — groupe ADVS, septième lot (vague 6, runner GitHub) : preuve due d'ADVS50 — PA3 : source DÉJÀ
// envoyée, gamme sœur créée ENSUITE (`dupliquer-variante-gamme`), renvoi « les deux ».
// Nouveau par rapport à advs6 : la PAGE CLIENT `/proposition/<jeton de la source>` (apps/web, `astro dev` du runner,
// rendue côté serveur depuis ce Django) est OUVERTE et AFFIRMÉE : la carte de la sœur y figure (nom, lien vers SON jeton),
// et le chatter ne porte aucun second « Envoyé » pour la source.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ADVS', ['ADVS50'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const lire = async (r, id) => lireJson(await r.get(`${API}/ventes/devis/${id}/`, T), 'devis')
const nouveauLead = async (r, nom, extra = {}) => lireJson(await r.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `advs50${marque()}@example.invalid`, ...extra },
}), 'lead')
const produitEssai = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
const ligne = (p, q, ordre = 0) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
const envoyer = async (r, id, extra = {}) => lireJson(await r.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true, ...extra } }), 'envoi')
const liens = (id) => py(`from apps.ventes.models import ShareLink
sortie([str(t) for t in ShareLink.objects.filter(devis_id=${Number(id)}).values_list('token', flat=True)])`)
const nbEnvoyes = (id) => py(`from apps.ventes.models import DevisActivity
sortie(DevisActivity.objects.filter(devis_id=${Number(id)}, field='statut', new_value='Envoyé').count())`)
const webBase = () => {
  const w = process.env.E2E_WEB_BASE
  expect(w, 'E2E_WEB_BASE absent : apps/web (page client) non servie').toBeTruthy()
  expect(w, 'jamais la prod').toMatch(/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?/)
  return w.replace(/\/$/, '')
}

/** Brouillon à lignes (panneaux + onduleur) envoyé, PUIS gamme « Premium » créée : rend source, sœur, lien source. */
async function sourceEnvoyeePuisGamme(r, tag) {
  const m = marque()
  const lead = await nouveauLead(r, `ADVS50 ${tag} ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produitEssai(r, `Panneau mono 550W ADVS50 ${m}`, '1000.00')
  const ond = await produitEssai(r, `Onduleur réseau 10kW ADVS50 ${m}`, '10000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12), ligne(ond, 1, 1)] },
  }), 'devis')
  const lien = await envoyer(r, d.id)
  const g = await r.post(`${API}/ventes/devis/${d.id}/dupliquer-variante-gamme/`, { ...T, data: { nom: 'Premium' } })
  const corps = await g.json().catch(() => ({}))
  expect(g.status(), `gamme créée après l'envoi (${J(corps).slice(0, 300)})`).toBe(201)
  return { d: await lire(r, d.id), soeurId: corps.gamme?.id, lien }
}

etape('PA3.renvoi_les_deux_page_client_carte_soeur', ['ADVS50'], async ({ page }) => {
  const r = page.request
  const { d, soeurId, lien } = await sourceEnvoyeePuisGamme(r, 'les-deux-ecran')
  expect(d.statut, 'source envoyée').toBe('envoye')
  expect((await lire(r, soeurId)).statut, 'sœur née brouillon').toBe('brouillon')
  const envoiAvant = d.date_envoi
  expect(envoiAvant, 'source tamponnée à son premier envoi').toBeTruthy()
  expect(await nbEnvoyes(d.id), 'source : UNE trace « Envoyé » avant le renvoi').toBe(1)

  // Page client AVANT le renvoi : la source seule, la sœur brouillon n'a pas de carte (mode d'envoi non « les deux »).
  const web = webBase()
  await page.goto(`${web}/proposition/${lien.token}`)
  await expect(page.locator('main, body').first()).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('[data-gamme-carte="soeur"]'), 'avant le renvoi : aucune carte de la sœur').toHaveCount(0)

  // Renvoi « les deux » (la route des écrans d'envoi).
  await envoyer(r, d.id, { gamme_envoi: 'les_deux' })
  const source = await lire(r, d.id)
  const soeur = await lire(r, soeurId)
  expect([source.statut, soeur.statut], 'source et sœur envoyées').toEqual(['envoye', 'envoye'])
  expect(source.date_envoi, 'source : date_envoi inchangée').toBe(envoiAvant)
  expect(await nbEnvoyes(d.id), 'source : aucun second « Envoyé » (aucun second devis_sent)').toBe(1)
  expect(await nbEnvoyes(soeurId), 'sœur : UNE trace « Envoyé »').toBe(1)
  const jetonsSoeur = await liens(soeurId)
  expect(jetonsSoeur.length, 'un lien vivant pour la sœur').toBe(1)

  // ÉCRAN — page client de la source, rechargée : la carte de la sœur est SERVIE au comparatif.
  for (const passage of ['ouverture', 'rechargement']) {
    if (passage === 'ouverture') await page.goto(`${web}/proposition/${lien.token}`)
    else await page.reload()
    const bloc = page.locator('#gammes')
    await expect(bloc, `(${passage}) section « Vos deux gammes » présente`).toHaveCount(1, { timeout: 120_000 })
    // Le repli natif <details> s'ouvre tout seul sans section de tailles ; sinon on l'ouvre par son titre.
    const pli = bloc.locator('details.gammes-fold')
    if (!(await pli.evaluate((e) => e.open))) await pli.locator('summary').click()
    const carteSoeur = page.locator('[data-gamme-carte="soeur"]')
    await expect(carteSoeur, `(${passage}) carte de la gamme sœur visible`).toBeVisible({ timeout: 60_000 })
    await expect(carteSoeur, `(${passage}) la carte nomme la gamme « Premium »`).toContainText('Premium')
    await expect(page.locator('[data-gamme-carte="courante"]'), `(${passage}) carte « Votre devis » visible`).toBeVisible()
    const href = await carteSoeur.locator('a[href]').first().getAttribute('href')
    expect(href, `(${passage}) le lien de la carte ouvre le jeton de la sœur`).toContain(jetonsSoeur[0])
  }
  // La page de la sœur elle-même se charge (jeton vivant).
  await page.goto(`${web}/proposition/${jetonsSoeur[0]}`)
  await expect(page.locator('body'), 'la page de la sœur est rendue (sa référence figure à l’écran)').toContainText(soeur.reference, { timeout: 120_000 })
  // Renvoi identique : aucun second lien pour la sœur.
  await envoyer(r, d.id, { gamme_envoi: 'les_deux' })
  expect((await liens(soeurId)).length, 'renvoi : toujours un seul lien de la sœur').toBe(1)
  expect(await nbEnvoyes(d.id), 'renvoi : toujours une seule trace « Envoyé » pour la source').toBe(1)
})

etape('PA3.renvoi_seule_soeur_brouillon_sans_carte', ['ADVS50'], async ({ page }) => {
  const r = page.request
  const { d, soeurId, lien } = await sourceEnvoyeePuisGamme(r, 'seule-ecran')
  await envoyer(r, d.id, { gamme_envoi: 'seule' })
  expect((await lire(r, soeurId)).statut, '« seule » : sœur brouillon').toBe('brouillon')
  expect((await liens(soeurId)).length, '« seule » : aucun lien pour la sœur').toBe(0)
  await page.goto(`${webBase()}/proposition/${lien.token}`)
  await expect(page.locator('main, body').first()).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('[data-gamme-carte="soeur"]'), '« seule » : la page client ne montre aucune carte de la sœur').toHaveCount(0)
})
