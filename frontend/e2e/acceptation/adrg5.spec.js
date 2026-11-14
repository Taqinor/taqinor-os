// Rejeu en direct du lot 5 du groupe ADRG (vérifie de clôture du 14/11/2026, constats C-ADRG-VER2-202 à 214,
// « l'écran suit la garde de la route ») : ADRG125 (rapports), ADRG129-131 (stock), ADRG132 (SAV), ADRG133-134
// (chantiers), ADRG135 (GED), ADRG136 (paramètres), ADRG137 (fiche lead). Chaque étape joue les RÔLES LIVRÉS du
// registre (rôles système `init_roles` de la société de demo_admin, relus par leur nom — jamais un rôle fabriqué),
// connectés par la vraie route `/token/` dans un navigateur à part : geste absent / inerte sous le rôle refusé,
// présent sous le rôle autorisé, appel réseau absent / présent, puis relecture après rechargement. Données propres
// créées par demo_admin (API ou shell Django) et retirées à la fin ; rendu seul, rien n'est écrit par les rôles.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ADRG', ['ADRG125', 'ADRG129', 'ADRG130', 'ADRG131', 'ADRG132', 'ADRG133', 'ADRG134',
  'ADRG135', 'ADRG136', 'ADRG137'])
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
const comptes = []
test.afterAll(async () => {
  if (!comptes.length) return
  await py(`U.objects.filter(username__in=${J(comptes)}).update(is_active=False)
sortie(1)`).catch(() => null)
})

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société (registre, `init_roles`). Renvoie {username, id}. */
async function compteDe(nomRole, prefixe) {
  const username = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True).pk
sortie(compte(${J(username)}, role=r, societe=${SOC}).id)`)
  comptes.push(username)
  return { username, id, nomRole }
}

/** Onglet NEUF (aucun cookie de demo_admin) connecté sous `c` par la vraie route `/token/`, observé par les
 *  oracles. `reseau` reçoit « MÉTHODE chemin → statut » de chaque réponse de l'API. */
async function ecranDe(page, suivi, testInfo, c) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  OUVERTS.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: c.username, password: MDP_ESSAI })
  // Visites guidées marquées vues (sinon leur bulle couvre les gestes à relire).
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
    if (u.pathname.startsWith(API)) reseau.push(`${r.request().method()} ${u.pathname.slice(API.length)} → ${r.status()}`)
  })
  return { ctx, p, reseau, api: ctx.request }
}
/** Lignes de `reseau` dont le chemin correspond à `re`. */
const appels = (reseau, re) => reseau.filter((l) => re.test(l.split(' ')[1]))
/** Attend une réponse GET dont le chemin correspond à `re`. */
const reponse = (p, re) => p.waitForResponse((r) => re.test(new URL(r.url()).pathname) && r.request().method() === 'GET', T)
const calme = (p) => p.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => undefined)
const bouton = (zone, nom) => zone.getByRole('button', { name: nom })

// ── ADRG125 — /rapports : chaque carte (ventes, stock, service) chargée selon la règle de sa route ─────────────
etape('PF4.4-ADRG125', ['ADRG125'], async ({ page, suivi, testInfo }) => {
  const RAPPORT = /^\/reporting\/reports\/(sales|stock|service)\/$/
  const CARTES = [['Ventes & pipeline', 'sales', 'Ventes & pipeline'], ['Stock', 'stock', 'Stock'],
    ['Service', 'service', 'Service (chantiers + SAV)']]
  for (const [nomRole, prefixe, permis] of [
    ['Technicien responsable', 'adrg125tr', ['service', 'stock']],
    ['Admin RH', 'adrg125rh', []],
    ['Directeur', 'adrg125di', ['sales', 'service', 'stock']],
  ]) {
    const c = await compteDe(nomRole, prefixe)
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of ['', 'relu après rechargement : ']) {
      s.reseau.length = 0
      const attendues = permis.map((k) => reponse(s.p, new RegExp(`/reporting/reports/${k}/$`)))
      if (passe) await s.p.reload(); else await s.p.goto('/rapports')
      for (const r of await Promise.all(attendues)) expect(r.status(), `${passe}${nomRole} : ${new URL(r.url()).pathname}`).toBe(200)
      await expect(s.p.getByRole('tab', { name: 'Stock', exact: true }), `${passe}${nomRole} : onglets des rapports`).toBeVisible(V)
      await calme(s.p)
      const lus = appels(s.reseau, RAPPORT).map((l) => `${RAPPORT.exec(l.split(' ')[1])[1]} ${l.split('→ ')[1]}`).sort()
      expect(lus, `${passe}${nomRole} : appels reporting/reports/* ${J(s.reseau.filter((l) => /reports/.test(l)))}`)
        .toEqual(permis.map((k) => `${k} 200`))
      for (const [onglet, cle, titre] of CARTES) {
        await s.p.getByRole('tab', { name: onglet, exact: true }).click()
        const panneau = s.p.getByRole('tabpanel')
        const carte = panneau.locator(':scope > div').filter({ has: s.p.getByText(titre, { exact: true }) })
        if (permis.includes(cle)) {
          await expect(carte, `${passe}${nomRole} : carte « ${titre} » rendue`).toHaveCount(1, V)
          await expect(carte.getByRole('button', { name: /Exporter Excel/ }), `${passe}${nomRole} : « ${titre} » chargée`).toBeVisible(V)
          await expect(carte, `${passe}${nomRole} : « ${titre} » sans erreur`).not.toContainText('Rapport indisponible')
        } else {
          await expect(carte, `${passe}${nomRole} : pas de carte « ${titre} » (ni erreur)`).toHaveCount(0)
        }
      }
    }
  }
})

// ── ADRG129 — export Excel SERVEUR du catalogue et des consignations sous `stock_export` ───────────────────────
etape('PF4.4-ADRG129', ['ADRG129'], async ({ page, suivi, testInfo }) => {
  const XLSX = /^\/stock\/produits\/export-xlsx\/$/
  for (const [nomRole, prefixe, exporte] of [['Commercial responsable', 'adrg129cr', false], ['Technicien responsable', 'adrg129tr', true]]) {
    const c = await compteDe(nomRole, prefixe)
    const s = await ecranDe(page, suivi, testInfo, c)
    for (const passe of ['', 'relu après rechargement : ']) {
      s.reseau.length = 0
      const charge = reponse(s.p, /^\/api\/django\/stock\/produits\/$/)
      if (passe) await s.p.reload(); else await s.p.goto('/stock')
      expect((await charge).status(), `${passe}${nomRole} : catalogue lu`).toBe(200)
      const exporter = s.p.getByRole('button', { name: /^Exporter$/ })
      await expect(exporter.first(), `${passe}${nomRole} : barre de la table catalogue`).toBeVisible(V)
      await calme(s.p)
      if (exporte) {
        // Témoin : le bouton de la table appelle l'export Excel SERVEUR (route `stock_export`), servi.
        const [rep] = await Promise.all([
          s.p.waitForResponse((r) => XLSX.test(new URL(r.url()).pathname.slice(API.length)), T),
          exporter.first().click(),
        ])
        expect(rep.status(), `${passe}${nomRole} : export Excel serveur servi`).toBe(200)
      } else {
        // Le bouton générique « Exporter » du moteur DataTable reste (repli CSV NAVIGATEUR, ADRG77 / D-ADRG-4) :
        // il ne doit plus offrir l'export serveur. Cliqué : un .csv local, aucune requête export-xlsx.
        const [dl] = await Promise.all([s.p.waitForEvent('download', T), exporter.first().click()])
        expect(dl.suggestedFilename(), `${passe}${nomRole} : export CSV local du navigateur`).toMatch(/\.csv$/)
        await calme(s.p)
        expect(appels(s.reseau, XLSX), `${passe}${nomRole} : aucune requête d'export Excel serveur`).toEqual([])
      }
    }
    // Consignations : « Exporter (Excel) » (route `stock/consignations/export-xlsx/` : `stock_export`).
    for (const passe of ['', 'relu après rechargement : ']) {
      if (passe) await s.p.reload(); else await s.p.goto('/stock/negoce/consignations')
      await expect(s.p.getByText('Dépôts chez les clients'), `${passe}${nomRole} : carte des dépôts`).toBeVisible(V)
      await calme(s.p)
      await expect(bouton(s.p, 'Exporter (Excel)'), `${passe}${nomRole} : « Exporter (Excel) »`).toHaveCount(exporte ? 1 : 0)
    }
  }
})

// ── ADRG130 — Quais (ASN, quais) et Picking (génération des comptages) : gestes = garde de leur route ──────────
etape('PF4.4-ADRG130', ['ADRG130'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nomQuai = `Quai ADRG130 ${m}`
  const q = await py(`from apps.stock.models import EmplacementStock
from apps.stock.models_wms import Quai
e = EmplacementStock.objects.filter(company_id=${SOC}).order_by('pk').first()
if e is None:
    e = EmplacementStock.objects.create(company_id=${SOC}, nom=${J(`Dépôt ADRG130 ${m}`)})
sortie(Quai.objects.create(company_id=${SOC}, nom=${J(nomQuai)}, emplacement=e, actif=True).pk)`)
  try {
    for (const [nomRole, prefixe, asn, admin] of [
      ['Commercial responsable', 'adrg130cr', false, false],
      ['Technicien', 'adrg130te', true, false],
      ['Directeur', 'adrg130di', true, true],
    ]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        const charge = reponse(s.p, /^\/api\/django\/stock\/quais\/$/)
        if (passe) await s.p.reload(); else await s.p.goto('/stock/entrepot/quais')
        expect((await charge).status(), `${passe}${nomRole} : quais lus`).toBe(200)
        await expect(s.p.getByText(nomQuai), `${passe}${nomRole} : quai listé`).toBeVisible(V)
        await calme(s.p)
        await expect(s.p.getByText('Fichier ASN', { exact: true }), `${passe}${nomRole} : « Fichier ASN »`).toHaveCount(asn ? 1 : 0)
        await expect(bouton(s.p, 'Ajouter le quai'), `${passe}${nomRole} : « Ajouter le quai »`).toHaveCount(admin ? 1 : 0)
        await expect(bouton(s.p, `Désactiver le quai ${nomQuai}`), `${passe}${nomRole} : « Désactiver » du quai`).toHaveCount(admin ? 1 : 0)
        if (!admin) await expect(bouton(s.p, /^(Activer|Désactiver) le quai /), `${passe}${nomRole} : aucun Activer/Désactiver`).toHaveCount(0)
      }
      for (const passe of ['', 'relu après rechargement : ']) {
        if (passe) await s.p.reload(); else await s.p.goto('/stock/entrepot/picking')
        await expect(s.p.getByRole('tab', { name: 'Comptages' }), `${passe}${nomRole} : onglets du picking`).toBeVisible(V)
        const plans = reponse(s.p, /^\/api\/django\/stock\/plans-comptage-tournant\/$/)
        await s.p.getByRole('tab', { name: 'Comptages' }).click()
        expect((await plans).status(), `${passe}${nomRole} : plans de comptage lus`).toBe(200)
        await expect(s.p.getByText('Comptages tournants').first(), `${passe}${nomRole} : carte des comptages`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(s.p, 'Générer les comptages'), `${passe}${nomRole} : « Générer les comptages »`).toHaveCount(admin ? 1 : 0)
      }
    }
    expect(await py(`from apps.stock.models_wms import Quai
sortie(Quai.objects.get(pk=${q}).actif)`), 'relu : quai toujours actif (rendu seul)').toBe(true)
  } finally {
    await py(`from apps.stock.models_wms import Quai
Quai.objects.filter(pk=${q}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG131 — « Supprimer le profil » saisonnier (PeutSupprimerStock) et « Soumettre pour validation »
//    (valider_dossier_fournisseur) ────────────────────────────────────────────────────────────────────────────
etape('PF4.4-ADRG131', ['ADRG131'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nomProduit = `Onduleur ADRG131 ${m}`
  const nomProfil = `Saison ADRG131 ${m}`
  const nomFournisseur = `Fournisseur ADRG131 ${m}`
  const x = await py(`from apps.stock.models import Produit, ProfilSaisonnier, Fournisseur, DossierOnboardingFournisseur, DocumentFournisseur
co = ${SOC}
p = Produit.objects.create(company_id=co, nom=${J(nomProduit)}, prix_vente='1000.00', prix_achat='600.00')
pr = ProfilSaisonnier.objects.create(company_id=co, produit=p, nom=${J(nomProfil)}, mois_debut=4, mois_fin=9, seuil_min=2, quantite_cible=5)
f = Fournisseur.objects.create(company_id=co, nom=${J(nomFournisseur)})
d = DossierOnboardingFournisseur.objects.create(company_id=co, fournisseur=f)
for t in DocumentFournisseur.TYPES_REQUIS:
    DocumentFournisseur.objects.create(company_id=co, dossier=d, type_document=t, file_key='acceptation/adrg131/' + t + '.pdf', filename=t + '.pdf', mime='application/pdf', taille=10)
sortie(dict(produit=p.pk, profil=pr.pk, fournisseur=f.pk, dossier=d.pk))`)
  try {
    for (const [nomRole, prefixe, autorise] of [['Technicien responsable', 'adrg131tr', false], ['Directeur', 'adrg131di', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        // Fiche produit : catalogue filtré → menu de la ligne → « Fiche produit » → onglet « Saison de réappro ».
        const charge = reponse(s.p, /^\/api\/django\/stock\/produits\/$/)
        await s.p.goto('/stock')
        expect((await charge).status(), `${passe}${nomRole} : catalogue lu`).toBe(200)
        await s.p.getByPlaceholder('Chercher partout…').fill(nomProduit)
        const ligne = s.p.getByRole('row').filter({ hasText: nomProduit }).first()
        await expect(ligne, `${passe}${nomRole} : produit listé`).toBeVisible(V)
        await ligne.getByRole('button', { name: "Plus d'actions sur la ligne" }).click()
        await s.p.getByRole('menuitem', { name: /Fiche produit/ }).click()
        const fiche = s.p.getByRole('dialog').filter({ hasText: nomProduit }).last()
        await expect(fiche, `${passe}${nomRole} : fiche produit ouverte`).toBeVisible(V)
        const profils = reponse(s.p, /^\/api\/django\/stock\/profils-saisonniers\/$/)
        await fiche.getByRole('tab', { name: 'Saison de réappro' }).click()
        expect((await profils).status(), `${passe}${nomRole} : profils saisonniers lus`).toBe(200)
        const profil = fiche.getByTestId(`profil-saisonnier-${x.profil}`)
        await expect(profil, `${passe}${nomRole} : profil listé`).toBeVisible(V)
        await expect(bouton(profil, `Modifier le profil ${nomProfil}`), `${passe}${nomRole} : « Modifier » (stock_modifier)`).toBeVisible()
        await expect(bouton(profil, `Supprimer le profil ${nomProfil}`), `${passe}${nomRole} : « Supprimer le profil »`).toHaveCount(autorise ? 1 : 0)
        await s.p.keyboard.press('Escape')
        // Dossier fournisseur : fiche 360 → onglet Onboarding → récapitulatif (étape 3/3, dossier complet).
        const dossier = reponse(s.p, new RegExp(`/stock/fournisseurs/${x.fournisseur}/onboarding/$`))
        await s.p.goto(`/stock/fournisseurs/${x.fournisseur}/360`)
        await s.p.getByRole('tab', { name: /Onboarding/ }).click()
        expect((await dossier).status(), `${passe}${nomRole} : dossier d'onboarding lu`).toBe(200)
        const suivant = s.p.getByTestId('onboarding-suivant')
        await expect(suivant, `${passe}${nomRole} : assistant d'onboarding`).toBeVisible(V)
        await suivant.click()
        await expect(suivant, `${passe}${nomRole} : dossier complet (récapitulatif ouvert)`).toBeEnabled(V)
        await suivant.click()
        await expect(s.p.getByText(/Étape 3\/3/), `${passe}${nomRole} : récapitulatif`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(s.p, 'Soumettre pour validation'), `${passe}${nomRole} : « Soumettre pour validation »`).toHaveCount(autorise ? 1 : 0)
      }
    }
    expect(await py(`from apps.stock.models import ProfilSaisonnier, DossierOnboardingFournisseur
sortie([ProfilSaisonnier.objects.filter(pk=${x.profil}).exists(), DossierOnboardingFournisseur.objects.get(pk=${x.dossier}).statut])`),
    'relu : profil présent, dossier toujours en attente (rendu seul)').toEqual([true, 'en_attente'])
  } finally {
    await py(`from apps.stock.models import Produit, ProfilSaisonnier, Fournisseur, DossierOnboardingFournisseur, DocumentFournisseur
DocumentFournisseur.objects.filter(dossier_id=${x.dossier}).delete()
DossierOnboardingFournisseur.objects.filter(pk=${x.dossier}).delete()
ProfilSaisonnier.objects.filter(pk=${x.profil}).delete()
Fournisseur.objects.filter(pk=${x.fournisseur}).delete()
Produit.objects.filter(pk=${x.produit}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG132 — catégories d'équipement sous `equipement_gerer`, feuille de maintenance sous `sav_gerer` ─────────
etape('PF4.4-ADRG132', ['ADRG132'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const nomCat = `Cat ADRG132 ${m}`
  const cr = await compteDe('Commercial responsable', 'adrg132cr')
  const co = await compteDe('Commercial', 'adrg132co')
  const tr = await compteDe('Technicien responsable', 'adrg132tr')
  const cl = await lireJson(await r.post(`${API}/crm/clients/`, { ...T, data: { nom: `ADRG132 ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `adrg132_${m}@example.invalid` } }), 'client')
  const ticket = await lireJson(await r.post(`${API}/sav/tickets/`, { ...T, data: { client: cl.id, type: 'correctif', description: `ADRG132 ${m}` } }), 'ticket')
  // Société à feuilles de maintenance ACTIVES ; le ticket porte une feuille (le Technicien responsable la lit en 200).
  const x = await py(`from apps.sav.models import SavSlaSettings, WorksheetMaintenanceModele, TicketWorksheet, Ticket, CategorieEquipement
from apps.authentication.models import Company
co = Company.objects.get(pk=${SOC})
sla = SavSlaSettings.get(co)
avant = sla.worksheets_maintenance_actifs
sla.worksheets_maintenance_actifs = True
sla.save()
mo = WorksheetMaintenanceModele.objects.create(company=co, nom=${J(`Feuille ADRG132 ${m}`)}, champs=[])
TicketWorksheet.objects.create(company=co, ticket_id=${ticket.id}, modele=mo)
Ticket.objects.filter(pk=${ticket.id}).update(created_by_id=${co.id}, technicien_responsable_id=${tr.id})
cat = CategorieEquipement.objects.create(company=co, nom=${J(nomCat)})
sortie(dict(avant=avant, modele=mo.pk, cat=cat.pk))`)
  const WORKSHEET = new RegExp(`^/sav/tickets/${ticket.id}/worksheet/$`)
  try {
    // 1) /sav/parametres › Catégories d'équipement.
    for (const [c, gere] of [[cr, false], [tr, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        if (passe) await s.p.reload(); else await s.p.goto('/sav/parametres')
        await expect(s.p.getByRole('heading', { name: 'Paramètres SAV' }), `${passe}${c.nomRole} : paramètres SAV`).toBeVisible(V)
        const lues = reponse(s.p, /^\/api\/django\/sav\/categories-equipement\/$/)
        await s.p.getByRole('tab', { name: "Catégories d'équipement" }).click()
        expect((await lues).status(), `${passe}${c.nomRole} : catégories lues`).toBe(200)
        const panneau = s.p.getByRole('tabpanel')
        await expect(panneau.getByText(nomCat), `${passe}${c.nomRole} : catégorie listée`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(panneau, /Ajouter/), `${passe}${c.nomRole} : « Ajouter »`).toHaveCount(gere ? 1 : 0)
        await expect(panneau.getByPlaceholder('Nouvelle catégorie…'), `${passe}${c.nomRole} : saisie d'une nouvelle catégorie`).toHaveCount(gere ? 1 : 0)
        const ligne = panneau.getByRole('listitem').filter({ hasText: nomCat })
        await expect(bouton(ligne, /Enregistrer/), `${passe}${c.nomRole} : « Enregistrer » de la catégorie`).toHaveCount(gere ? 1 : 0)
      }
    }
    // 2) Fiche du ticket : Commercial (sav_voir sans sav_gerer) → aucun GET worksheet ; Technicien responsable → panneau.
    for (const [c, gere] of [[co, false], [tr, true]]) {
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        s.reseau.length = 0
        const feuille = gere ? s.p.waitForResponse((x2) => WORKSHEET.test(new URL(x2.url()).pathname.slice(API.length)), T) : null
        await s.p.goto(`/sav?id=${ticket.id}`)
        const fiche = s.p.locator('aside[aria-label^="Détail du ticket"], [role="dialog"]').filter({ hasText: 'Feuille de maintenance' }).first()
        await expect(fiche, `${passe}${c.nomRole} : fiche ticket ouverte`).toBeVisible(V)
        if (gere) {
          expect((await feuille).status(), `${passe}${c.nomRole} : feuille de maintenance lue`).toBe(200)
          await expect(fiche.getByText(`Feuille ADRG132 ${m}`), `${passe}${c.nomRole} : panneau de la feuille`).toBeVisible(V)
        }
        await calme(s.p)
        const vus = appels(s.reseau, WORKSHEET)
        if (gere) {
          expect(vus.length, `${passe}${c.nomRole} : lecture de la feuille ${J(vus)}`).toBeGreaterThanOrEqual(1)
        } else {
          expect(vus, `${passe}${c.nomRole} : aucune requête worksheet`).toEqual([])
          await expect(fiche.getByText(`Feuille ADRG132 ${m}`), `${passe}${c.nomRole} : pas de panneau de feuille`).toHaveCount(0)
        }
      }
    }
    expect(await py(`from apps.sav.models import CategorieEquipement, TicketWorksheet
sortie([CategorieEquipement.objects.get(pk=${x.cat}).nom, TicketWorksheet.objects.get(ticket_id=${ticket.id}).complete])`),
    'relu : catégorie et feuille inchangées').toEqual([nomCat, false])
  } finally {
    await py(`from apps.sav.models import SavSlaSettings, WorksheetMaintenanceModele, TicketWorksheet, CategorieEquipement
from apps.authentication.models import Company
co = Company.objects.get(pk=${SOC})
TicketWorksheet.objects.filter(ticket_id=${ticket.id}).delete()
WorksheetMaintenanceModele.objects.filter(pk=${x.modele}).delete()
CategorieEquipement.objects.filter(pk=${x.cat}).delete()
sla = SavSlaSettings.get(co); sla.worksheets_maintenance_actifs = ${x.avant ? 'True' : 'False'}; sla.save()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG133 — « Rejeter » / « Approuver l'étape » d'un plan d'approbation sous `approuver_demande_achat` ───────
etape('PF4.4-ADRG133', ['ADRG133'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const r = page.request
  const objet = `Demande ADRG133 ${m}`
  const da = await lireJson(await r.post(`${API}/installations/demandes-achat/`, { ...T, data: { objet } }), 'demande d\'achat')
  try {
    const soumise = await lireJson(await r.post(`${API}/installations/demandes-achat/${da.id}/soumettre/`, { ...T, data: {} }), 'soumettre')
    expect(soumise.statut, 'demande soumise').toBe('soumise')
    // Plan d'approbation : une étape EN ATTENTE (créée si aucune règle de la société n'en a instancié).
    await py(`from apps.installations.models_approbation_achat import EtapeApprobationAchat
if not EtapeApprobationAchat.objects.filter(demande_id=${da.id}, statut='en_attente').exists():
    EtapeApprobationAchat.objects.create(company_id=${SOC}, demande_id=${da.id}, niveau=1, statut='en_attente')
sortie(1)`)
    for (const [nomRole, prefixe, present] of [['Technicien responsable', 'adrg133tr', false], ['Directeur', 'adrg133di', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        const plan = reponse(s.p, new RegExp(`/installations/demandes-achat/${da.id}/etapes-approbation/$`))
        await s.p.goto(`/chantiers/demandes-achat?da=${da.id}`)
        await expect(s.p.getByText(objet).first(), `${passe}${nomRole} : détail ouvert`).toBeVisible(V)
        expect((await plan).status(), `${passe}${nomRole} : plan d'approbation lu`).toBe(200)
        const zone = s.p.locator('[aria-label="Plan d\'approbation"]')
        await expect(zone.getByText(/Niveau 1/), `${passe}${nomRole} : étape en attente affichée`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(zone, 'Rejeter'), `${passe}${nomRole} : « Rejeter »`).toHaveCount(present ? 1 : 0)
        await expect(bouton(zone, "Approuver l'étape"), `${passe}${nomRole} : « Approuver l'étape »`).toHaveCount(present ? 1 : 0)
      }
    }
    expect(await py(`from apps.installations.models_approbation_achat import EtapeApprobationAchat
from apps.installations.models_demande_achat import DemandeAchat
sortie([DemandeAchat.objects.get(pk=${da.id}).statut, EtapeApprobationAchat.objects.filter(demande_id=${da.id}, statut='en_attente').count() > 0])`),
    'relu : demande soumise, étape toujours en attente').toEqual(['soumise', true])
  } finally {
    await py(`from apps.installations.models_demande_achat import DemandeAchat
DemandeAchat.objects.filter(pk=${da.id}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG134 — /interventions ne lit `crm/assignable-users/` que si `useCanListAssignableUsers` le permet ───────
etape('PF4.4-ADRG134', ['ADRG134'], async ({ page, suivi, testInfo }) => {
  const ASSIGNABLES = /^\/crm\/assignable-users\/$/
  for (const [nomRole, prefixe, lit] of [['Technicien', 'adrg134te', false], ['Commercial responsable', 'adrg134cr', true]]) {
    const c = await compteDe(nomRole, prefixe)
    const s = await ecranDe(page, suivi, testInfo, c)
    if (nomRole === 'Technicien') {
      // Accord de suivi GPS d'un compte terrain neuf (sinon l'écran d'accord remplace l'app) — même geste qu'adrg4.
      await lireJson(await s.api.get(`${API}/installations/gps-consentements/mon-consentement/`, T), 'accord GPS à donner')
      const accord = await s.api.post(`${API}/installations/gps-consentements/mon-consentement/accepter/`, T)
      expect(accord.ok(), `accord GPS donné (${accord.status()})`).toBeTruthy()
    }
    for (const passe of ['', 'relu après rechargement : ']) {
      s.reseau.length = 0
      const liste = reponse(s.p, /^\/api\/django\/installations\/interventions\/$/)
      const users = lit ? reponse(s.p, /^\/api\/django\/crm\/assignable-users\/$/) : null
      if (passe) await s.p.reload(); else await s.p.goto('/interventions')
      expect((await liste).status(), `${passe}${nomRole} : interventions lues`).toBe(200)
      if (lit) expect((await users).status(), `${passe}${nomRole} : utilisateurs assignables servis`).toBe(200)
      await calme(s.p)
      await expect(s.p.getByText('Impossible de charger les interventions'), `${passe}${nomRole} : écran rendu`).toHaveCount(0)
      const vus = appels(s.reseau, ASSIGNABLES)
      if (lit) {
        expect(vus.length, `${passe}${nomRole} : lecture des utilisateurs assignables ${J(vus)}`).toBeGreaterThanOrEqual(1)
        expect(vus.every((l) => l.endsWith('→ 200')), `${passe}${nomRole} : ${J(vus)}`).toBe(true)
      } else {
        expect(vus, `${passe}${nomRole} : aucune lecture crm/assignable-users/`).toEqual([])
      }
    }
  }
})

// ── ADRG135 — « Restaurer » une version sous `ged_gerer` ; politiques et dispositions sous `ged_gouvernance` ───
const PDF = (n) => Buffer.from(`%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n% version ${n}\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF\n`)
/** Libellés des entrées d'un menu ouvert (Radix), menu refermé ensuite. */
async function entreesMenu(p) {
  const menu = p.getByRole('menu')
  await expect(menu, 'menu ouvert').toBeVisible({ timeout: 30_000 })
  const textes = (await menu.getByRole('menuitem').allInnerTexts()).map((x) => x.replace(/\s+/g, ' ').trim())
  await p.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  return textes
}
etape('PF4.4-ADRG135', ['ADRG135'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const m = marque()
  const GED = `${API}/ged`
  const cab = await lireJson(await r.post(`${GED}/cabinets/`, { ...T, data: { nom: `Cab ADRG135 ${m}` } }), 'armoire')
  const dos = await lireJson(await r.post(`${GED}/dossiers/`, { ...T, data: { nom: `Dos ADRG135 ${m}`, cabinet: cab.id } }), 'dossier')
  const doc = await lireJson(await r.post(`${GED}/documents/`, { ...T, data: { nom: `Plan ADRG135 ${m}`, folder: dos.id } }), 'document')
  for (const n of [1, 2]) {
    await lireJson(await r.post(`${GED}/documents/${doc.id}/nouvelle-version/`, { ...T, multipart: { file: { name: `plan-v${n}.pdf`, mimeType: 'application/pdf', buffer: PDF(n) } } }), `version ${n}`)
  }
  const politique = `Politique ADRG135 ${m}`
  const dispoAttente = `Dispo attente ADRG135 ${m}`
  const dispoApprouvee = `Dispo approuvée ADRG135 ${m}`
  const x = await py(`from apps.ged.models import PolitiqueRetention, DemandeDisposition
a = U.objects.get(username='demo_admin')
p = PolitiqueRetention.objects.create(company_id=${SOC}, nom=${J(politique)}, folder_id=${dos.id}, duree_conservation_jours=3650, created_by=a)
d1 = DemandeDisposition.objects.create(company_id=${SOC}, libelle=${J(dispoAttente)}, documents=[], statut='en_attente', demandeur=a)
d2 = DemandeDisposition.objects.create(company_id=${SOC}, libelle=${J(dispoApprouvee)}, documents=[], statut='approuvee', demandeur=a, approbateur=a, decision_le=timezone.now())
sortie(dict(politique=p.pk, d1=d1.pk, d2=d2.pk))`)
  try {
    // 1) « Versions… » de l'aperçu : Viewer (ged_voir seul) sans « Restaurer », Directeur avec.
    for (const [nomRole, prefixe, gere] of [['Viewer', 'adrg135vi', false], ['Directeur', 'adrg135di', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        await s.p.goto('/ged')
        const choix = s.p.getByRole('combobox', { name: 'Choisir le cabinet' })
        await expect(s.p.getByRole('tree', { name: 'Dossiers' }).or(choix).first(), `${passe}${nomRole} : GED rendue`).toBeVisible(V)
        if (await choix.count()) {
          await choix.click()
          await s.p.getByRole('option', { name: cab.nom, exact: true }).click()
        }
        await s.p.getByRole('treeitem').filter({ hasText: dos.nom }).getByRole('button').first().click()
        await s.p.getByRole('button', { name: `Aperçu de ${doc.nom}` }).click()
        const apercu = s.p.getByRole('dialog').filter({ hasText: doc.nom })
        await expect(bouton(apercu, /Versions…/), `${passe}${nomRole} : « Versions… » (deux versions)`).toBeVisible(V)
        await bouton(apercu, /Versions…/).click()
        const versions = s.p.getByRole('dialog').filter({ has: s.p.getByRole('heading', { name: 'Versions du document' }) })
        await expect(versions.getByText(/\(actuelle\)/), `${passe}${nomRole} : liste des versions`).toBeVisible(V)
        await expect(versions.getByText(/^v1/), `${passe}${nomRole} : version antérieure listée`).toBeVisible()
        await expect(bouton(versions, /Restaurer/), `${passe}${nomRole} : « Restaurer »`).toHaveCount(gere ? 1 : 0)
        await s.p.keyboard.press('Escape')
        await s.p.keyboard.press('Escape')
      }
    }
    // 2) /ged/retention : Commercial responsable (ged_gerer sans ged_gouvernance) sans geste ; Directeur avec tous.
    for (const [nomRole, prefixe, gouv] of [['Commercial responsable', 'adrg135cr', false], ['Directeur', 'adrg135d2', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        if (passe) await s.p.reload(); else await s.p.goto('/ged/retention')
        const lignePol = s.p.getByRole('row').filter({ hasText: politique })
        await expect(lignePol, `${passe}${nomRole} : politique listée`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(s.p, /Nouvelle politique/), `${passe}${nomRole} : « Nouvelle politique »`).toHaveCount(gouv ? 1 : 0)
        const kebabPol = lignePol.getByRole('button', { name: "Plus d'actions sur la ligne" })
        if (gouv) {
          await kebabPol.click()
          const menu = await entreesMenu(s.p)
          expect(menu.some((t) => /Supprimer/.test(t)), `Directeur : « Supprimer » la politique ${J(menu)}`).toBe(true)
        } else {
          await expect(kebabPol, `${passe}${nomRole} : aucune action sur la politique`).toHaveCount(0)
        }
        await s.p.getByRole('tab', { name: 'Dispositions' }).click()
        for (const [libelle, geste] of [[dispoAttente, /Approuver/], [dispoApprouvee, /Exécuter/]]) {
          const ligne = s.p.getByRole('row').filter({ hasText: libelle })
          await expect(ligne, `${passe}${nomRole} : disposition « ${libelle} » listée`).toBeVisible(V)
          const kebab = ligne.getByRole('button', { name: "Plus d'actions sur la ligne" })
          if (gouv) {
            await kebab.click()
            const menu = await entreesMenu(s.p)
            expect(menu.some((t) => geste.test(t)), `Directeur : ${geste} sur « ${libelle} » ${J(menu)}`).toBe(true)
          } else {
            await expect(kebab, `${passe}${nomRole} : aucune action sur « ${libelle} »`).toHaveCount(0)
          }
        }
      }
    }
    expect(await py(`from apps.ged.models import PolitiqueRetention, DemandeDisposition, DocumentVersion
sortie([PolitiqueRetention.objects.filter(pk=${x.politique}).exists(), DemandeDisposition.objects.get(pk=${x.d1}).statut, DemandeDisposition.objects.get(pk=${x.d2}).statut, DocumentVersion.objects.filter(document_id=${doc.id}).count()])`),
    'relu : politique présente, dispositions inchangées, deux versions (rien restauré)').toEqual([true, 'en_attente', 'approuvee', 2])
  } finally {
    await py(`from apps.ged.models import PolitiqueRetention, DemandeDisposition
PolitiqueRetention.objects.filter(pk=${x.politique}).delete()
DemandeDisposition.objects.filter(pk__in=[${x.d1}, ${x.d2}]).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG136 — « Aperçu » / « Aperçu du rendu » d'un modèle brandé sous `parametres_modifier` ───────────────────
etape('PF4.4-ADRG136', ['ADRG136'], async ({ page, suivi, testInfo }) => {
  const m = marque()
  const nom = `Modèle ADRG136 ${m}`
  const id = await py(`from core.models import BrandedTemplate
sortie(BrandedTemplate.objects.create(company_id=${SOC}, kind='email', code=${J(`adrg136_${m}`)}, nom=${J(nom)}, sujet='Essai', corps='Bonjour {{ client.nom }}').pk)`)
  try {
    for (const [nomRole, prefixe, modif] of [['Commercial responsable', 'adrg136cr', false], ['Directeur', 'adrg136di', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        const liste = reponse(s.p, /\/core\/branded-templates\/?$/)
        if (passe) await s.p.reload(); else await s.p.goto('/parametres?onglet=modeles_brandes')
        expect((await liste).status(), `${passe}${nomRole} : modèles lus`).toBe(200)
        const ligne = s.p.getByTestId(`modele-brande-email-adrg136_${m}`)
        await expect(ligne, `${passe}${nomRole} : modèle listé`).toBeVisible(V)
        await calme(s.p)
        await expect(bouton(ligne, /Aperçu/), `${passe}${nomRole} : « Aperçu » de la ligne`).toHaveCount(modif ? 1 : 0)
        await bouton(ligne, nom).click()
        await expect(s.p.getByRole('textbox', { name: "Contexte d'exemple" }), `${passe}${nomRole} : éditeur du modèle ouvert`).toBeVisible(V)
        await expect(bouton(s.p, /Aperçu du rendu/), `${passe}${nomRole} : « Aperçu du rendu »`).toHaveCount(modif ? 1 : 0)
        if (modif && !passe) {
          // Témoin : l'aperçu du Directeur est servi par la route (POST …/preview/ : parametres_modifier).
          const [rep] = await Promise.all([
            s.p.waitForResponse((x2) => new RegExp(`/core/branded-templates/${id}/preview/$`).test(new URL(x2.url()).pathname), T),
            bouton(s.p, /Aperçu du rendu/).click(),
          ])
          expect(rep.status(), 'Directeur : aperçu servi').toBe(200)
        }
      }
    }
  } finally {
    await py(`from core.models import BrandedTemplate
BrandedTemplate.objects.filter(pk=${id}).delete()
sortie(1)`).catch(() => null)
  }
})

// ── ADRG137 — gestes d'écriture du rail d'identité de la fiche lead inertes sans `crm_modifier` ───────────────
etape('PF4.4-ADRG137', ['ADRG137'], async ({ page, suivi, testInfo }) => {
  const crees = []
  try {
    for (const [nomRole, prefixe, actif] of [['Viewer', 'adrg137vi', false], ['Commercial', 'adrg137co', true]]) {
      const c = await compteDe(nomRole, prefixe)
      const m = marque()
      const tel = telephoneMobileUnique()
      // Lead du rôle (portée « soi ») : un doublon (même téléphone), une suggestion de segment (note « forage »),
      // un client lié dont l'identité diffère (bandeau « Mettre à jour la fiche client »).
      const x = await py(`from apps.crm.models import Lead, Client
co = ${SOC}
cl = Client.objects.create(company_id=co, nom=${J(`Autre ADRG137 ${m}`)}, prenom='Ancien', email=${J(`adrg137c_${m}@example.invalid`)}, telephone=${J(telephoneMobileUnique())})
l = Lead.objects.create(company_id=co, owner_id=${c.id}, nom=${J(`ADRG137 ${m}`)}, prenom='Essai', telephone=${J(tel)}, email=${J(`adrg137_${m}@example.invalid`)}, note='Irrigation : pompe pour le forage de la ferme', client=cl)
d = Lead.objects.create(company_id=co, owner_id=${c.id}, nom=${J(`ADRG137 doublon ${m}`)}, prenom='Essai', telephone=${J(tel)})
sortie(dict(lead=l.pk, dup=d.pk, client=cl.pk, type=l.type_installation or ''))`)
      crees.push(x)
      const s = await ecranDe(page, suivi, testInfo, c)
      for (const passe of ['', 'relu après rechargement : ']) {
        const detail = reponse(s.p, new RegExp(`/crm/leads/${x.lead}/$`))
        const doublons = reponse(s.p, new RegExp(`/crm/leads/${x.lead}/duplicates/$`))
        if (passe) await s.p.reload(); else await s.p.goto(`/crm/leads/${x.lead}`)
        expect((await detail).status(), `${passe}${nomRole} : fiche lue`).toBe(200)
        expect((await doublons).status(), `${passe}${nomRole} : doublons lus`).toBe(200)
        const rail = s.p.getByTestId('lw-identity-rail')
        await expect(rail, `${passe}${nomRole} : rail d'identité`).toBeVisible(V)
        await calme(s.p)
        const gestes = [
          ['Examiner (doublon)', bouton(rail, 'Examiner')],
          ['Mettre à jour la fiche client', bouton(rail.getByTestId('lw-client-lie'), 'Mettre à jour la fiche client')],
          ['Passer en <segment>', bouton(rail.getByTestId('lw-segment-suggere'), /^Passer en /)],
          ['Relance le', rail.locator('.lw-rail-field').filter({ hasText: 'Relance le' }).getByRole('button').first()],
        ]
        for (const [quoi, g] of gestes) {
          await expect(g, `${passe}${nomRole} : « ${quoi} » rendu`).toBeVisible(V)
          if (actif) await expect(g, `${passe}${nomRole} : « ${quoi} » actif`).toBeEnabled()
          else await expect(g, `${passe}${nomRole} : « ${quoi} » inerte`).toBeDisabled()
        }
        if (actif) {
          // « Fusionner » : derrière « Examiner », présent et actif pour le Commercial (jamais cliqué).
          await bouton(rail, 'Examiner').click()
          const dlg = s.p.getByRole('dialog').filter({ hasText: 'Doublons probables' })
          await expect(bouton(dlg, 'Fusionner ici').first(), `${passe}${nomRole} : « Fusionner ici » actif`).toBeEnabled(V)
          await s.p.keyboard.press('Escape')
        }
      }
      expect(await py(`from apps.crm.models import Lead, Client
l = Lead.objects.get(pk=${x.lead})
sortie([l.type_installation or '', bool(Lead.objects.filter(pk=${x.dup}).exists()), Client.objects.get(pk=${x.client}).nom])`),
      `${nomRole} relu : segment, doublon et client inchangés`).toEqual([x.type, true, `Autre ADRG137 ${m}`])
    }
  } finally {
    for (const x of crees) {
      await py(`from apps.crm.models import Lead, Client
for pk in [${x.lead}, ${x.dup}]:
    try: Lead.all_objects.filter(pk=pk).delete() if hasattr(Lead, 'all_objects') else Lead.objects.filter(pk=pk).delete()
    except Exception as exc: print('nettoyage', pk, exc)
try: Client.objects.filter(pk=${x.client}).delete()
except Exception as exc: print('client', exc)
sortie(1)`).catch(() => null)
    }
  }
})
