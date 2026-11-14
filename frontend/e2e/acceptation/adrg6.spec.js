// Preuves en direct du groupe ADRG, lot 6 (contre-visite du 14/11 : C-ADRG-VER2-204, C-ADRG-VER2-205) :
// ADRG127 (Ventes › Devis, menu de ligne : « Copier le lien de la proposition », « Copier l'aperçu interne » sous le
// droit de modifier, « Bon de commande (PDF) » sous le droit PDF) et ADRG128 (Ventes › Factures : « Aperçu du PDF »
// sous le droit PDF, barre d'actions de lot sous le code de route de chaque geste, aucune barre pour un Viewer).
// Comptes d'essai aux rôles SYSTÈME du registre (`init_roles`, relus par leur nom dans la société démo — jamais un
// rôle fabriqué), connectés par le VRAI écran de connexion. Données posées par demo_admin par les vraies routes, puis
// attribuées (created_by) au compte qui doit les voir ; Viewer et ce compte ont le même encadrant (portée « équipe »
// du Viewer : ses pairs). Persistance : n/a (rendu) — chaque écran est relu après rechargement.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, telephoneMobileUnique, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG127', 'ADRG128'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const J = (x) => JSON.stringify(x)
const SOC = `U.objects.get(username='demo_admin').company_id`
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })

/** Compte d'essai du rôle SYSTÈME `nomRole`, encadré par demo_admin ; renvoie son id. */
const compteDuRole = (nom, nomRole) => py(`from apps.roles.models import Role
u = compte(${J(nom)}, role=Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True).pk, societe=${SOC})
U.objects.filter(pk=u.pk).update(supervisor_id=U.objects.get(username='demo_admin').pk)
sortie(u.id)`)

/** Écran sous le compte `nom` : contexte neuf (SW bloqué), connexion par l'ÉCRAN de connexion, visites guidées
 *  marquées vues. La page demo_admin de l'étape est refermée à la première ouverture. */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1')
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
      const v = (t) => parts.find((x) => x.type === t).value
      localStorage.setItem('taqinor.prechargementTournee', `${v('year')}-${v('month')}-${v('day')}`)
    } catch { /* mode privé */ }
  })
  const p = suivi.surveiller(await ctx.newPage())
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return p
}

const produitDemo = async (r, m) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau ADRG6 ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'produit')
/** Devis posé par demo_admin (lead + ligne produit) ; `etat` : envoye ou accepte. */
async function devisDemo(r, m, etat, prod) {
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ADRG6 ${etat} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `adrg6${etat}${m}@example.invalid` } }), 'lead')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: prod.id, designation: prod.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  if (etat === 'accepte') await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADRG6' } }), 'accepter')
  return lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
}

// ───────── ADRG127 — menu de ligne des devis : Viewer sans les trois entrées, Commercial avec ─────────
etape('PF4.1-ADRG127', ['ADRG127'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const vi = { nom: `adrg127vi_${m}` }
  const co = { nom: `adrg127co_${m}` }
  vi.id = await compteDuRole(vi.nom, 'Viewer')
  co.id = await compteDuRole(co.nom, 'Commercial')
  const prod = await produitDemo(r, m)
  const envoye = await devisDemo(r, m, 'envoye', prod)
  let accepte = await devisDemo(r, m, 'accepte', prod)
  if (!accepte.bon_commande_etat?.exists) {
    await lireJson(await r.post(`${API}/ventes/devis/${accepte.id}/convertir-bc/`, T), 'convertir en BC')
    accepte = await lireJson(await r.get(`${API}/ventes/devis/${accepte.id}/`, T), 'devis accepté relu')
  }
  expect([envoye.statut, accepte.statut], 'Given : un devis envoyé, un devis accepté').toEqual(['envoye', 'accepte'])
  expect(accepte.bon_commande_etat?.exists, 'Given : un bon de commande lié').toBe(true)
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk__in=${J([envoye.id, accepte.id])}).update(created_by_id=${co.id})
sortie(1)`)
  // Ce que la ligne doit offrir (ou non) : [devis, nom de l'entrée].
  const ENTREES = [
    [envoye, /Copier le lien de la proposition/],
    [envoye, /Copier l.aperçu interne/],
    [accepte, /Bon de commande \(PDF\)/],
  ]
  for (const [qui, nom, present] of [['Viewer', vi.nom, false], ['Commercial', co.nom, true]]) {
    const p = await ecran(page, suivi, testInfo, nom)
    for (const recharger of [false, true]) {
      for (const [d, entree] of ENTREES) {
        await p.goto(`/ventes/devis?q=${encodeURIComponent(d.reference)}`)
        if (recharger) await p.reload()
        const passe = `${qui}${recharger ? ' (rechargé)' : ''}`
        const ligne = p.locator(`#devis-row-${d.id}`)
        await expect(ligne, `${passe} : ligne ${d.reference} affichée`).toBeVisible({ timeout: 60_000 })
        await ligne.getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
        const menu = p.getByRole('menu')
        await expect(menu.getByRole('menuitem', { name: 'Lien interne' }), `${passe} : menu ouvert`).toBeVisible()
        const it = menu.getByRole('menuitem', { name: entree })
        if (present) await expect(it, `${passe} ${d.statut} : « ${entree.source} » offert`).toBeVisible()
        else await expect(it, `${passe} ${d.statut} : aucune entrée « ${entree.source} »`).toHaveCount(0)
        await p.keyboard.press('Escape')
      }
    }
  }
})

// ───────── ADRG128 — liste des factures : Viewer sans aperçu ni barre de lot, Commercial responsable avec ─────────
etape('PF4.1-ADRG128', ['ADRG128'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const vi = { nom: `adrg128vi_${m}` }
  const cr = { nom: `adrg128cr_${m}` }
  vi.id = await compteDuRole(vi.nom, 'Viewer')
  cr.id = await compteDuRole(cr.nom, 'Commercial responsable')
  const prod = await produitDemo(r, m)
  const d = await devisDemo(r, m, 'accepte', prod)
  const rep = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'complete', emettre: true, remplacer_brouillons: true } }), 'facturer')
  const f = rep.facture
  expect(f.statut, 'Given : facture émise').toBe('emise')
  // « Avec PDF » : clé de stockage posée sur la facture (le rendu du PDF n'est pas l'objet du geste, seul le droit l'est).
  await py(`from apps.ventes.models import Facture
Facture.objects.filter(pk=${f.id}).update(created_by_id=${cr.id}, fichier_pdf='factures/ADRG128-${m}.pdf')
sortie(1)`)
  const BARRE = ['Émettre', 'Relancer', 'Envoyer par email', 'Générer le PDF', 'Encaissement groupé']
  for (const [qui, nom, present] of [['Viewer', vi.nom, false], ['Commercial responsable', cr.nom, true]]) {
    const p = await ecran(page, suivi, testInfo, nom)
    for (const recharger of [false, true]) {
      const passe = `${qui}${recharger ? ' (rechargé)' : ''}`
      await p.goto('/ventes/factures')
      if (recharger) await p.reload()
      const ligne = p.locator(`#facture-row-${f.id}`)
      await expect(ligne, `${passe} : facture ${f.reference} affichée`).toBeVisible({ timeout: 90_000 })
      // Menu de la ligne : « Aperçu du PDF ».
      const actions = ligne.getByRole('button', { name: /Actions/ })
      if (await actions.count()) {
        await actions.click()
        const apercu = p.getByRole('menuitem', { name: /Aperçu du PDF/ })
        if (present) await expect(apercu, `${passe} : « Aperçu du PDF » offert`).toBeVisible({ timeout: 30_000 })
        else {
          await p.waitForTimeout(500)
          await expect(apercu, `${passe} : aucune entrée « Aperçu du PDF »`).toHaveCount(0)
        }
        await p.keyboard.press('Escape')
      } else {
        expect(present, `${passe} : le menu « Actions » de la ligne existe`).toBe(false)
      }
      // Barre d'actions de lot après sélection de la ligne.
      await p.getByRole('checkbox', { name: `Sélectionner la facture ${f.reference}` }).check()
      const barre = p.getByRole('region', { name: 'Actions factures en masse' })
      if (present) {
        await expect(barre, `${passe} : barre de lot affichée`).toBeVisible({ timeout: 30_000 })
        for (const b of BARRE) await expect(barre.getByRole('button', { name: b, exact: true }), `${passe} : « ${b} »`).toBeVisible()
      } else {
        await expect(p.getByRole('checkbox', { name: `Sélectionner la facture ${f.reference}` }), `${passe} : ligne sélectionnée`).toBeChecked()
        await expect(barre, `${passe} : aucune barre de lot`).toHaveCount(0)
        for (const b of BARRE) await expect(p.getByRole('button', { name: b, exact: true }), `${passe} : aucun « ${b} »`).toHaveCount(0)
      }
    }
  }
})
