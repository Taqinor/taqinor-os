// Acceptation en direct — groupe ADVS, sixième lot (run 99392c vague 10) : preuve due d'ADVS50 — PA3 : source DÉJÀ
// envoyée, gamme sœur créée ENSUITE (`dupliquer-variante-gamme`), renvoi « les deux » ⇒ la sœur passe envoyée avec un
// lien vivant, la page client sert sa carte (jeton de la sœur dans `gammes.soeur.proposition_path`), la source n'est
// pas re-tamponnée, un second renvoi ne frappe aucun second lien ; « seule » : sœur brouillon.
// La page Astro `/proposition` n'est pas servie par la pile : la page se lit par son contrat public
// (`/public/proposal/<t>/data/`, celui qu'elle rend — même lecture que advs.spec.js). EMAIL backend console.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ADVS', ['ADVS50'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
const J = JSON.stringify
test.describe.configure({ timeout: 420_000 })
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
const donnees = async (r, token) => lireJson(await r.get(`${API}/public/proposal/${token}/data/`, T), 'charge publique')
const liens = (id) => py(`from apps.ventes.models import ShareLink
sortie([str(t) for t in ShareLink.objects.filter(devis_id=${Number(id)}).values_list('token', flat=True)])`)

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

etape('PA3.renvoi_les_deux_soeur_creee_apres', ['ADVS50'], async ({ page }) => {
  const r = page.request
  const { d, soeurId, lien } = await sourceEnvoyeePuisGamme(r, 'les-deux')
  expect(d.statut, 'source envoyée').toBe('envoye')
  expect((await lire(r, soeurId)).statut, 'sœur née brouillon').toBe('brouillon')
  const envoiAvant = d.date_envoi
  expect(envoiAvant, 'source tamponnée à son premier envoi').toBeTruthy()
  // Renvoi « les deux » (la route de l'envoi, celle des écrans d'envoi).
  await envoyer(r, d.id, { gamme_envoi: 'les_deux' })
  const source = await lire(r, d.id)
  const soeur = await lire(r, soeurId)
  expect([source.statut, soeur.statut], 'source et sœur envoyées').toEqual(['envoye', 'envoye'])
  expect(source.date_envoi, 'source : date_envoi inchangée (pas re-tamponnée)').toBe(envoiAvant)
  const jetonsSoeur = await liens(soeurId)
  expect(jetonsSoeur.length, 'un lien vivant pour la sœur').toBe(1)
  // Page client (charge publique de la source) : la carte de la sœur porte SON jeton.
  const pub = await donnees(r, lien.token)
  expect(pub.gammes?.soeur?.proposition_path, `carte de la sœur servie (${J(pub.gammes).slice(0, 300)})`).toContain(jetonsSoeur[0])
  // Le lien de la sœur ouvre bien sa propre page.
  const pubSoeur = await donnees(r, jetonsSoeur[0])
  expect(pubSoeur.reference ?? pubSoeur.quote?.reference ?? soeur.reference, 'la page de la sœur se charge').toBeTruthy()
  // Renvoi identique : aucun second lien pour la sœur ; la source n'a pas de seconde trace d'envoi.
  await envoyer(r, d.id, { gamme_envoi: 'les_deux' })
  expect((await liens(soeurId)).length, 'renvoi : toujours un seul lien de la sœur').toBe(1)
  expect((await lire(r, d.id)).date_envoi, 'renvoi : date_envoi de la source inchangée').toBe(envoiAvant)
  // Écran : liste des devis — la sœur y paraît « Envoyé » ; persistance : rechargement.
  for (let passe = 0; passe < 2; passe += 1) {
    if (passe === 0) await page.goto('/ventes/devis')
    else await page.reload()
    await page.getByPlaceholder('Rechercher (référence ou client)…').fill(soeur.reference, { timeout: 60_000 })
    const ligneEcran = page.locator('tr', { has: page.getByTestId(`ref-cell-${soeurId}`) }).first()
    await expect(ligneEcran).toBeVisible({ timeout: 60_000 })
    await expect(ligneEcran).toContainText(/Envoy/)
  }
})

etape('PA3.renvoi_seule_soeur_brouillon', ['ADVS50'], async ({ page }) => {
  const r = page.request
  const { d, soeurId } = await sourceEnvoyeePuisGamme(r, 'seule')
  await envoyer(r, d.id, { gamme_envoi: 'seule' })
  expect((await lire(r, soeurId)).statut, '« seule » : sœur brouillon').toBe('brouillon')
  expect((await liens(soeurId)).length, '« seule » : aucun lien pour la sœur').toBe(0)
  void page
})
