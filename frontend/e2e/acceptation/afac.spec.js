// AFAC99 — spec d'acceptation en direct du parcours J5 (groupe AFAC) : facture → encaissement →
// lien de paiement → avoir/retour → relance → relevé client → export, jouée par l'ORCHESTRATEUR
// sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`). EMAIL_BACKEND console :
// aucun envoi réel (les relances sont CONSIGNÉES, `envoyer_email` décoché).
//
// Étapes = identifiants stables de l'audit facturation (docs/audits/2026-10-08-facturation.md) :
// P1.3 émission (acompte + facture depuis BC), P2.1 paiement manuel, P2.3 import de relevé,
// P2.6 encaissement groupé + reliquat, P3.1 lien « Payer en ligne », P4.1 avoir partiel,
// P4.4 retour client remisé, P4.2 note de débit (D-AFAC-C4 = D-AFAC-84), P1.4 annulation d'une
// facture encaissée (D-AFAC-C5 = D-AFAC-80), P5.1 relance manuelle sur facture soldée dans un
// autre onglet, P5.3 promesse partielle (D-AFAC-C10 = D-AFAC-87), P6.1 relevé client (PDF +
// portail, identité AFAC97), P6.2 export comptable + journal des ventes.
//
// Données : chaque étape crée SES devis/factures par l'API réelle ; produits avec un
// `prix_achat` repère (4 321,09) pour l'oracle 7 (jamais visible côté client).
//
// LIMITES CONSTATÉES (dites, jamais contournées) :
// - P3.1 : en local, le `pay_url` est construit sur l'hôte de la requête ; le proxy
//   `vite preview` (changeOrigin) le réécrit en 127.0.0.1:8010 (l'API, qui ne sert pas la page
//   /payer/). L'URL copiée est vérifiée ABSOLUE et de chemin /payer/<jeton>, puis ce chemin est
//   ouvert sur l'origine du front (en production nginx sert les deux sur le même hôte) ;
// - P5.3 : la bascule « tenue » d'une promesse partielle honorée (D-AFAC-C10) n'est écrite que
//   par le beat `scheduled._check_promesses_expirees` APRÈS la date promise : non jouable en
//   direct ; l'étape vérifie la saisie à l'écran, la persistance et l'absence de rupture ;
// - `audit_coherence` (oracle 10) est une commande de l'orchestrateur : NA ici.
import { expect } from '@playwright/test'
import { unzipSync, strFromU8 } from 'fflate'
import { groupe } from './_oracles.js'
import { uniq, lireJson, textePdf, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('AFAC', ['AFAC99'])
const API = '/api/django'
const T = { timeout: 120_000 }
const f2 = (v) => Number(v).toFixed(2)
const cents = (v) => Math.round(Number(v) * 100)
const plat = (s) => String(s).replace(/\s+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const contientMontant = (texte, v) => plat(texte).includes(f2(v))
const SERIE = /^FAC-\d{6}-\d{4}$/
const PRIX_ACHAT = '4321.09'
const AUJOURDHUI = () => new Date().toISOString().slice(0, 10)

// Panier « non rond » : remise 5 %, panneaux à 10 %, arrondi commercial 79,24 → TTC 31 900,00.
const LIGNES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12345.67', tva: '20.00', marque: 'Deye' },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1234.57', tva: '10.00', marque: 'Canadian Solar' },
  { d: 'Structures acier', q: '8', pu: '416.67', tva: '20.00' },
  { d: 'Installation', q: '1', pu: '3333.33', tva: '20.00' },
]

/** Devis démo accepté (lead + produits + POST ventes/devis/atomic/ + share-link + accepter). */
async function creerDevis(request, { client = null } = {}) {
  let leadId = null
  if (!client) {
    leadId = (await lireJson(await request.post(`${API}/crm/leads/`, {
      ...T, data: { nom: uniq('AFAC99 Client'), ville: 'Casablanca', telephone: telephoneMobileUnique() },
    }), 'lead')).id
  }
  const lignes = []
  for (const [i, l] of LIGNES.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, {
      ...T, data: { nom: `${l.d} ${Date.now()}-${i}`, prix_vente: l.pu, prix_achat: PRIX_ACHAT, ...(l.marque ? { marque: l.marque } : {}) },
    }), `produit ${l.d}`)
    lignes.push({ produit: p.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00', taux_tva: l.tva, type_ligne: 'produit', ordre: i })
  }
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '5', lignes, ...(leadId ? { lead: leadId } : { client }) },
  }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client AFAC99' } }), 'acceptation')
  const relu = await lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
  return { id: devis.id, leadId, client: relu.client, reference: relu.reference, ttc: relu.total_ttc }
}

const lireFacture = async (request, id) => lireJson(await request.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)

/** Facture ÉMISE depuis le BC d'un devis (convertir-bc → confirmer → creer-facture → emettre). */
async function factureDepuisBc(request, d) {
  const bc = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await request.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
  const brouillon = await lireJson(await request.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  await lireJson(await request.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
  return { bc, brouillon, facture: await lireFacture(request, brouillon.id) }
}

/** Facture complète émise du devis (POST devis/<id>/facturer-complet/, brouillon d'acompte remplacé). */
async function factureComplete(request, d) {
  const r = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  return lireFacture(request, r.facture_id)
}

async function payerApi(request, id, montant, reference, mode = 'virement') {
  return lireJson(await request.post(`${API}/ventes/factures/${id}/enregistrer-paiement/`, {
    ...T, data: { montant: f2(montant), date_paiement: AUJOURDHUI(), mode, reference },
  }), `paiement ${reference}`)
}

/** Octets + texte d'un PDF servi. */
async function pdf(request, chemin) {
  const rep = await request.get(`${API}/${chemin}`, T)
  expect(rep.status(), `${chemin} → ${(await rep.text().catch(() => '')).slice(0, 300)}`).toBe(200)
  expect(rep.headers()['content-type'] || '').toContain('application/pdf')
  return textePdf(await rep.body())
}

/** Ligne de la facture dans /ventes/factures (recherche « Référence, client… », `#facture-row-<id>`). */
async function ligneFacture(page, f) {
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(f.reference)
  // `.first()` pour AGIR sur la ligne ; l'unicité de la ligne est un ORACLE, vérifié en fin
  // d'étape par `ecranEgalApi` (une facture listée deux fois = défaut, jamais masqué).
  const ligne = page.locator(`#facture-row-${f.id}`).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  return ligne
}

/** L'écran (ligne de liste) porte le TTC, le payé et le dû de l'API (rechargement + relecture),
 *  et la facture n'y figure qu'UNE fois. */
async function ecranEgalApi(page, request, id) {
  const f = await lireFacture(request, id)
  const ligne = await ligneFacture(page, f)
  const texte = plat(await ligne.innerText())
  for (const [nom, v] of [['TTC', f.total_ttc], ['payé', f.montant_paye], ['dû', f.montant_du]]) {
    expect(texte.includes(f2(v)) || texte.includes(String(Math.round(Number(v)))), `écran ${nom} ${v} dans la ligne ${f.reference}`).toBeTruthy()
  }
  expect(await page.locator(`#facture-row-${f.id}`).count(), `/ventes/factures : ${f.reference} listée une seule fois`).toBe(1)
  return { f, ligne }
}

/** « Encaisser » de la ligne → PaiementDialog (#pay-montant, #pay-ref, « Enregistrer »). */
async function encaisserEcran(page, f, montant, reference) {
  const ligne = await ligneFacture(page, f)
  await ligne.getByRole('button', { name: /Encaisser/ }).first().click()
  const dialogue = page.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${f.reference}` })
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  await dialogue.locator('#pay-montant').fill(f2(montant))
  await dialogue.locator('#pay-ref').fill(reference)
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/enregistrer-paiement\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 }),
    dialogue.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(201)
  return rep.json()
}

const sansPrixAchat = (texte, quoi) => {
  expect(plat(texte), `${quoi} : prix_achat jamais visible`).not.toContain(PRIX_ACHAT)
  expect(String(texte)).not.toMatch(/prix_achat|prix d'achat/i)
}

// ── (1) P1.3 — acompte puis facture depuis BC, émises au numéro de série ; PDF = écran ──────
etape('P1.3', ['AFAC99'], async ({ page, suivi, testInfo }) => {
  testInfo.setTimeout(420_000)
  // (a) acompte par le panneau de vente du lead (PanneauVente.jsx → FacturerVenteDialog).
  const da = await creerDevis(page.request)
  await page.goto(`/crm/leads/${da.leadId}`)
  await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  await page.getByRole('region', { name: `Vente du devis ${da.reference}` }).getByRole('button', { name: "Facturer l'acompte" }).click()
  const dialogue = page.getByRole('dialog').filter({ has: page.getByTestId('facturer-vente-form') })
  await expect(dialogue).toBeVisible({ timeout: 60_000 })
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/devis/${da.id}/facturer/$`).test(new URL(x.url()).pathname), { timeout: 120_000 }),
    dialogue.getByRole('button', { name: 'Créer la facture' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBeLessThan(300)
  let acompte = await lireFacture(page.request, (await rep.json()).facture.id)
  if (acompte.statut === 'brouillon') {
    await lireJson(await page.request.post(`${API}/ventes/factures/${acompte.id}/emettre/`, { ...T, data: {} }), 'émission acompte')
    acompte = await lireFacture(page.request, acompte.id)
  }
  expect(acompte.reference, 'acompte émis = numéro de série').toMatch(SERIE)
  // (b) facture depuis BC (autre vente : une vente n'a qu'UNE porte de facturation, ATOT2).
  const db = await creerDevis(page.request)
  const { brouillon, facture } = await factureDepuisBc(page.request, db)
  expect(brouillon.reference, 'brouillon hors série').not.toMatch(SERIE)
  expect(facture.statut).toBe('emise')
  expect(facture.reference, 'facture émise = numéro de série').toMatch(SERIE)
  expect(f2(facture.total_ttc), 'TTC facture du BC = devis').toBe(f2(db.ttc))
  // PDF = écran (API + ligne de liste) au centime ; jamais prix_achat.
  for (const f of [acompte, facture]) {
    const texte = await pdf(page.request, `ventes/factures/${f.id}/telecharger-pdf/`)
    expect(plat(texte)).toContain(f.reference)
    expect(contientMontant(texte, f.total_ttc), `PDF ${f.reference} TTC ${f.total_ttc}`).toBeTruthy()
    expect(contientMontant(texte, f.total_ht), `PDF ${f.reference} HT ${f.total_ht}`).toBeTruthy()
    sansPrixAchat(texte, `PDF ${f.reference}`)
    await ecranEgalApi(page, page.request, f.id)
  }
  suivi.verifie(5)
  suivi.verifie(7)
})

// ── (2a) P2.1 — encaissement partiel à l'écran (/ventes/factures) ──────────────────────────
etape('P2.1', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  await encaisserEcran(page, facture, 5000, uniq('VIR-P21'))
  const f = await lireFacture(page.request, facture.id)
  expect(cents(f.montant_paye)).toBe(500000)
  expect(cents(f.montant_du)).toBe(cents(f.total_ttc) - 500000)
  expect(f.paiements.length, 'un seul paiement').toBe(1)
  expect(f.statut).not.toBe('payee')
  await page.reload()
  await ecranEgalApi(page, page.request, f.id)
})

// ── (2b) P2.3 — import d'un relevé CRLF deux fois : aucun paiement en double ────────────────
etape('P2.3', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  const csv = `date,reference,libelle,montant\r\n${AUJOURDHUI()},${facture.reference},VIREMENT ${facture.client_nom},3000.00\r\n`
  const fichier = { name: `releve-${Date.now()}.csv`, mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf8') }
  const importer = async (premiere) => {
    await page.goto('/ventes/paiements/import-releve')
    const dialogue = page.getByRole('dialog').filter({ hasText: 'Importer un relevé bancaire' })
    await expect(dialogue).toBeVisible({ timeout: 60_000 })
    await dialogue.locator('#imp-fichier').setInputFiles(fichier)
    await Promise.all([
      page.waitForResponse((r) => /import-releve\/dry-run\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 }),
      dialogue.getByRole('button', { name: 'Aperçu (sans écrire)' }).click(),
    ])
    if (premiere) {
      const [rep] = await Promise.all([
        page.waitForResponse((r) => /import-releve\/commit\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 }),
        dialogue.getByRole('button', { name: 'Importer', exact: true }).click(),
      ])
      expect(rep.status(), await rep.text()).toBe(201)
      expect((await rep.json()).created).toBe(1)
    } else {
      await expect(dialogue.getByRole('alert').filter({ hasText: 'déjà été importé' })).toBeVisible()
      await expect(dialogue.getByRole('button', { name: 'Importer', exact: true }), 'second import impossible').toBeDisabled()
    }
  }
  await importer(true)
  await importer(false)
  // Le serveur refuse aussi un second commit du même contenu (dédoublonnage AUD121).
  const dry = await page.request.post(`${API}/ventes/paiements/import-releve/dry-run/`, { ...T, multipart: { file: fichier } })
  const apercu = await dry.json()
  expect(apercu.deja_importe).toBe(true)
  const commit = await page.request.post(`${API}/ventes/paiements/import-releve/commit/`, { ...T, data: { token: apercu.token } })
  expect(commit.status(), 'second commit refusé').toBe(409)
  // Persistance : UN paiement de 3 000.
  const f = await lireFacture(page.request, facture.id)
  expect(f.paiements.length, 'aucun paiement en double').toBe(1)
  expect(cents(f.montant_paye)).toBe(300000)
  await ecranEgalApi(page, page.request, f.id)
})

// ── (2c) P2.6 — encaissement groupé avec reliquat : avance non affectée, visible ───────────
etape('P2.6', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  const ref = uniq('VIR-GRP')
  const reliquat = 500
  const rep = await lireJson(await page.request.post(`${API}/ventes/factures/encaissement-groupe/`, {
    ...T, data: { client: facture.client, montant: f2(Number(facture.montant_du) + reliquat), factures: [facture.id], mode: 'virement', date: AUJOURDHUI(), reference: ref },
  }), 'encaissement groupé')
  const avance = rep.find((p) => !p.facture)
  expect(avance, 'reliquat en avance non affectée').toBeTruthy()
  expect(cents(avance.montant_disponible)).toBe(reliquat * 100)
  const f = await lireFacture(page.request, facture.id)
  expect(f.statut).toBe('payee')
  expect(cents(f.montant_du)).toBe(0)
  // Le reliquat est VISIBLE : /ventes/paiements liste la ligne sans facture du client.
  await page.goto('/ventes/paiements')
  const lignes = page.getByRole('row').filter({ hasText: facture.client_nom })
  await expect(lignes.filter({ hasText: /500[,.]00|500\s?MAD|500 DH/ }).first()).toBeVisible({ timeout: 60_000 })
  await ecranEgalApi(page, page.request, f.id)
})

// ── (3) P3.1 — « Payer en ligne » : URL absolue → page client (pas du JSON) ────────────────
etape('P3.1', ['AFAC99'], async ({ page, context, suivi, testInfo }) => {
  testInfo.setTimeout(300_000)
  const origine = new URL(testInfo.project.use.baseURL).origin
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: origine })
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  const ligne = await ligneFacture(page, facture)
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/lien-paiement\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 }),
    ligne.getByRole('button', { name: /Payer en ligne/ }).click(),
  ])
  expect(rep.status(), await rep.text()).toBeLessThan(300)
  const lien = await rep.json()
  const copie = await page.evaluate(() => navigator.clipboard.readText())
  expect(copie, 'le lien copié = pay_url servi').toBe(lien.pay_url)
  expect(copie, 'URL ABSOLUE').toMatch(/^https?:\/\/[^/]+\/payer\/[\w-]+$/)
  const chemin = new URL(copie).pathname
  // Ouverture de la page client (voir LIMITES : chemin servi par l'origine du front).
  const client = suivi.surveiller(await context.newPage())
  const page2 = await client.goto(`${origine}${chemin}`)
  expect(page2.headers()['content-type'] || '', 'une page HTML, pas une API JSON').toContain('text/html')
  await expect(client.getByRole('heading', { name: 'Payer ma facture' })).toBeVisible({ timeout: 60_000 })
  await expect(client.getByText(facture.reference).first()).toBeVisible()
  expect(contientMontant(await client.getByTestId('montant-a-regler').innerText(), lien.montant_a_payer), 'montant à régler = reste dû').toBeTruthy()
  sansPrixAchat(await client.locator('body').innerText(), 'page de paiement')
  // Persistance : rechargée, même montant.
  await client.reload()
  expect(contientMontant(await client.getByTestId('montant-a-regler').innerText(), (await lireFacture(page.request, facture.id)).montant_du)).toBeTruthy()
  suivi.verifie(7)
})

// ── (4a) P4.1 — avoir partiel ───────────────────────────────────────────────────────────────
etape('P4.1', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const f0 = await factureComplete(page.request, await creerDevis(page.request))
  const panneau = f0.lignes.find((l) => /Panneau/.test(l.designation))
  const avoir = await lireJson(await page.request.post(`${API}/ventes/factures/${f0.id}/creer-avoir/`, {
    ...T, data: { motif: 'AFAC99 avoir partiel', type: 'correction', lignes: [{ produit: panneau.produit, designation: panneau.designation, quantite: '1', prix_unitaire: panneau.prix_unitaire, taux_tva: '10.00' }] },
  }), 'avoir partiel')
  expect(f2(avoir.total_ht), 'HT net remisé (5 %)').toBe(f2(Number(panneau.prix_unitaire) * 0.95))
  expect(avoir.tva_par_taux.map((b) => Number(b.taux))).toEqual([10])
  const f = await lireFacture(page.request, f0.id)
  expect(cents(f.avoirs_total)).toBe(cents(avoir.total_ttc))
  expect(cents(f.montant_du)).toBe(cents(f.total_ttc) - cents(avoir.total_ttc))
  const texte = await pdf(page.request, `ventes/avoirs/${avoir.id}/telecharger-pdf/`)
  expect(contientMontant(texte, avoir.total_ttc), 'PDF avoir = écran').toBeTruthy()
  sansPrixAchat(texte, 'PDF avoir')
  await ecranEgalApi(page, page.request, f.id)
})

// ── (4b) P4.4 — retour client sur une facture à remise globale : HT net remisé, taux réel ──
etape('P4.4', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const f0 = await factureComplete(page.request, await creerDevis(page.request))
  expect(Number(f0.remise_globale), 'facture à remise globale').toBe(5)
  const panneau = f0.lignes.find((l) => /Panneau/.test(l.designation))
  const retour = await lireJson(await page.request.post(`${API}/ventes/factures/${f0.id}/retour-client/`, {
    ...T, data: { motif: 'AFAC99 retour 1 panneau', lignes: [{ produit: panneau.produit, quantite: '1' }], restocker: false },
  }), 'retour client')
  expect(retour.type).toBe('retour')
  const netRemise = Number(panneau.prix_unitaire) * 0.95
  // L'avoir de retour d'UN panneau (ligne à 10 %) se ventile à 10 %, au HT net remisé de la
  // ligne (au plus ; le palier d'arrondi de la facture peut s'en retrancher au prorata).
  expect((retour.tva_par_taux || []).map((b) => Number(b.taux)), 'TVA du retour au taux de la ligne (10 %)').toEqual([10])
  expect(cents(retour.total_ht), 'HT du retour ≤ HT net remisé de la ligne').toBeLessThanOrEqual(Math.round(netRemise * 100))
  for (const b of retour.tva_par_taux) {
    expect(Math.abs(cents(b.base_ht) * Number(b.taux) / 100 - cents(b.montant)), 'TVA = base × taux').toBeLessThanOrEqual(1)
  }
  const f = await lireFacture(page.request, f0.id)
  expect(cents(f.montant_du)).toBe(cents(f.total_ttc) - cents(retour.total_ttc))
  await ecranEgalApi(page, page.request, f.id)
})

// ── (4c) P4.2 — note de débit émise puis annulée (D-AFAC-84 : par avoir) ─────────────────
etape('P4.2', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const f0 = await factureComplete(page.request, await creerDevis(page.request))
  const nd = await lireJson(await page.request.post(`${API}/ventes/factures/${f0.id}/creer-note-debit/`, {
    ...T, data: { motif: 'AFAC99 frais de déplacement', montant: '500.00', taux_tva: '20.00' },
  }), 'note de débit')
  expect(nd.reference).toMatch(/^ND-\d{6}-\d{4}$/)
  expect(f2(nd.total_ttc)).toBe('600.00')
  let f = await lireFacture(page.request, f0.id)
  expect(cents(f.montant_du), 'la ND AUGMENTE le dû').toBe(cents(f0.total_ttc) + 60000)
  const annule = await lireJson(await page.request.post(`${API}/ventes/notes-debit/${nd.id}/annuler/`, { ...T, data: {} }), 'annulation ND')
  // D-AFAC-84 (a) : une ND émise s'annule PAR UN AVOIR (jamais effacée en place).
  expect(annule.note_debit.annulee).toBe(true)
  expect(annule.avoir, "avoir d'annulation de la ND").toBeTruthy()
  expect(f2(annule.avoir.total_ttc)).toBe('600.00')
  f = await lireFacture(page.request, f0.id)
  expect(cents(f.montant_du), 'dû revenu au TTC').toBe(cents(f0.total_ttc))
  const nr = await lireJson(await page.request.get(`${API}/ventes/notes-debit/${nd.id}/`, T), 'ND relue')
  expect(nr.annulee).toBe(true)
  await ecranEgalApi(page, page.request, f.id)
})

// ── (4d) P1.4 — annuler une facture encaissée sans directive : refusée (D-AFAC-80) ─────────
etape('P1.4', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const f0 = await factureComplete(page.request, await creerDevis(page.request))
  await payerApi(page.request, f0.id, 2000, uniq('VIR-P14'))
  const rep = await page.request.post(`${API}/ventes/factures/${f0.id}/annuler/`, { ...T, data: {} })
  const corps = await rep.json()
  // D-AFAC-80 (a) : « refus 400 + choix imposé (directive d'acompte) ». Contrat servi
  // (ENF11, refus d'ÉTAT) : 409 `directive_acompte_requise`. Les deux : refus lisible, rien annulé.
  expect([400, 409], `annuler → ${rep.status()} ${JSON.stringify(corps)}`).toContain(rep.status())
  expect(corps.code).toBe('directive_acompte_requise')
  expect(String(corps.detail)).toMatch(/transférer|rembourser/)
  const f = await lireFacture(page.request, f0.id)
  expect(f.statut, 'facture toujours émise').not.toBe('annulee')
  expect(cents(f.montant_paye)).toBe(200000)
  await ecranEgalApi(page, page.request, f.id)
})

// ── (5a) P5.1 — relance manuelle d'une facture soldée dans un autre onglet : erreur affichée ─
etape('P5.1', ['AFAC99'], async ({ page, context, suivi, testInfo }) => {
  testInfo.setTimeout(360_000)
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  await page.goto('/ventes/relances')
  const ligne = page.getByRole('row').filter({ hasText: facture.reference })
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  await ligne.getByRole('button', { name: 'Relancer', exact: true }).click()
  const dialogue = page.getByRole('dialog').filter({ hasText: `Consigner une relance — ${facture.reference}` })
  await expect(dialogue).toBeVisible()
  // Autre onglet : la facture est soldée à l'écran pendant que la modale reste ouverte.
  const onglet = suivi.surveiller(await context.newPage())
  await encaisserEcran(onglet, facture, facture.montant_du, uniq('VIR-SOLDE'))
  expect((await lireFacture(page.request, facture.id)).statut).toBe('payee')
  suivi.attendre(new RegExp(`/ventes/factures/${facture.id}/relancer/`))
  const [rep] = await Promise.all([
    page.waitForResponse((r) => new RegExp(`/ventes/factures/${facture.id}/relancer/$`).test(new URL(r.url()).pathname), { timeout: 120_000 }),
    dialogue.getByRole('button', { name: 'Consigner' }).click(),
  ])
  expect(rep.status(), 'relance refusée par le serveur').toBeGreaterThanOrEqual(400)
  const motif = (await rep.json()).detail
  // Aucun catch muet : la raison du serveur est affichée dans la modale.
  await expect(dialogue.getByRole('alert')).toContainText(motif)
  // Persistance : aucune relance consignée.
  const relances = await lireJson(await page.request.get(`${API}/ventes/factures/${facture.id}/relances/`, T), 'relances')
  expect((Array.isArray(relances) ? relances : relances.results || []).length).toBe(0)
})

// ── (5b) P5.3 — promesse de paiement partielle saisie à l'écran ───────────────────────────
etape('P5.3', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const d = await creerDevis(page.request)
  const { facture } = await factureDepuisBc(page.request, d)
  await page.goto('/ventes/relances')
  const ligne = page.getByRole('row').filter({ hasText: facture.reference })
  await expect(ligne).toBeVisible({ timeout: 90_000 })
  await ligne.getByRole('button', { name: `Plus d'actions — ${facture.reference}` }).click()
  await page.getByRole('menuitem', { name: 'Promesse de paiement' }).click()
  const dialogue = page.getByRole('dialog').filter({ has: page.locator('#promesse-montant') })
  await dialogue.locator('#promesse-montant').fill('1000')
  const [rep] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && /\/promesses-paiement\/$/.test(new URL(r.url()).pathname), { timeout: 120_000 }),
    dialogue.getByRole('button', { name: 'Enregistrer la promesse' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(201)
  const promesse = await rep.json()
  expect(f2(promesse.montant_promis)).toBe('1000.00')
  // Paiement PARTIEL = le montant promis (solde encore dû).
  await payerApi(page.request, facture.id, 1000, uniq('VIR-PROM'))
  const relue = await lireJson(await page.request.get(`${API}/ventes/promesses-paiement/${promesse.id}/`, T), 'promesse relue')
  expect(relue.statut, 'promesse honorée jamais rompue').not.toBe('rompue')
  const f = await lireFacture(page.request, facture.id)
  expect(cents(f.montant_du)).toBe(cents(f.total_ttc) - 100000)
  // Persistance : la file des relances, rechargée, porte la promesse.
  await page.reload()
  const lu = await lireJson(await page.request.get(`${API}/ventes/relances/`, T), 'relances')
  const rang = lu.find((r) => r.id === facture.id)
  expect(rang?.promesse?.id, 'promesse servie dans la file').toBe(promesse.id)
})

// ── (6) P6.1 — relevé client : identité AFAC97 sur API, PDF et portail ; aucun brouillon ──
etape('P6.1', ['AFAC99'], async ({ page, suivi, testInfo }) => {
  testInfo.setTimeout(420_000)
  const d = await creerDevis(page.request)
  const f0 = await factureComplete(page.request, d)
  await payerApi(page.request, f0.id, 3000, uniq('VIR-REL'))
  const panneau = f0.lignes.find((l) => /Panneau/.test(l.designation))
  await lireJson(await page.request.post(`${API}/ventes/factures/${f0.id}/creer-avoir/`, {
    ...T, data: { motif: 'AFAC99 relevé', type: 'correction', lignes: [{ produit: panneau.produit, designation: panneau.designation, quantite: '1', prix_unitaire: panneau.prix_unitaire, taux_tva: '10.00' }] },
  }), 'avoir')
  await lireJson(await page.request.post(`${API}/ventes/factures/${f0.id}/creer-note-debit/`, {
    ...T, data: { motif: 'AFAC99 relevé ND', montant: '500.00', taux_tva: '20.00' },
  }), 'note de débit')
  // Un 2e devis accepté du MÊME client laisse un BROUILLON d'acompte : jamais compté.
  const d2 = await creerDevis(page.request, { client: d.client })
  const brouillons = (await lireJson(await page.request.get(`${API}/ventes/devis/${d2.id}/`, T), 'devis 2')).factures_liees.filter((x) => x.statut === 'brouillon')
  expect(brouillons.length, 'un brouillon existe pour le client').toBeGreaterThan(0)
  const rel = await lireJson(await page.request.get(`${API}/ventes/clients/${d.client}/releve/`, T), 'relevé API')
  const t = rel.totaux
  expect(cents(t.facture) + cents(t.notes_debit) - cents(t.paye) - cents(t.retenues) - cents(t.avoirs) - cents(t.abandons), 'identité du relevé').toBe(cents(t.du))
  const f = await lireFacture(page.request, f0.id)
  expect(cents(t.facture), 'Facturé = TTC émis seul (aucun brouillon)').toBe(cents(f.total_ttc))
  expect(cents(t.du), 'Solde dû = dû de la facture').toBe(cents(f.montant_du))
  expect(rel.lignes.map((l) => l.reference)).not.toContain(brouillons[0].reference)
  // PDF du relevé.
  const texte = await pdf(page.request, `ventes/clients/${d.client}/releve-pdf/`)
  for (const [nom, v] of Object.entries(t)) {
    if (cents(v) !== 0) expect(contientMontant(texte, v), `relevé PDF ${nom} ${v}`).toBeTruthy()
  }
  sansPrixAchat(texte, 'relevé PDF')
  // Portail client (compte tokenisé ; lien révélé par l'action tracée lien-acces).
  const compte = await lireJson(await page.request.post(`${API}/portail/comptes-portail/`, { ...T, data: { client: d.client } }), 'compte portail')
  const acces = await lireJson(await page.request.post(`${API}/portail/comptes-portail/${compte.id}/lien-acces/`, { ...T, data: {} }), 'lien-acces')
  const portail = await lireJson(await page.request.get(`${API}/public/portail/${acces.token_acces}/mon-releve/`, T), 'relevé portail')
  const tp = portail.totaux || portail
  for (const k of ['facture', 'notes_debit', 'paye', 'avoirs', 'du']) {
    if (tp[k] !== undefined) expect(f2(tp[k]), `portail ${k} = API`).toBe(f2(t[k]))
  }
  expect(f2(tp.du ?? tp.solde ?? NaN), 'portail : solde dû = API').toBe(f2(t.du))
  sansPrixAchat(JSON.stringify(portail), 'portail')
  await ecranEgalApi(page, page.request, f0.id)
  suivi.verifie(7)
})

// ── (7) P6.2 — export comptable + journal des ventes : la date de fin est incluse ──────────
etape('P6.2', ['AFAC99'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const f = await factureComplete(page.request, await creerDevis(page.request))
  const jour = f.date_emission
  const csv = await page.request.get(`${API}/ventes/export-comptable/?start=${jour}&end=${jour}&fmt=csv`, T)
  expect(csv.status(), (await csv.text()).slice(0, 300)).toBe(200)
  const texteCsv = await csv.text()
  expect(texteCsv, 'export comptable : facture de la date de fin incluse').toContain(f.reference)
  const journal = await page.request.get(`${API}/ventes/journal-ventes/?start=${jour}&end=${jour}`, T)
  expect(journal.status()).toBe(200)
  // Feuille 1 du journal (exports.export_journal_ventes) : UNE ligne par ligne de facture,
  // chaînes inline ; colonnes A = Facture, I = Total HT, K = Montant TVA, L = Total TTC.
  const fichiers = unzipSync(new Uint8Array(await journal.body()))
  const feuille = strFromU8(fichiers['xl/worksheets/sheet1.xml'])
  const rangs = [...feuille.matchAll(/<row[^>]*>(.*?)<\/row>/gs)].map((m) => Object.fromEntries(
    [...m[1].matchAll(/<c r="([A-Z]+)\d+"[^>]*>(?:<f>[^<]*<\/f>)?(?:<v>([^<]*)<\/v>|<is><t[^>]*>([^<]*)<\/t><\/is>)<\/c>/g)]
      .map(([, col, v, t]) => [col, v ?? t])))
  const siennes = rangs.filter((r) => r.A === f.reference)
  expect(siennes.length, 'journal des ventes : facture de la date de fin incluse').toBeGreaterThan(0)
  const somme = (col) => siennes.reduce((s, r) => s + cents(r[col]), 0)
  expect(somme('I'), 'journal : Σ HT des lignes = HT facture').toBe(cents(f.total_ht))
  expect(somme('K'), 'journal : Σ TVA des lignes = TVA facture').toBe(cents(f.total_tva))
  expect(somme('L'), 'journal : Σ TTC des lignes = TTC facture').toBe(cents(f.total_ttc))
  await ecranEgalApi(page, page.request, f.id)
})
