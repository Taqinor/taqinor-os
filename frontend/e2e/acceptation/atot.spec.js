// ATOT17 — spec d'acceptation en direct du parcours d'argent (groupe ATOT), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`) :
// devis → BC → facture(s) → paiement → avoir → révision → PDF et charge utile publique.
//
// Étapes = (1)…(7) de la tâche, numérotées comme les étapes de l'audit totaux
// (docs/audits/2026-10-07-totaux.md : P1.4 réouverture/enregistrement, P3.2 page publique,
// P2.2 portes, P2.3 recopie, P2.5 reste à payer, P2.8 correction après coup, P3.4 PDF).
//
// Données : chaque étape crée SES devis par l'API réelle (lead + produits + POST
// ventes/devis/atomic/), jamais la base à la main. Devis « non rond » : 4 lignes dont les
// panneaux à 10 %, remise 5 % → Sous-total 28 888,92, remise 1 444,45, arrondi commercial
// 79,24 (palier PAS_ARRONDI_DEVIS), Total HT 27 365,23, TTC 31 900,00 (constaté sur la pile).
// Les fiches « ATOT17 … » restent dans la démo locale (factures émises : PROTECT).
//
// LIMITES CONSTATÉES (dites, jamais contournées) :
// - la page publique `/proposition/<token>` vit dans apps/web (Astro), non servie par la
//   pile ERP : l'étape P3.2 vérifie la charge utile que cette page lit
//   (GET ventes/proposal/<token>/, `option_totals`) et le PDF /proposal, pas son rendu ;
// - le bouton « Facturer (facture complète) » a été retiré de l'écran (VNT75) : l'étape
//   P2.2 joue le geste par son endpoint (POST devis/<id>/facturer-complet/).
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { uniq, lireJson, textePdf, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ATOT', ['ATOT17'])
const API = '/api/django'
const T = { timeout: 120_000 }
const f2 = (v) => Number(v).toFixed(2)
const cents = (v) => Math.round(Number(v) * 100)
// Texte comparable : blancs (insécables compris) retirés, virgule décimale → point.
const plat = (s) => String(s).replace(/\s+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const contientMontant = (texte, v) => plat(texte).includes(f2(v))

// Panier « non rond » (prix constatés : TTC 31 900,00 après arrondi de 79,24 HT).
const LIGNES_NON_RONDES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12345.67', tva: '20.00', marque: 'Deye' },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1234.57', tva: '10.00', marque: 'Canadian Solar' },
  { d: 'Structures acier', q: '8', pu: '416.67', tva: '20.00' },
  { d: 'Installation', q: '1', pu: '3333.33', tva: '20.00' },
]
// Panier composable (aucun arrondi) pour la consolidée : remise 10 % → HT 24 750,
// TVA 900 + 3 150, TTC 28 800,00 — l'exemple « deux devis remisés » de ATOT3.
const LIGNES_RONDES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12500.00', tva: '20.00', marque: 'Deye' },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1250.00', tva: '10.00', marque: 'Canadian Solar' },
  { d: 'Installation', q: '1', pu: '5000.00', tva: '20.00' },
]

/** Lead (sauf `client` fourni) + produits + devis (POST ventes/devis/atomic/, views/devis_edition.py),
 *  puis, si demandé, envoi (share-link {envoi:true}, views/devis_envoi.py) et acceptation
 *  (POST devis/<id>/accepter/, views/devis_cycle.py). */
async function creerDevis(request, { lignes = LIGNES_NON_RONDES, remise = '5', client = null, envoyer = true, accepter = true } = {}) {
  let leadId = null
  if (!client) {
    const lead = await lireJson(await request.post(`${API}/crm/leads/`, {
      ...T, data: { nom: uniq('ATOT17 Client'), ville: 'Casablanca', telephone: telephoneMobileUnique() },
    }), 'lead')
    leadId = lead.id
  }
  const corps = []
  for (const [i, l] of lignes.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, {
      ...T, data: { nom: `${l.d} ${Date.now()}-${i}`, prix_vente: l.pu, ...(l.marque ? { marque: l.marque } : {}) },
    }), `produit ${l.d}`)
    corps.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
  }
  const data = { taux_tva: '20.00', remise_globale: remise, lignes: corps, ...(leadId ? { lead: leadId } : { client }) }
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, { ...T, data }), 'devis')
  let token = null
  if (envoyer) {
    token = (await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')).token
  }
  if (envoyer && accepter) {
    await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client ATOT17' } }), 'acceptation')
  }
  const relu = await lireDevis(request, devis.id)
  return { id: devis.id, leadId, client: relu.client, reference: relu.reference, ttc: relu.total_ttc, token }
}

const lireDevis = async (request, id) => lireJson(await request.get(`${API}/ventes/devis/${id}/`, T), `devis ${id}`)
const lireFacture = async (request, id) => lireJson(await request.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)
const lireAvoir = async (request, id) => lireJson(await request.get(`${API}/ventes/avoirs/${id}/`, T), `avoir ${id}`)
const vivantes = (d) => (d.factures_liees || []).filter((f) => f.statut !== 'annulee')

/** PDF servi (GET ou POST), texte extrait par pdfjs (helpers.textePdf). */
async function pdf(request, chemin, methode = 'get') {
  const rep = await request[methode](`${API}/${chemin}`, { ...T, ...(methode === 'post' ? { data: {} } : {}) })
  expect(rep.status(), `${chemin} → ${await rep.text().catch(() => '')}`.slice(0, 400)).toBe(200)
  expect(rep.headers()['content-type'] || '').toContain('application/pdf')
  return textePdf(await rep.body())
}

/** Ligne de la facture dans /ventes/factures (recherche « Référence, client… », `#facture-row-<id>`). */
async function ligneFacture(page, f) {
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(f.reference)
  const ligne = page.locator(`#facture-row-${f.id}`)
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  return ligne
}

/** L'écran (ligne de liste) porte le TTC, le payé et le dû servis par l'API. */
async function ecranEgalApi(page, f) {
  const ligne = await ligneFacture(page, f)
  const texte = await ligne.innerText()
  for (const [nom, v] of [['TTC', f.total_ttc], ['payé', f.montant_paye], ['dû', f.montant_du]]) {
    const brut = plat(texte)
    expect(brut.includes(f2(v)) || brut.includes(String(Math.round(Number(v)))), `écran ${nom} ${v} dans « ${texte} »`).toBeTruthy()
  }
  return ligne
}

/** Chaîne Sous-total − Remise − Arrondi = Total HT ; Total HT + TVA = TTC (au centime). */
function verifierChaine(o) {
  expect(cents(o.ht_brut) - cents(o.remise) - cents(o.arrondi), 'Sous-total − Remise − Arrondi = Total HT').toBe(cents(o.ht_net))
  expect(cents(o.ht_net) + cents(o.tva), 'Total HT + TVA = TTC').toBe(cents(o.ttc))
  expect(o.tva_par_taux.reduce((s, b) => s + cents(b.montant), 0), 'Σ TVA par taux = TVA').toBe(cents(o.tva))
}

// ── (1) P1.4 — rouvrir le devis en édition et l'enregistrer sans rien toucher ─────────────
etape('P1.4', ['ATOT17'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request, { envoyer: false })
  expect(cents(d.ttc), 'TTC non rond avant arrondi : 31 900,00 constaté').toBe(3190000)
  // Écran d'édition (reviserDevis.js : `/ventes/devis/nouveau?edit=<id>`), barre d'actions
  // (BarreActionsDevis.jsx : gen-barre-actions, pastille gen-barre-non-enregistre).
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  const barre = page.getByTestId('gen-barre-actions')
  await expect(barre).toContainText(d.reference, { timeout: 60_000 })
  await expect(page.getByTestId('gen-barre-total')).not.toHaveText(/^\s*0\s*MAD/, { timeout: 60_000 })
  // Données de référence chargées (BandeauxEdition.jsx `refsLoading`) : l'état « modifié »
  // ne se juge qu'écran complet (sinon l'oracle passerait avant que la pastille n'arrive).
  await expect(page.getByText('Chargement des données (leads, clients, produits)')).toHaveCount(0, { timeout: 180_000 })
  await expect(page.getByTestId('gen-barre-non-enregistre'), "aucun « Modifications non enregistrées » à l'ouverture").toHaveCount(0)
  await expect(page.getByTestId('draft-restore-banner')).toHaveCount(0)
  const [rep] = await Promise.all([
    page.waitForResponse((r) => ['PUT', 'PATCH', 'POST'].includes(r.request().method())
      && new RegExp(`/ventes/devis/(${d.id}/|atomic/)`).test(new URL(r.url()).pathname), { timeout: 120_000 }),
    barre.getByRole('button', { name: /Enregistrer/ }).click(),
  ])
  expect(rep.status(), `enregistrement → ${await rep.text().catch(() => '')}`.slice(0, 400)).toBeLessThan(300)
  await expect(page.getByTestId('gen-barre-non-enregistre'), 'aucune pastille après un enregistrement réussi').toHaveCount(0, { timeout: 30_000 })
  // Persistance : le serveur garde le TTC au centime, la réouverture ne marque rien de modifié.
  expect(f2((await lireDevis(page.request, d.id)).total_ttc), 'total_ttc serveur identique').toBe(f2(d.ttc))
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.getByTestId('gen-barre-actions')).toContainText(d.reference, { timeout: 60_000 })
  await expect(page.getByText('Chargement des données (leads, clients, produits)')).toHaveCount(0, { timeout: 180_000 })
  await expect(page.getByTestId('gen-barre-non-enregistre')).toHaveCount(0)
  await expect(page.getByTestId('draft-restore-banner')).toHaveCount(0)
  expect(plat(await page.getByTestId('gen-barre-total').innerText())).toContain(plat('31 900'))
})

// ── (2) P3.2 — envoyer ; chaîne de prix de la charge utile publique = PDF /proposal ──────
etape('P3.2', ['ATOT17'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request, { accepter: false })
  expect((await lireDevis(page.request, d.id)).statut).toBe('envoye')
  // La charge utile que lit la page /proposition/<token> (apps/web lib/proposition.ts
  // proposalEndpoint → GET ventes/proposal/<token>/, public_views.proposal_data).
  const pub = await lireJson(await page.request.get(`${API}/ventes/proposal/${d.token}/`, T), 'proposition publique')
  const o = pub.option_totals.sans_batterie
  expect(cents(o.arrondi), 'devis non rond : arrondi > 0').toBeGreaterThan(0)
  verifierChaine(o)
  expect(f2(o.ttc), 'TTC public = devis').toBe(f2(d.ttc))
  // PDF client /proposal (règle #4) : mêmes montants au centime.
  const texte = await pdf(page.request, `ventes/devis/${d.id}/proposal/`)
  for (const [nom, v] of [['Sous-total HT', o.ht_brut], ['Remise', o.remise], ['Arrondi', o.arrondi], ['Total HT', o.ht_net], ['TTC', o.ttc]]) {
    expect(contientMontant(texte, v), `PDF /proposal porte ${nom} ${f2(v)}`).toBeTruthy()
  }
  expect(plat(texte)).toContain(plat(`Sous-total HT ${f2(o.ht_brut)}`))
  expect(plat(texte)).toContain(plat(`Total HT ${f2(o.ht_net)}`))
  for (const b of o.tva_par_taux) expect(contientMontant(texte, b.montant), `PDF TVA ${b.taux} %`).toBeTruthy()
  // Persistance : relire la charge utile → mêmes chiffres.
  const relu = (await lireJson(await page.request.get(`${API}/ventes/proposal/${d.token}/`, T), 'relue')).option_totals.sans_batterie
  expect(relu).toEqual(o)
  await page.goto(`/crm/leads/${d.leadId}`)
  await expect(page.getByTestId('lw-context-rail')).toBeVisible({ timeout: 60_000 })
})

// ── (3) P2.2 — accepter, facturer l'acompte à l'écran, puis tenter la facture complète ───
etape('P2.2', ['ATOT17'], async ({ page, suivi, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  // Panneau de vente du lead (PanneauVente.jsx) → « Facturer l'acompte » → dialogue VNT45.
  await page.goto(`/crm/leads/${d.leadId}`)
  await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  await page.getByRole('region', { name: `Vente du devis ${d.reference}` }).getByRole('button', { name: "Facturer l'acompte" }).click()
  const dialogue = page.getByRole('dialog').filter({ has: page.getByTestId('facturer-vente-form') })
  await expect(dialogue).toBeVisible({ timeout: 60_000 })
  const cible = new RegExp(`/ventes/devis/${d.id}/facturer/$`)
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname), { timeout: 120_000 }),
    dialogue.getByRole('button', { name: 'Créer la facture' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBeLessThan(300)
  const acompte = (await rep.json()).facture
  // Le second geste : facture complète sur une vente déjà facturée → refus lisible nommant la facture.
  suivi.attendre(new RegExp(`/ventes/devis/${d.id}/facturer-complet/`), 409)
  const refus = await page.request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: {} })
  const corps = await refus.json()
  // Plan : « 400 lisible ». Contrat actuel (VNT, `_facturer_complete`) : 409 `deja_facture`.
  // Les deux sont des refus lisibles ; jamais 201 ni 500.
  expect([400, 409], `facturer-complet → ${refus.status()} ${JSON.stringify(corps)}`).toContain(refus.status())
  expect(String(corps.detail)).toContain(acompte.reference)
  expect(String(corps.detail)).toMatch(/déjà facturée?/)
  // Persistance : une seule facture vivante sur le devis.
  const relu = await lireDevis(page.request, d.id)
  expect(vivantes(relu).map((f) => f.reference), 'une seule facture').toEqual([acompte.reference])
  await ligneFacture(page, acompte)
  suivi.verifie(5)
})

// ── (4) P2.3 — BC facturé = devis ; consolidée = Σ devis ──────────────────────────────────
etape('P2.3', ['ATOT17'], async ({ page, suivi, testInfo }) => {
  testInfo.setTimeout(420_000)
  // (a) 2e devis → BC (convertir-bc, confirmer, creer-facture : views/bon_commande.py).
  const d2 = await creerDevis(page.request)
  const bc = await lireJson(await page.request.post(`${API}/ventes/devis/${d2.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  expect(f2(bc.total_ttc), 'TTC BC = devis').toBe(f2(d2.ttc))
  await lireJson(await page.request.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
  const fbc = await lireJson(await page.request.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  expect(f2(fbc.total_ttc), 'TTC facture du BC = devis').toBe(f2(d2.ttc))
  // (b) consolidée de deux devis composables du MÊME client (POST factures/consolider/).
  const d3 = await creerDevis(page.request, { lignes: LIGNES_RONDES, remise: '10' })
  const d4 = await creerDevis(page.request, { lignes: LIGNES_RONDES, remise: '10', client: d3.client })
  const cons = await lireJson(await page.request.post(`${API}/ventes/factures/consolider/`, { ...T, data: { devis_ids: [d3.id, d4.id] } }), 'consolidée')
  expect(cents(cons.total_ttc), 'TTC consolidée = Σ devis').toBe(cents(d3.ttc) + cents(d4.ttc))
  // (c) deux devis à arrondi non composable : refus lisible nommant les devis, jamais un total faux.
  const d5 = await creerDevis(page.request)
  const d6 = await creerDevis(page.request, { client: d5.client })
  suivi.attendre(/\/ventes\/factures\/consolider\//, 409)
  const refus = await page.request.post(`${API}/ventes/factures/consolider/`, { ...T, data: { devis_ids: [d5.id, d6.id] } })
  expect([400, 409, 201], `consolider non composable → ${refus.status()}`).toContain(refus.status())
  if (refus.status() === 201) {
    expect(cents((await refus.json()).total_ttc), 'si elle est créée, TTC = Σ devis').toBe(cents(d5.ttc) + cents(d6.ttc))
  } else {
    const msg = JSON.stringify(await refus.json())
    expect(msg).toContain(d5.reference)
    expect(msg).toContain(d6.reference)
  }
  // Persistance : rouvrir chaque facture → mêmes TTC ; écran = API.
  for (const [f, attendu] of [[fbc, cents(d2.ttc)], [cons, cents(d3.ttc) + cents(d4.ttc)]]) {
    const relue = await lireFacture(page.request, f.id)
    expect(cents(relue.total_ttc)).toBe(attendu)
    await ecranEgalApi(page, relue)
  }
  suivi.verifie(5)
})

// ── (5) P2.5 — encaisser, rejeter un chèque, créer un avoir puis l'annuler ───────────────
etape('P2.5', ['ATOT17'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const fc = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  const id = fc.facture_id
  const ttc = cents(fc.total_ttc)
  expect(ttc).toBe(cents(d.ttc))
  const payer = async (montant, mode, reference) => lireJson(await page.request.post(`${API}/ventes/factures/${id}/enregistrer-paiement/`, {
    ...T, data: { montant, date_paiement: '2026-10-20', mode, reference },
  }), `paiement ${reference}`)
  await payer('10000.00', 'virement', 'VIR-ATOT17')
  await payer('5000.00', 'cheque', 'CHQ-ATOT17')
  let f = await lireFacture(page.request, id)
  expect(cents(f.montant_paye)).toBe(1500000)
  expect(cents(f.montant_du)).toBe(ttc - 1500000)
  await ecranEgalApi(page, f)
  // Rejet du chèque (POST paiements/<id>/rejeter/) : le dû remonte, statut non payé.
  const cheque = f.paiements.find((p) => p.reference === 'CHQ-ATOT17')
  const rejete = await lireJson(await page.request.post(`${API}/ventes/paiements/${cheque.id}/rejeter/`, { ...T, data: { motif: 'Chèque impayé' } }), 'rejet')
  expect(rejete.statut).toBe('rejete')
  f = await lireFacture(page.request, id)
  expect(cents(f.montant_paye), 'payé après rejet').toBe(1000000)
  expect(cents(f.montant_du), 'dû après rejet').toBe(ttc - 1000000)
  expect(f.statut).not.toBe('payee')
  await ecranEgalApi(page, f)
  // Avoir partiel (1 panneau, au HT net remisé) puis annulation.
  const panneau = f.lignes.find((l) => /Panneau/.test(l.designation))
  const avoir = await lireJson(await page.request.post(`${API}/ventes/factures/${id}/creer-avoir/`, {
    ...T, data: { motif: 'ATOT17 correction', type: 'correction', lignes: [{ produit: panneau.produit, designation: panneau.designation, quantite: '1', prix_unitaire: panneau.prix_unitaire, taux_tva: '10.00' }] },
  }), 'avoir')
  expect(f2(avoir.total_ht), 'avoir au HT net remisé (5 %)').toBe(f2(Number(panneau.prix_unitaire) * 0.95))
  f = await lireFacture(page.request, id)
  expect(cents(f.avoirs_total)).toBe(cents(avoir.total_ttc))
  expect(cents(f.montant_du), 'dû = TTC − payé − avoirs').toBe(ttc - 1000000 - cents(avoir.total_ttc))
  await ecranEgalApi(page, f)
  const annule = await lireJson(await page.request.post(`${API}/ventes/avoirs/${avoir.id}/annuler/`, { ...T, data: {} }), 'annulation avoir')
  expect(annule.statut).toBe('annulee')
  // Persistance : facture, avoir et solde du devis relus.
  f = await lireFacture(page.request, id)
  expect(cents(f.avoirs_total)).toBe(0)
  expect(cents(f.montant_du)).toBe(ttc - 1000000)
  expect((await lireAvoir(page.request, avoir.id)).statut).toBe('annulee')
  const solde = (await lireDevis(page.request, d.id)).solde
  expect(cents(solde.restant), '« Restant » du devis = dû de la facture').toBe(cents(f.montant_du))
  expect(cents(solde.paye)).toBe(1000000)
  await ecranEgalApi(page, f)
})

// ── (6) P2.8 — réviser à la baisse un devis facturé (Prix négocié → V2 + avoir) ──────────
etape('P2.8', ['ATOT17'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const fc = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  const f1 = await lireFacture(page.request, fc.facture_id)
  const v1 = await lireDevis(page.request, d.id)
  const rep = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/prix-negocie/`, {
    ...T, data: { mode: 'appliquer', remise_pct: '10', confirmer_avoir: true },
  }), 'prix négocié')
  const v2 = await lireDevis(page.request, rep.devis_v2.id)
  expect(v2.statut).toBe('accepte')
  expect(cents(v2.total_ttc)).toBeLessThan(cents(v1.total_ttc))
  const f = await lireFacture(page.request, f1.id)
  const avoirs = (f.avoirs || []).filter((a) => a.statut !== 'annulee')
  expect(avoirs.length, "un avoir d'écart").toBe(1)
  const avoir = await lireAvoir(page.request, avoirs[0].id)
  // L'avoir porte l'écart RÉEL : TTC, HT et TVA = V1 − V2 au centime (jamais un taux mélangé).
  expect(cents(avoir.total_ttc), 'TTC avoir = écart TTC').toBe(cents(v1.total_ttc) - cents(v2.total_ttc))
  expect(cents(avoir.total_ht), 'HT avoir = écart HT').toBe(cents(v1.total_ht) - cents(v2.total_ht))
  expect(cents(avoir.total_tva), 'TVA avoir = écart de TVA').toBe(cents(v1.total_tva) - cents(v2.total_tva))
  const taux = (avoir.tva_par_taux || []).map((b) => Number(b.taux)).sort((a, b) => a - b)
  expect(taux, 'ventilé aux deux taux réels').toEqual([10, 20])
  for (const b of avoir.tva_par_taux) {
    expect(Math.abs(cents(b.base_ht) * Number(b.taux) / 100 - cents(b.montant)), `TVA ${b.taux} % = base × taux`).toBeLessThanOrEqual(1)
  }
  expect(cents(f.montant_du), 'dû = TTC − avoir').toBe(cents(f.total_ttc) - cents(avoir.total_ttc))
  // Persistance : la V2 relue porte le même solde.
  expect(cents((await lireDevis(page.request, v2.id)).solde.restant)).toBe(cents(f.montant_du))
  await ecranEgalApi(page, f)
})

// ── (7) P3.4 — PDF facture, avoir et pro-forma = écran au centime ─────────────────────────
etape('P3.4', ['ATOT17'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  // Pro-forma du devis accepté (POST devis/<id>/proforma-pdf/) : TTC = devis.
  const proforma = await pdf(page.request, `ventes/devis/${d.id}/proforma-pdf/`, 'post')
  expect(contientMontant(proforma, d.ttc), `pro-forma TTC ${d.ttc}`).toBeTruthy()
  expect(plat(proforma)).toContain(plat('Total HT'))
  const fc = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  const f = await lireFacture(page.request, fc.facture_id)
  const tf = await pdf(page.request, `ventes/factures/${f.id}/telecharger-pdf/`)
  expect(plat(tf), 'chaîne facture avec Total HT').toContain(plat(`Total HT ${f2(f.total_ht)}`))
  expect(contientMontant(tf, f.total_ttc)).toBeTruthy()
  expect(plat(tf)).toMatch(/Arrondicommercial/)
  for (const b of f.tva_par_taux) expect(contientMontant(tf, b.montant), `facture TVA ${b.taux} %`).toBeTruthy()
  // Avoir partiel d'une facture remisée : sa chaîne imprime le Total HT net.
  const panneau = f.lignes.find((l) => /Panneau/.test(l.designation))
  const avoir = await lireJson(await page.request.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, {
    ...T, data: { motif: 'ATOT17 PDF', type: 'correction', lignes: [{ produit: panneau.produit, designation: panneau.designation, quantite: '1', prix_unitaire: panneau.prix_unitaire, taux_tva: '10.00' }] },
  }), 'avoir')
  const ta = await pdf(page.request, `ventes/avoirs/${avoir.id}/telecharger-pdf/`)
  expect(plat(ta), 'chaîne avoir avec Total HT').toContain(plat(`Total HT ${f2(avoir.total_ht)}`))
  expect(contientMontant(ta, avoir.total_ttc)).toBeTruthy()
  for (const b of avoir.tva_par_taux) expect(contientMontant(ta, b.montant), `avoir TVA ${b.taux} %`).toBeTruthy()
  // Écran (liste des factures) = API = PDF.
  await ecranEgalApi(page, await lireFacture(page.request, f.id))
})
