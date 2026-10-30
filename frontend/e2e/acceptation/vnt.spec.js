// VNT48 — spec d'acceptation en direct du lot M1 « Tijani » (groupe VNT), jouée par
// l'ORCHESTRATEUR sur la pile locale (`scripts/acceptation.ps1 VNT`, société démo,
// connexion demo_admin par auth.setup.js). Format : `_format.md`.
//
// Réplique du dossier Kharbachi (lead 1594) créée par l'API (lead + devis à 11
// lignes, remise 10 %, TTC 49 000,00, envoyé puis accepté), puis les gestes
// d'écran du lot : Facturer l'acompte (dialogue FacturerVenteDialog), PDF réel,
// téléphone 375 px, Annuler (avoir automatique), refacturer en brouillon,
// supprimer le brouillon, erreur sous le champ.
//
// NON COUVERT ICI : VNT47 (commande `reparer_vente_active`, lancée à la main par
// l'orchestrateur et enregistrée à part), VNT24 / VNT32 / VNT43 (aucune étape ne
// les prouve). Chaque sélecteur / endpoint est cité ci-dessous (fichier:ligne) ;
// ce qui n'a pas pu être confirmé dans le code est marqué `// À CONFIRMER`.
//
// Nettoyage : un devis ACCEPTÉ qui porte des factures émises ne se supprime pas
// (PROTECT) — le nettoyage est donc best-effort (DELETE devis puis lead, erreurs
// ignorées) ; les fiches « VNT Kharbachi … » restent dans la démo locale.
import { expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { uniq, lireJson, listeDe, textePdf, telephoneMobileUnique, STAGE_LABELS } from '../helpers.js'

const plage = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => `VNT${a + i}`)
const etape = groupe('VNT', [
  ...plage(10, 23), ...plage(25, 31), ...plage(33, 42), 'VNT44', 'VNT45', 'VNT46',
  'VNT58', 'VNT59', 'VNT60', 'VNT61', 'VNT62', 'VNT64', 'VNT73', 'VNT74', 'VNT75', 'VNT78',
  'VNT53', 'VNT54', 'VNT55', 'VNT67', 'VNT77', 'VNT84', 'VNT85', 'VNT86', 'VNT88', 'VNT89', 'VNT91', 'VNT92', 'VNT93',
  'VNT97', 'VNT98', 'VNT100', 'VNT102', 'VNT103', 'VNT104', 'VNT105', 'VNT106',
])

const API = '/api/django'
const DATE_PAIEMENT = '2026-10-12'
const f2 = (v) => Number(v).toFixed(2)
const norm = (s) => String(s).replace(/\s+/g, ' ')

// ── Réplique du devis 388 (panier : facturation/contract_samples/facture_situation_vente.json,
// les 11 lignes de l'option acceptée ; Σ HT 46 243,50 ; panneaux à 10 %, le reste à 20 %). ──
const LIGNES = [
  { d: 'Onduleur hybride Deye 5kW Monophasé', q: '1', pu: '12500.00', tva: '20.00', marque: 'Deye', gar: 120 },
  { d: 'Panneau Canadian Solar 710W', q: '8', pu: '1200.00', tva: '10.00', marque: 'Canadian Solar', gar: 144, garProd: 360 },
  { d: 'Batterie Dyness 5 kWh', q: '1', pu: '11666.67', tva: '20.00', marque: 'Dyness', gar: 120 },
  { d: 'Structures acier', q: '8', pu: '416.67', tva: '20.00' },
  { d: 'Socles', q: '16', pu: '67.00', tva: '20.00' },
  { d: 'Câble solaire Nexans 6mm² (au mètre)', q: '60', pu: '10.83', tva: '20.00', marque: 'Nexans' },
  { d: 'Câble de terre Nexans 6 mm² (au mètre)', q: '40', pu: '12.00', tva: '20.00', marque: 'Nexans' },
  { d: 'Accessoires', q: '1', pu: '416.67', tva: '20.00' },
  { d: 'Tableau De Protection AC/DC', q: '1', pu: '1625.00', tva: '20.00' },
  { d: 'Installation', q: '1', pu: '4000.00', tva: '20.00' },
  { d: 'Transport', q: '1', pu: '900.00', tva: '20.00' },
]
// Échéancier de départ 30/60/10 (nature acompte / intermediaire / solde : ventes/serializers.py:266-280,
// forme [{libelle, type, pct_or_montant}] de devis_replace_lines_entete.json). Le geste « acompte libre »
// le réécrit en [15 000 MAD, 60 %, reste] (D-VNT-3 / arbitrage 9).
const ECHEANCIER = [
  { libelle: 'Acompte', type: 'acompte', pct_or_montant: 30 },
  { libelle: 'Livraison du matériel', type: 'intermediaire', pct_or_montant: 60 },
  { libelle: 'Solde', type: 'solde', pct_or_montant: 10 },
]

// Échéancier à DEUX tranches (acompte 30 % / solde 70 %) : après un acompte libre, la tranche suivante est
// le SOLDE (reste à facturer) — le parcours « Facturer le solde » de VNT83.
const ECHEANCIER_2 = [
  { libelle: 'Acompte', type: 'acompte', pct_or_montant: 30 },
  { libelle: 'Solde', type: 'solde', pct_or_montant: 70 },
]

/** Lead + devis (11 lignes) créés par l'API, envoyé puis accepté.
 *  - POST crm/leads/ : patron de suivi-commercial.spec.js:73 ;
 *  - POST stock/produits/ : patron de comptes-justes.spec.js:46 (+ marque, garantie_mois, garantie_production_mois
 *    de stock/serializers.py:742,789) ;
 *  - POST ventes/devis/atomic/ : views/devis_edition.py:206 (corps = en-tête + `lignes`, lead OU client) ;
 *  - POST ventes/devis/<id>/share-link/ {envoi:true} : views/devis_envoi.py:101 (brouillon → envoyé via
 *    mark_devis_sent, sans e-mail) ; statut en lecture seule (serializers.py:1129) ;
 *  - POST ventes/devis/<id>/accepter/ : views/devis_cycle.py:560 (mono-option : pas d'`option`). */
async function creerReplique(request, { remise = '10', accepter = true, echeancier = ECHEANCIER } = {}) {
  const lead = await lireJson(await request.post(`${API}/crm/leads/`, { timeout: 120_000, 
    data: { nom: uniq('VNT Kharbachi'), ville: 'Casablanca', telephone: telephoneMobileUnique() },
  }), 'lead réplique')
  const lignes = []
  for (const [i, l] of LIGNES.entries()) {
    const donnees = { nom: `${l.d} ${Date.now()}-${i}`, prix_vente: l.pu }
    if (l.marque) donnees.marque = l.marque
    if (l.gar) donnees.garantie_mois = l.gar
    if (l.garProd) donnees.garantie_production_mois = l.garProd
    const produit = await lireJson(await request.post(`${API}/stock/produits/`, { timeout: 120_000,  data: donnees }), `produit ${l.d}`)
    lignes.push({
      produit: produit.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00',
      taux_tva: l.tva, type_ligne: 'produit', ordre: i,
    })
  }
  // À CONFIRMER : le corps `atomic` (produit requis par ligne, echeancier en en-tête) n'a pas été exécuté ici
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, { timeout: 120_000, 
    data: { lead: lead.id, taux_tva: '20.00', remise_globale: remise, echeancier: ECHEANCIER, lignes },
  }), 'devis réplique')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { timeout: 120_000,  data: { envoi: true } }), 'envoi du devis')
  if (accepter) await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { timeout: 120_000,  data: { nom: 'Tijani Kharbachi' } }), 'acceptation du devis')
  const relu = await lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`, { timeout: 120_000 }), 'devis relu')
  if (accepter) expect(relu.statut, 'devis accepté').toBe('accepte')
  return { leadId: lead.id, devisId: devis.id, reference: relu.reference }
}

async function nettoyer(request, r) {
  if (!r) return
  await request.delete(`${API}/ventes/devis/${r.devisId}/`, { timeout: 120_000 }).catch(() => null)
  await request.delete(`${API}/crm/leads/${r.leadId}/`, { timeout: 120_000 }).catch(() => null)
}

/** Corps d'étape avec réplique fraîche + nettoyage (best-effort). */
async function avecReplique(page, testInfo, corps, options) {
  testInfo.setTimeout(480_000)
  let r = null
  try {
    r = await creerReplique(page.request, options)
    await corps(r)
  } finally {
    await nettoyer(page.request, r)
  }
}

/** GET devis/<id>/facturer/ (contrat ventes/contract_samples/devis_facturer.json `apercu_get`). */
async function apercu(request, devisId) {
  return lireJson(await request.get(`${API}/ventes/devis/${devisId}/facturer/`, { timeout: 120_000 }), 'aperçu facturer')
}

/** Acompte posé par l'API (SETUP des étapes dont le geste testé vient après) —
 *  corps de la requête : devis_facturer.json `requete`. */
async function acompteParApi(request, devisId, { montant = '15000.00', payer = true, emettre = true } = {}) {
  const data = { nature: 'acompte', montant_ttc: montant, emettre }
  if (payer) data.paiements = [{ montant, date_paiement: DATE_PAIEMENT, mode_paiement: 'virement', reference: 'VIR-1012' }]
  const rep = await lireJson(await request.post(`${API}/ventes/devis/${devisId}/facturer/`, { timeout: 120_000,  data }), 'acompte par API')
  return rep.facture
}

/** Détail d'une facture : GET ventes/factures/<id>/ (FactureSerializer `__all__` : statut, total_ttc,
 *  montant_ht, montant_tva, ventilation_tva, objet_vente, garanties, tva_par_taux). */
async function facture(request, id) {
  return lireJson(await request.get(`${API}/ventes/factures/${id}/`, { timeout: 120_000 }), `facture ${id}`)
}

/** Ventilation TVA lue de `ventilation_tva` (sinon `tva_par_taux`), clés `base_ht`|`base` + `montant`. */
function ventilation(f) {
  const brut = (Array.isArray(f.ventilation_tva) && f.ventilation_tva.length ? f.ventilation_tva : f.tva_par_taux) || []
  return Object.fromEntries(brut.map((b) => [Number(b.taux), { base: f2(b.base_ht ?? b.base), tva: f2(b.montant ?? b.tva) }]))
}

/** Fiche lead (route /crm/leads/:id : features/crm/module.config.jsx:126) → onglet Devis
 *  (ContextRail.jsx:159 testid lw-context-rail, :169 onglet « N devis ») → panneau de vente
 *  (section « Vente du devis <ref> », PanneauVente.jsx:48-53, monté par DevisTab.jsx:463) → bouton
 *  « Facturer l'acompte » (PanneauVente.jsx:73-74, ouvert par `vente.peut.facturer_acompte`).
 *  VNT75 (lot M2) a retiré les 2 boutons legacy « Facturer (facture complète) » de DevisTab au profit
 *  de ce bouton ; il ouvre le MÊME dialogue VNT45 « Facturer — <ref> » (FacturerVenteDialog.jsx:416). */
function panneauVente(page, r) {
  return page.getByRole('region', { name: `Vente du devis ${r.reference}` })
}

async function ouvrirFacturer(page, r) {
  await page.goto(`/crm/leads/${r.leadId}`)
  await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  await panneauVente(page, r).getByRole('button', { name: "Facturer l'acompte" }).click()
  const dialogue = page.getByRole('dialog').filter({ has: page.getByTestId('facturer-vente-form') })
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  await expect(dialogue).toContainText(`Facturer — ${r.reference}`)
  return dialogue
}

/** « Créer la facture » (FacturerVenteDialog.jsx:405) et lecture de la réponse du POST
 *  devis/<id>/facturer/ (ventesApi.js:115) → `facture`. */
async function creerLaFacture(page, dialogue, devisId) {
  const cible = new RegExp(`/ventes/devis/${devisId}/facturer/$`)
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
    dialogue.getByRole('button', { name: 'Créer la facture' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBeLessThan(300)
  return (await rep.json()).facture
}

/** Liste des factures (/ventes/factures : ventes/module.config.jsx:156) filtrée par la recherche
 *  (placeholder « Référence, client… » : FactureList.jsx:979) → ligne `#facture-row-<id>` (FactureRow.jsx:132). */
async function ligneFacture(page, f) {
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(f.reference)
  const ligne = page.locator(`#facture-row-${f.id}`)
  await expect(ligne).toBeVisible({ timeout: 30_000 })
  return ligne
}

/** Menu « Plus d'actions » de la ligne (FactureRow.jsx:387). */
async function ouvrirActions(ligne) {
  await ligne.getByTitle("Plus d'actions").click()
}

/** PDF de la facture : GET ventes/factures/<id>/telecharger-pdf/ (ventesApi.js:422 ; views/facture.py:864 rend
 *  à la volée si jamais généré) ; sondage borné comme facturePdf.js. Texte extrait par pdfjs (helpers.js textePdf). */
async function pdfFacture(request, id) {
  // Attente par condition (ADEP24 : jamais un sommeil fixe) : expect.poll relit le GET
  // jusqu'au 200 (rendu à la volée côté serveur), puis on relit le corps.
  await expect.poll(async () => (await request.get(`${API}/ventes/factures/${id}/telecharger-pdf/`, { timeout: 120_000 })).status(),
    { timeout: 60_000, intervals: [1_000, 2_000] }).toBe(200)
  const rep = await request.get(`${API}/ventes/factures/${id}/telecharger-pdf/`, { timeout: 120_000 })
  const octets = await rep.body()
  expect(rep.headers()['content-type'] || '').toContain('application/pdf')
  expect(octets.subarray(0, 5).toString()).toBe('%PDF-')
  expect(octets.length).toBeGreaterThan(5_000)
  return { octets, texte: norm(await textePdf(octets)) }
}

etape('P1.1', plage(15, 23), async ({ page, testInfo }) => {
  // La réplique (lead + devis 11 lignes, remise 10 %, envoyé, accepté) porte le prix convenu 49 000,00
  // et rien n'est encore ÉMIS : GET devis/<id>/facturer/ (devis_facturer.json `apercu_get`).
  // Depuis VNT62 (lot M2, D-SIGN-AUTO = a : `accept_devis` crée le brouillon d'acompte 30 % = 14 700)
  // le reste à facturer = 49 000 − 14 700 = 34 300 (formule VNT16 `plan_facturation` : prix − émis −
  // brouillons, vente_facturation.py:398-404 ; dérivé admis par la règle (f) du groupe).
  await avecReplique(page, testInfo, async (r) => {
    const ap = await apercu(page.request, r.devisId)
    expect(f2(ap.vente.prix_convenu_ttc)).toBe('49000.00')
    expect(f2(ap.vente.emis_ttc)).toBe('0.00')
    expect(f2(ap.vente.brouillons_ttc), "brouillon d'acompte automatique (VNT62)").toBe('14700.00')
    expect(f2(ap.vente.reste_a_facturer_ttc)).toBe('34300.00')
    // Persistance : le lead s'ouvre, l'onglet Devis liste la réplique acceptée avec son bouton Facturer
    // (« Facturer l'acompte » du panneau de vente depuis VNT75 — voir ouvrirFacturer).
    await page.goto(`/crm/leads/${r.leadId}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await expect(page.getByTestId('lw-context-rail')).toContainText(r.reference)
    await expect(panneauVente(page, r).getByRole('button', { name: "Facturer l'acompte" })).toBeVisible()
    await page.reload()
    expect(f2((await apercu(page.request, r.devisId)).vente.prix_convenu_ttc)).toBe('49000.00')
  })
})

etape('P1.2', ['VNT25', ...plage(26, 31), 'VNT44', 'VNT45'], async ({ page, suivi, testInfo }) => {
  // Acompte 15 000 « déjà payé » virement 12/10 depuis la fiche lead.
  await avecReplique(page, testInfo, async (r) => {
    const dialogue = await ouvrirFacturer(page, r)
    await expect(dialogue.getByTestId('facturer-prix')).toContainText('49')          // prix convenu LU du serveur (:248)
    await dialogue.getByRole('tab', { name: 'Acompte' }).click()                    // onglets : FacturerVenteDialog.jsx:263-273
    await dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' }).fill('15000')  // :278-284
    await dialogue.getByRole('switch', { name: 'Déjà payé' }).click()                // :323
    const paiement = dialogue.getByTestId('facturer-paiement')                       // :326
    await expect(paiement).toBeVisible()
    await paiement.getByRole('spinbutton', { name: 'Montant encaissé' }).fill('15000')
    await paiement.getByLabel('Date du paiement').fill(DATE_PAIEMENT)
    await paiement.getByRole('combobox', { name: 'Mode de paiement' }).click()
    await page.getByRole('option', { name: 'Virement' }).click()                     // modesPaiement.js:5
    const f = await creerLaFacture(page, dialogue, r.devisId)
    expect(f.statut).toBe('payee')

    const detail = await facture(page.request, f.id)
    expect(detail.statut).toBe('payee')
    expect(f2(detail.total_ttc)).toBe('15000.00')
    expect(f2(detail.montant_ht)).toBe('12720.41')
    expect(f2(detail.montant_tva)).toBe('2279.59')
    // À CONFIRMER : forme de ventilation_tva / tva_par_taux d'une tranche sans lignes
    const vent = ventilation(detail)
    expect(vent[10]).toEqual({ base: '2644.90', tva: '264.49' })
    expect(vent[20]).toEqual({ base: '10075.51', tva: '2015.10' })

    const ap = await apercu(page.request, r.devisId)
    expect(f2(ap.vente.reste_a_facturer_ttc)).toBe('34000.00')
    expect(ap.prochaine.libelle).toBe('Livraison du matériel')
    expect(f2(ap.prochaine.montant_ttc)).toBe('29400.00')

    // Persistance : fiche rechargée sans erreur, puis la ligne de la facture figure dans la liste.
    await page.goto(`/crm/leads/${r.leadId}`)
    await page.reload()
    const ligne = await ligneFacture(page, f)
    await expect(ligne).toContainText(f.reference)
    suivi.verifie(5)
  })
})

etape('P1.3', plage(33, 42), async ({ page, suivi, testInfo }) => {
  // Le PDF réel de l'acompte payé + le détail API (objet_vente, garanties) ; aucun prix_achat.
  await avecReplique(page, testInfo, async (r) => {
    const f = await acompteParApi(page.request, r.devisId)
    const ap = await apercu(page.request, r.devisId)
    const detail = await facture(page.request, f.id)

    // Détail API : `objet_vente` et `garanties` sont des champs de modèle servis tels quels (FactureSerializer `__all__`).
    // `situation_vente` / `prochaines_echeances` ne sont PAS servis par le détail sur cet arbre (VNT89, lot M3) :
    // ils se prouvent sur le PDF ci-dessous et sur GET devis/<id>/facturer/. // À CONFIRMER : contrat facture_situation_vente.json
    expect(detail.objet_vente?.lignes, 'objet_vente figé à l\'émission').toHaveLength(11)
    expect(f2(detail.objet_vente.total_ttc)).toBe('49000.00')
    expect(Array.isArray(detail.garanties) && detail.garanties.length, 'garanties').toBeGreaterThanOrEqual(1)
    for (const g of detail.garanties) expect((g.duree || '').trim(), `garantie « ${g.libelle} » sans durée`).not.toBe('')
    expect(JSON.stringify(detail)).not.toContain('prix_achat')
    expect(f2(ap.vente.paye_ttc)).toBe('15000.00')
    expect(f2(ap.vente.reste_a_payer_ttc)).toBe('34000.00')

    // Le bouton PDF de la ligne existe (FactureRow.jsx:365-373) ; le fichier vient de telecharger-pdf.
    const ligne = await ligneFacture(page, f)
    await expect(ligne.getByRole('button', { name: /PDF/ }).first()).toBeVisible()

    const { texte } = await pdfFacture(page.request, f.id)
    // gabarit templates/pdf/facture.html (libellés :13-49, part de la vente :325-327, blocs :349-540)
    expect(texte).toContain('Objet de la vente')
    for (const d of ['Onduleur hybride Deye 5kW', 'Panneau Canadian Solar 710W', 'Batterie Dyness 5 kWh', 'Transport']) {
      expect(texte, `ligne « ${d} »`).toContain(d)
    }
    expect(texte).toMatch(/15000\.00 MAD/)
    expect(texte).toMatch(/12720\.41/)
    // Le PDF imprime la TVA PAR TAUX (chaîne de totaux CIQ215), jamais le total 2279.59 : on
    // vérifie les deux bases/TVA réelles du panier 388 ; le total TVA est prouvé sur l'API (ci-dessus).
    expect(texte).toMatch(/2644\.90/)
    expect(texte).toMatch(/264\.49/)
    expect(texte).toMatch(/10075\.51/)
    expect(texte).toMatch(/2015\.10/)
    // À CONFIRMER : mise en forme de la ventilation par taux (_chaine_totaux.html)
    for (const n of ['2644.90', '264.49', '10075.51', '2015.10']) expect(texte, `ventilation ${n}`).toContain(n)
    expect(texte).toMatch(/30\.61 % du prix convenu 49000\.00 MAD/)
    // En-tête de colonne `thead th` (facture.html:535) rendu en CAPITALES par `text-transform: uppercase`
    // (facture.html:94) : pdfjs extrait les glyphes imprimés « GARANTIES DURÉE DÉTAIL ».
    expect(texte).toContain('GARANTIES DURÉE DÉTAIL')
    expect(texte).toContain('Situation de la vente au')
    expect(texte).toContain('Prochaines échéances')
    expect(texte).toContain('Livraison du matériel')
    expect(texte, 'chaque chiffre du PDF == GET devis/<id>/facturer/').toContain(`${f2(ap.prochaine.montant_ttc)} MAD`)
    expect(texte).toMatch(/29400\.00 MAD/)
    expect(texte).toMatch(/4600\.00 MAD/)
    expect(texte).toMatch(/34000\.00/)
    expect(texte, 'filigrane absent d\'une facture émise').not.toContain('Sans valeur comptable')
    expect(texte.toLowerCase()).not.toMatch(/prix[ _]achat/)
    // Capital / forme juridique : dépend du profil société de la démo — non affirmé ici. // À CONFIRMER
    suivi.verifie(7)
  })
})

etape('P1.4', ['VNT45'], async ({ page, suivi, testInfo }) => {
  // Téléphone (375 px) : le dialogue s'ouvre en tiroir bas ; acompte tapé en POURCENTAGE (30 %) → 14 700,00.
  await avecReplique(page, testInfo, async (r) => {
    await page.setViewportSize({ width: 375, height: 812 })
    // À CONFIRMER : à 375 px l'onglet « Devis » du rail de contexte reste atteignable tel quel (ouvrirFacturer)
    const dialogue = await ouvrirFacturer(page, r)
    await expect(page.locator('[data-sheet-scroller]'), 'tiroir bas (ui/Sheet.jsx:168, side=bottom)').toBeVisible()
    // « Facturer l'acompte » doit ouvrir le dialogue SUR l'onglet Acompte (FacturerVenteDialog.jsx:52-58
    // `ongletParDefaut` : acompte tant qu'il n'est pas émis). L'onglet ouvert est LU une fois l'aperçu
    // serveur chargé (`facturer-prix`, même rendu que `setTab`), puis l'onglet Acompte est choisi pour
    // prouver le reste du geste (pourcentage → 14 700) ; l'onglet d'ouverture est affirmé en FIN d'étape
    // (expect dur : jamais `expect.soft`, que l'enregistreur _oracles.js:97-107 compterait PASS).
    await expect(dialogue.getByTestId('facturer-prix')).toContainText('49')
    const ongletAcompte = dialogue.getByRole('tab', { name: 'Acompte' })
    const acompteALOuverture = await ongletAcompte.getAttribute('aria-selected')
    await ongletAcompte.click()
    await dialogue.getByRole('spinbutton', { name: 'Pourcentage (%)' }).fill('30')   // FacturerVenteDialog.jsx:286-291
    await expect(dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' })).toHaveValue('')
    const f = await creerLaFacture(page, dialogue, r.devisId)
    const detail = await facture(page.request, f.id)
    expect(f2(detail.total_ttc)).toBe('14700.00')
    expect(f2(detail.montant_ht)).toBe('12466.00')
    expect(f2(detail.montant_tva)).toBe('2234.00')
    expect(f2((await apercu(page.request, r.devisId)).vente.reste_a_facturer_ttc)).toBe('34300.00')
    // Persistance : la ligne est listée après rechargement (liste au format téléphone).
    await ligneFacture(page, f)
    await page.reload()
    await expect(page.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 30_000 })
    expect(acompteALOuverture, "« Facturer l'acompte » ouvre le dialogue sur l'onglet Acompte").toBe('true')
    suivi.verifie(5)
  })
})

etape('P1.5', [...plage(10, 14), 'VNT46'], async ({ page, suivi, testInfo }) => {
  // Annuler (facture PAYÉE) depuis la liste : avoir de correction automatique, vente libérée.
  await avecReplique(page, testInfo, async (r) => {
    const f = await acompteParApi(page.request, r.devisId)   // setup : acompte payé 15 000
    const ligne = await ligneFacture(page, f)
    await ouvrirActions(ligne)
    await page.getByTestId('annuler-facture').click()        // FactureRow.jsx:494
    const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture ${f.reference}` })   // AnnulationFactureDialog.jsx
    await expect(dlg).toBeVisible()
    await expect(dlg.getByTestId('annulation-avoir')).toContainText('avoir de contre-passation')
    const garder = dlg.getByRole('radio', { name: 'Garder en avance client' })
    await expect(garder, 'directive jamais pré-cochée (AFAC13)').not.toBeChecked()
    const confirmer = dlg.getByRole('button', { name: 'Annuler la facture', exact: true })
    await expect(confirmer).toBeDisabled()
    await garder.check()
    await expect(confirmer).toBeEnabled()
    const cible = new RegExp(`/ventes/factures/${f.id}/annuler/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
      confirmer.click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)
    await expect(dlg).toHaveCount(0)

    const apres = await facture(page.request, f.id)
    expect(apres.statut).toBe('annulee')
    const avoirs = listeDe(await lireJson(await page.request.get(`${API}/ventes/avoirs/?facture=${f.id}`, { timeout: 120_000 }), 'avoirs de la facture'))
    expect(avoirs, 'un avoir de contre-passation').toHaveLength(1)
    expect(avoirs[0].type).toBe('correction')
    expect(f2(avoirs[0].total_ttc)).toBe('15000.00')
    const ap = await apercu(page.request, r.devisId)
    expect(f2(ap.vente.reste_a_facturer_ttc)).toBe('49000.00')
    // Avance client de 15 000 : aucun endpoint de lecture confirmé dans le code lu — assertion omise. // À CONFIRMER

    // Persistance : après rechargement la facture reste tracée (jamais supprimée), annulée.
    await page.reload()
    await page.getByPlaceholder('Référence, client').fill(f.reference)
    // À CONFIRMER : la liste montre les annulées par défaut
    await expect(page.locator(`#facture-row-${f.id}`)).toContainText(/Annulée/i, { timeout: 30_000 })
    suivi.verifie(5)
  })
})

etape('P1.6', ['VNT33', 'VNT34', 'VNT46'], async ({ page, suivi, testInfo }) => {
  // Refacturer l'acompte en BROUILLON (filigrane), puis supprimer ce brouillon ; la vente reste libre.
  await avecReplique(page, testInfo, async (r) => {
    // setup : acompte payé puis annulé (garder en avance) — corps de facture_annulation.json `requete_garder_en_avance`
    const payee = await acompteParApi(page.request, r.devisId)
    await lireJson(await page.request.post(`${API}/ventes/factures/${payee.id}/annuler/`, { timeout: 120_000, 
      data: { acompte: { action: 'garder_en_avance' } },
    }), 'annulation de l\'acompte (setup)')

    const dialogue = await ouvrirFacturer(page, r)
    await dialogue.getByRole('tab', { name: 'Acompte' }).click()
    await dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' }).fill('15000')
    const emettre = dialogue.getByRole('switch', { name: 'Émettre tout de suite' })   // FacturerVenteDialog.jsx:317
    await expect(emettre).toBeChecked()
    await emettre.click()
    await expect(emettre).not.toBeChecked()
    const f = await creerLaFacture(page, dialogue, r.devisId)
    expect(f.statut).toBe('brouillon')
    expect(f.reference).toMatch(/^BROUILLON-/)

    // Filigrane sur le PDF du brouillon (templates/pdf/facture.html:184-186 « BROUILLON » / « Sans valeur comptable »).
    // À CONFIRMER : telecharger-pdf sert aussi un brouillon
    const { texte } = await pdfFacture(page.request, f.id)
    expect(texte).toContain('BROUILLON')
    expect(texte).toContain('Sans valeur comptable')
    expect((await facture(page.request, f.id)).statut).toBe('brouillon')

    // Supprimer le brouillon par l'écran (FactureRow.jsx:507 puis :568).
    const ligne = await ligneFacture(page, f)
    await ouvrirActions(ligne)
    await page.getByTestId('supprimer-brouillon').click()
    const cible = new RegExp(`/ventes/factures/${f.id}/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'DELETE' && cible.test(new URL(x.url()).pathname)),
      page.getByTestId('supprimer-brouillon-confirmer').click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)

    // Persistance : disparu après rechargement ET côté API ; la vente reste libre.
    await page.reload()
    await page.getByPlaceholder('Référence, client').fill(f.reference)
    await expect(page.locator(`#facture-row-${f.id}`)).toHaveCount(0)
    expect((await page.request.get(`${API}/ventes/factures/${f.id}/`, { timeout: 120_000 })).status()).toBe(404)
    expect(f2((await apercu(page.request, r.devisId)).vente.reste_a_facturer_ttc)).toBe('49000.00')
    suivi.verifie(5)
  })
})

etape('P1.7', ['VNT44', 'VNT45'], async ({ page, suivi, testInfo }) => {
  // Montant 60 000 > reste : l'erreur s'affiche SOUS le champ + bandeau « Corrigez : Montant », jamais un toast.
  await avecReplique(page, testInfo, async (r) => {
    // refus d'état montant_depasse_reste (devis_facturer.json erreurs_409, ENF11) : le SEUL 4xx excusé
    suivi.attendre(new RegExp(`/ventes/devis/${r.devisId}/facturer/$`), 409)
    const dialogue = await ouvrirFacturer(page, r)
    await dialogue.getByRole('tab', { name: 'Acompte' }).click()
    const montant = dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' })
    await montant.fill('60000')
    await dialogue.getByRole('button', { name: 'Créer la facture' }).click()
    await expect(dialogue.getByTestId('facturer-bandeau')).toHaveText('Corrigez : Montant')   // erreursVente.js `bandeau`
    await expect(dialogue.locator('#facturer-montant-error')).toBeVisible()                    // ui/Form.jsx:60 `${htmlFor}-error`
    await expect(montant).toHaveAttribute('aria-invalid', 'true')
    await expect(page.locator('[data-sonner-toast]'), 'aucun toast d\'erreur').toHaveCount(0)
    await expect(dialogue, 'le dialogue reste ouvert').toBeVisible()
    // Persistance : rien n'a été facturé.
    expect(f2((await apercu(page.request, r.devisId)).vente.emis_ttc)).toBe('0.00')
  })
})

// ───────────────────────── Lot M2 (VNT83) : étapes P2.x ─────────────────────────
async function devisDetail(request, id) {
  return lireJson(await request.get(`${API}/ventes/devis/${id}/`, { timeout: 120_000 }), `devis ${id}`)
}

/** Facture(s) de la vente servies par le serveur (`vente.factures`, vente_etat.json). */
const venteDe = async (request, id) => (await devisDetail(request, id)).vente

etape('P2.1', ['VNT62', 'VNT74', 'VNT75'], async ({ page, suivi, testInfo }) => {
  // Accepter ⇒ brouillon d'acompte automatique (30 % de 54 500 = 16 350) visible dans le panneau ;
  // « Facturer l'acompte » 15 000 « déjà payé » ⇒ LE MÊME brouillon est émis et payé.
  await avecReplique(page, testInfo, async (r) => {
    const v0 = await venteDe(page.request, r.devisId)
    expect(f2(v0.prix_convenu_ttc)).toBe('54500.00')
    expect(v0.factures, "un seul brouillon d'acompte créé par l'acceptation").toHaveLength(1)
    const brouillon = v0.factures[0]
    expect([brouillon.nature, brouillon.statut, f2(brouillon.total_ttc)]).toEqual(['acompte', 'brouillon', '16350.00'])
    await page.goto(`/crm/leads/${r.leadId}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    const panneau = panneauVente(page, r)
    await expect(panneau.getByTestId(`facture-vente-${brouillon.id}`)).toContainText('Brouillon', { timeout: 30_000 })
    await expect(panneau.getByTestId(`facture-vente-${brouillon.id}`)).toContainText('BROUILLON-')

    const dialogue = await ouvrirFacturer(page, r)
    await dialogue.getByRole('tab', { name: 'Acompte' }).click()
    await dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' }).fill('15000')
    await dialogue.getByRole('switch', { name: 'Déjà payé' }).click()
    const paiement = dialogue.getByTestId('facturer-paiement')
    await paiement.getByRole('spinbutton', { name: 'Montant encaissé' }).fill('15000')
    await paiement.getByLabel('Date du paiement').fill(DATE_PAIEMENT)
    await paiement.getByRole('combobox', { name: 'Mode de paiement' }).click()
    await page.getByRole('option', { name: 'Virement' }).click()
    const f = await creerLaFacture(page, dialogue, r.devisId)
    expect(f.id, "le MÊME brouillon est émis (pas un 2e document)").toBe(brouillon.id)
    expect(f.statut).toBe('payee')
    expect(f.reference).not.toMatch(/^BROUILLON-/)

    // Persistance : rechargée, la vente a toujours UNE facture d'acompte, payée 15 000.
    await page.reload()
    const v1 = await venteDe(page.request, r.devisId)
    expect(v1.factures).toHaveLength(1)
    expect([v1.factures[0].id, v1.factures[0].statut, f2(v1.paye_ttc), f2(v1.reste_a_facturer_ttc)])
      .toEqual([brouillon.id, 'payee', '15000.00', '39500.00'])
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await expect(panneauVente(page, r).getByTestId(`facture-vente-${brouillon.id}`)).not.toContainText('Brouillon')
    suivi.verifie(5)
  }, { remise: '0' })
})

etape('P2.2', ['VNT58', 'VNT59', 'VNT60', 'VNT64', 'VNT73', 'VNT78'], async ({ page, suivi, testInfo }) => {
  // « Prix négocié » 49 000 depuis le panneau : aperçu serveur (remise 10,00 %), application ⇒ V2 acceptée,
  // V1 remplacée, acompte payé repris, reste à facturer 34 000 ; le lien d'avenant s'affiche.
  await avecReplique(page, testInfo, async (r) => {
    const acompte = await acompteParApi(page.request, r.devisId)
    await page.goto(`/crm/leads/${r.leadId}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await panneauVente(page, r).getByRole('button', { name: 'Prix négocié' }).click()
    const dlg = page.getByRole('dialog').filter({ hasText: 'Prix négocié' })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.getByLabel('Nouveau prix TTC (MAD)').fill('49000')
    await dlg.getByRole('button', { name: 'Voir les effets' }).click()
    const effets = dlg.getByRole('list', { name: 'Effets du prix négocié' }).or(dlg.locator('dl[aria-label="Effets du prix négocié"]'))
    await expect(effets).toContainText('10,00', { timeout: 30_000 })
    await expect(effets).toContainText('49')
    const cible = new RegExp(`/ventes/devis/${r.devisId}/prix-negocie/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
      dlg.getByRole('button', { name: 'Appliquer le prix négocié' }).click(),
    ])
    expect(rep.status(), await rep.text()).toBe(201)
    const corps = await rep.json()
    expect(f2(corps.remise_pct)).toBe('10.00')
    expect(f2(corps.total_ttc)).toBe('49000.00')
    await expect(dlg).toContainText(`Version 2 créée : ${corps.devis_v2.reference}`)

    const v2 = await devisDetail(page.request, corps.devis_v2.id)
    expect([v2.statut, v2.is_active, f2(v2.total_ttc)]).toEqual(['accepte', true, '49000.00'])
    const v1 = await devisDetail(page.request, r.devisId)
    expect(v1.is_active, 'V1 remplacée').toBe(false)
    expect(v1.vente.est_tete).toBe(false)
    expect(v1.vente.tete_id).toBe(v2.id)
    expect(f2(v2.vente.prix_convenu_ttc)).toBe('49000.00')
    expect(v2.vente.factures.map((x) => x.id), 'acompte payé repris sur la V2').toContain(acompte.id)
    expect(f2(v2.vente.paye_ttc)).toBe('15000.00')
    expect(f2(v2.vente.reste_a_facturer_ttc)).toBe('34000.00')
    r.v2 = v2
    // Persistance : après rechargement la fiche montre la V2 acceptée avec son panneau ; la V1 n'a aucun bouton.
    await page.reload()
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    const pV1 = panneauVente(page, r)
    await expect(pV1).toContainText('Remplacé par')
    await expect(pV1.getByRole('button', { name: /Facturer|Prix négocié/ })).toHaveCount(0)
    await expect(page.getByRole('region', { name: `Vente du devis ${v2.reference}` })).toBeVisible()
    suivi.verifie(5)
  }, { remise: '0' })
})

/** POST devis/<id>/prix-negocie/ (contrat devis_prix_negocie.json) — SETUP des étapes dont le geste testé vient après. */
async function prixNegocieParApi(request, devisId, prix) {
  return lireJson(await request.post(`${API}/ventes/devis/${devisId}/prix-negocie/`, {
    timeout: 120_000, data: { prix_ttc: prix, mode: 'appliquer' },
  }), 'prix négocié par API')
}

/** PUT devis/<id>/echeancier/ (VNT66, devis_echeancier.json) : acompte 15 000 conservé + SOLDE = reste (34 000).
 *  Sans cela la tranche suivante d'un échéancier 30/60/10 est « Livraison du matériel » 29 400 (observé). */
async function echeancierSolde(request, devisId) {
  return lireJson(await request.put(`${API}/ventes/devis/${devisId}/echeancier/`, { timeout: 120_000, data: { tranches: [
    { cle: 'acompte', libelle: 'Acompte', unite: 'montant', valeur: '15000.00' },
    { cle: 'solde', libelle: 'Solde', unite: 'montant', valeur: '34000.00' },
  ] } }), "échéancier acompte + solde")
}

const ligneVente = (panneau, f) => panneau.getByTestId(`facture-vente-${f.id}`)
const ongletDevis = (page) => page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i })

etape('P2.3', ['VNT67', 'VNT75', 'VNT77'], async ({ page, suivi, testInfo }) => {
  // Brouillon d'acompte automatique : Modifier le montant (→ 15 000) puis Supprimer, depuis le panneau.
  await avecReplique(page, testInfo, async (r) => {
    const brouillon = (await venteDe(page.request, r.devisId)).factures[0]
    expect([brouillon.statut, f2(brouillon.total_ttc)]).toEqual(['brouillon', '14700.00'])
    await page.goto(`/crm/leads/${r.leadId}`)
    await ongletDevis(page).click()
    const ligne = ligneVente(panneauVente(page, r), brouillon)
    await expect(ligne).toBeVisible({ timeout: 30_000 })
    await ligne.getByRole('button', { name: 'Modifier le montant' }).click()
    await ligne.getByLabel(`Montant TTC de ${brouillon.reference}`).fill('15000')
    const cible = new RegExp(`/ventes/factures/${brouillon.id}/montant-tranche/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
      ligne.getByRole('button', { name: 'Enregistrer' }).click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)
    expect(f2((await facture(page.request, brouillon.id)).total_ttc)).toBe('15000.00')
    const v1 = await venteDe(page.request, r.devisId)
    expect([f2(v1.brouillons_ttc), f2(v1.emis_ttc), f2(v1.reste_a_facturer_ttc)]).toEqual(['15000.00', '0.00', '34000.00'])
    // Persistance : rechargé, le panneau affiche 15 000.
    await page.reload()
    await ongletDevis(page).click()
    await expect(ligneVente(panneauVente(page, r), brouillon)).toContainText('15', { timeout: 30_000 })

    // Supprimer le brouillon par le panneau (dialogue de confirmation).
    const l2 = ligneVente(panneauVente(page, r), brouillon)
    await l2.getByRole('button', { name: 'Supprimer' }).click()
    const supp = new RegExp(`/ventes/factures/${brouillon.id}/$`)
    const [rep2] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'DELETE' && supp.test(new URL(x.url()).pathname)),
      page.getByTestId('supprimer-brouillon-confirmer').click(),
    ])
    expect(rep2.status(), await rep2.text()).toBeLessThan(300)
    await page.reload()
    await ongletDevis(page).click()
    await expect(panneauVente(page, r)).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId(`facture-vente-${brouillon.id}`)).toHaveCount(0)
    const v2 = await venteDe(page.request, r.devisId)
    expect(v2.factures).toHaveLength(0)
    expect(f2(v2.reste_a_facturer_ttc)).toBe('49000.00')
    suivi.verifie(5)
  })
})

etape('P2.4', ['VNT75', 'VNT77'], async ({ page, suivi, testInfo }) => {
  // Acompte payé 15 000 → « Facturer … » (Totalité) en brouillon 34 000 → Supprimer ce brouillon →
  // Annuler l'acompte émis : directive puis avoir de contre-passation.
  await avecReplique(page, testInfo, async (r0) => {
    const acompte = await acompteParApi(page.request, r0.devisId)
    const neg = await prixNegocieParApi(page.request, r0.devisId, '49000')
    await echeancierSolde(page.request, neg.devis_v2.id)
    const r = { leadId: r0.leadId, devisId: neg.devis_v2.id, reference: neg.devis_v2.reference }   // la tête de vente est la V2
    const ap = await apercu(page.request, r.devisId)
    expect([(await venteDe(page.request, r.devisId)).prochaine_action, f2(ap.prochaine?.montant_ttc)], 'prochaine tranche attendue : le solde 34 000').toEqual(['solde', '34000.00'])
    await page.goto(`/crm/leads/${r.leadId}`)
    await ongletDevis(page).click()
    await panneauVente(page, r).getByRole('button', { name: 'Facturer le solde' }).click()
    const dialogue = page.getByRole('dialog').filter({ has: page.getByTestId('facturer-vente-form') })
    await expect(dialogue).toBeVisible({ timeout: 30_000 })
    await dialogue.getByRole('tab', { name: 'Solde' }).click()
    const emettre = dialogue.getByRole('switch', { name: 'Émettre tout de suite' })
    await emettre.click()
    await expect(emettre).not.toBeChecked()
    const f = await creerLaFacture(page, dialogue, r.devisId)
    expect(f.statut).toBe('brouillon')
    expect(f2((await facture(page.request, f.id)).total_ttc)).toBe('34000.00')
    // Supprimer ce brouillon depuis le panneau.
    await page.reload()
    await ongletDevis(page).click()
    const lb = ligneVente(panneauVente(page, r), f)
    await expect(lb).toBeVisible({ timeout: 30_000 })
    await lb.getByRole('button', { name: 'Supprimer' }).click()
    const supp = new RegExp(`/ventes/factures/${f.id}/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'DELETE' && supp.test(new URL(x.url()).pathname)),
      page.getByTestId('supprimer-brouillon-confirmer').click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)
    expect((await page.request.get(`${API}/ventes/factures/${f.id}/`, { timeout: 120_000 })).status()).toBe(404)

    // Annuler l'acompte émis (payé) depuis le panneau : directive, puis avoir.
    await page.reload()
    await ongletDevis(page).click()
    const la = ligneVente(panneauVente(page, r), acompte)
    await expect(la).toBeVisible({ timeout: 30_000 })
    await la.getByRole('button', { name: 'Annuler', exact: true }).click()
    const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture ${acompte.reference}` })
    await expect(dlg).toBeVisible()
    const garder = dlg.getByRole('radio', { name: 'Garder en avance client' })
    await expect(garder).not.toBeChecked()
    const confirmer = dlg.getByRole('button', { name: 'Annuler la facture', exact: true })
    await expect(confirmer).toBeDisabled()
    await garder.check()
    const ann = new RegExp(`/ventes/factures/${acompte.id}/annuler/$`)
    const [rep2] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && ann.test(new URL(x.url()).pathname)),
      confirmer.click(),
    ])
    expect(rep2.status(), await rep2.text()).toBeLessThan(300)
    expect((await facture(page.request, acompte.id)).statut).toBe('annulee')
    const avoirs = listeDe(await lireJson(await page.request.get(`${API}/ventes/avoirs/?facture=${acompte.id}`, { timeout: 120_000 }), 'avoirs'))
    expect(avoirs).toHaveLength(1)
    expect(f2(avoirs[0].total_ttc)).toBe('15000.00')
    expect(f2((await venteDe(page.request, r.devisId)).reste_a_facturer_ttc)).toBe('49000.00')
    await page.reload()
    await ongletDevis(page).click()
    await expect(panneauVente(page, r)).toBeVisible({ timeout: 30_000 })
    // Observé : le panneau ne garde plus la ligne d'une facture ANNULÉE (la vente ne montre que les factures en vigueur) ;
    // si elle y figure, elle porte la pastille « Annulée » et aucun bouton d'annulation.
    if (await page.getByTestId(`facture-vente-${acompte.id}`).count()) {
      await expect(ligneVente(panneauVente(page, r), acompte)).toContainText('Annulée')
      await expect(ligneVente(panneauVente(page, r), acompte).getByRole('button', { name: 'Annuler', exact: true })).toHaveCount(0)
    }
    suivi.verifie(5)
  }, { remise: '0' })
})

etape('P2.5', ['VNT54'], async ({ page, testInfo, suivi }) => {
  // Une 2e vente sur le MÊME lead : accepter un 2e devis ⇒ 409 vente_active_existante nommant la vente en vigueur.
  await avecReplique(page, testInfo, async (r) => {
    const produit = await lireJson(await page.request.post(`${API}/stock/produits/`, { timeout: 120_000,
      data: { nom: `VNT 2e ${Date.now()}`, prix_vente: '1000.00' } }), 'produit 2e devis')
    const d2 = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, { timeout: 120_000,
      data: { lead: r.leadId, taux_tva: '20.00', lignes: [{ produit: produit.id, designation: 'Deuxième affaire', quantite: '1',
        prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), '2e devis')
    await lireJson(await page.request.post(`${API}/ventes/devis/${d2.id}/share-link/`, { timeout: 120_000, data: { envoi: true } }), 'envoi 2e devis')
    suivi.attendre(new RegExp(`/ventes/devis/${d2.id}/accepter/$`), 409)
    const rep = await page.request.post(`${API}/ventes/devis/${d2.id}/accepter/`, { timeout: 120_000, data: { nom: 'Tijani Kharbachi' } })
    expect(rep.status()).toBe(409)
    const corps = await rep.json()
    expect(corps.code).toBe('vente_active_existante')
    expect(corps.vente_active.reference).toBe(r.reference)
    expect((await devisDetail(page.request, d2.id)).statut, "rien n'a été accepté").toBe('envoye')
  })
})

etape('P2.6', ['VNT60', 'VNT61'], async ({ page, testInfo }) => {
  // Avenant : « Faire signer l'avenant » = lien public + UNE tâche (idempotent) ; le client signe par le lien :
  // confirmation, statut inchangé (accepté). La PAGE publique (apps/web, bandeau) n'est pas servie par cette pile :
  // seule l'API publique qu'elle appelle est rejouée ici.
  await avecReplique(page, testInfo, async (r) => {
    const neg = await prixNegocieParApi(page.request, r.devisId, '49000')
    const v2Id = neg.devis_v2.id
    const demande = async () => lireJson(await page.request.post(`${API}/ventes/devis/${v2Id}/avenant/demander-signature/`,
      { timeout: 120_000 }), 'demande de signature')
    const a = await demande()
    const b = await demande()
    expect(a.share_link).toMatch(/\/proposition\/[^/]+$/)
    expect(b.share_link, 'lien réutilisé, jamais régénéré').toBe(a.share_link)
    expect(a.tache_id, 'UNE tâche, idempotente').toBeTruthy()
    expect(b.tache_id).toBe(a.tache_id)
    const jeton = a.share_link.split('/').pop()
    const lue = await lireJson(await page.request.get(`${API}/ventes/proposal/${jeton}/`, { timeout: 120_000 }), 'proposition publique')
    expect(lue.avenant?.a_signer, 'avenant à signer').toBe(true)
    expect(lue.avenant.remplace.reference).toBe(r.reference)
    expect(lue.avenant.signe_le).toBeNull()
    const sign = await page.request.post(`${API}/ventes/proposal/${jeton}/accept/`, { timeout: 120_000, data: {
      nom: 'Tijani Kharbachi', consent_esign: true, empreinte_contenu: lue.empreinte_contenu,
      signature_data_url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
      signed_at_client: new Date().toISOString(), langue: 'fr',
    } })
    expect(sign.status(), await sign.text()).toBe(200)
    const corps = await sign.json()
    expect(corps.avenant_signe?.signe_le).toBeTruthy()
    expect(corps.statut, 'statut inchangé (règle #4)').toBe('accepte')
    // Persistance : relue, l'avenant n'est plus « à signer », la V2 reste acceptée active.
    const relue = await lireJson(await page.request.get(`${API}/ventes/proposal/${jeton}/`, { timeout: 120_000 }), 'proposition relue')
    expect(relue.avenant.a_signer).toBe(false)
    expect(relue.avenant.signe_le).toBeTruthy()
    const v2 = await devisDetail(page.request, v2Id)
    expect([v2.statut, v2.is_active]).toEqual(['accepte', true])
  }, { remise: '0' })
})

etape('P2.7', ['VNT53', 'VNT55'], async ({ page, testInfo }) => {
  // Parcours classique Réviser → Envoyer la V2 d'un accepté : 0 étape de cadence commerciale, UNE tâche
  // « Faire signer l'avenant » (ADEV57). Puis abandonner la révision rend la V1 active (VNT55) — sur une 2e réplique.
  await avecReplique(page, testInfo, async (r) => {
    const etapes = async () => listeDe(await lireJson(await page.request.get(`${API}/crm/relance-etapes/?lead=${r.leadId}`,
      { timeout: 120_000 }), 'étapes de cadence'))
    const avant = new Set((await etapes()).map((e) => e.id))
    const v2 = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/reviser/`, { timeout: 120_000 }), 'révision')
    expect(v2.version).toBe(2)
    await lireJson(await page.request.post(`${API}/ventes/devis/${v2.id}/share-link/`, { timeout: 120_000, data: { envoi: true } }), 'envoi de la V2')
    expect((await devisDetail(page.request, v2.id)).statut).toBe('envoye')
    const nouvelles = (await etapes()).filter((e) => !avant.has(e.id))
    expect(nouvelles.map((e) => e.libelle), 'aucune étape de cadence commerciale, une tâche avenant').toEqual(['Faire signer l’avenant'])
    // Persistance : relue, toujours UNE tâche avenant ouverte.
    const relues = (await etapes()).filter((e) => e.libelle === 'Faire signer l’avenant')
    expect(relues).toHaveLength(1)
  }, { remise: '10' })
  await avecReplique(page, testInfo, async (r) => {
    const v2 = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/reviser/`, { timeout: 120_000 }), 'révision')
    expect((await devisDetail(page.request, r.devisId)).is_active, 'V1 désactivée par Réviser').toBe(false)
    const sup = await page.request.delete(`${API}/ventes/devis/${v2.id}/`, { timeout: 120_000 })
    expect(sup.status(), await sup.text()).toBeLessThan(300)
    const v1 = await devisDetail(page.request, r.devisId)
    expect([v1.statut, v1.is_active], 'révision abandonnée : la V1 acceptée redevient active').toEqual(['accepte', true])
  })
})

// ───────────────────────── Lot M3 (VNT95) : étapes P3.x ─────────────────────────
const lireFunnelSigne = async (request) => {
  const d = await lireJson(await request.get(`${API}/reporting/commercial/dashboard/`, { timeout: 120_000 }), 'tableau de bord commercial')
  const signe = d.funnel.find((e) => e.label === STAGE_LABELS.SIGNED)
  return { count: signe.count, valeur: Number(signe.valeur), total_signes: d.total_signes }
}

/** Code exécuté dans le conteneur Django (E2E_DJANGO_EXEC) : `manage.py shell` y démarre en ~3 min. */
function shellDjango(code) {
  const surmesure = process.env.E2E_DJANGO_EXEC
  if (!surmesure) throw new Error('E2E_DJANGO_EXEC absent : lecture du carnet impossible')
  const [cmd, ...args] = surmesure.split(' ')
  return execFileSync(cmd, [...args, 'python', 'manage.py', 'shell', '-c', code], { stdio: 'pipe', timeout: 2_000_000 }).toString()
}

etape('P3.1', ['VNT84', 'VNT85', 'VNT86'], async ({ page, testInfo }) => {
  // Chaîne révisée (V1 54 500 acceptée → Prix négocié 49 000 = V2) : le KPI « devis signés » ne compte qu'UNE vente
  // (49 000) et l'intégrité ne signale pas la V1 remplacée.
  const avant = await lireFunnelSigne(page.request)
  await avecReplique(page, testInfo, async (r) => {
    await prixNegocieParApi(page.request, r.devisId, '49000')
    const apres = await lireFunnelSigne(page.request)
    expect(apres.count - avant.count, 'une seule vente signée comptée').toBe(1)
    expect(apres.total_signes - avant.total_signes).toBe(1)
    expect((apres.valeur - avant.valeur).toFixed(2), 'valeur signée = 49 000 (jamais 54 500 + 49 000)').toBe('49000.00')
    const integ = await lireJson(await page.request.get(`${API}/reporting/insights/integrite/`, { timeout: 120_000 }), 'intégrité')
    expect(JSON.stringify(integ), "la V1 remplacée n'est pas signalée « acceptée sans chantier »").not.toContain(r.reference)
  }, { remise: '0' })
})

etape('P3.4', ['VNT88'], async ({ page, testInfo }) => {
  // Carnet / rappel « à facturer » (sélecteurs sans route HTTP : lus dans le conteneur Django) — la V2 est
  // rappelée, la V1 remplacée jamais. `manage.py shell` y démarre en plusieurs minutes sur cette pile chargée.
  await avecReplique(page, testInfo, async (r) => {
    testInfo.setTimeout(2_400_000)
    const neg = await prixNegocieParApi(page.request, r.devisId, '49000')
    const code = ['from apps.ventes.models import Devis',
      'from apps.ventes.selectors_facturation import devis_a_facturer',
      `d = Devis.objects.get(pk=${neg.devis_v2.id})`,
      'ids = sorted(x.id for x in devis_a_facturer(d.company, jours=-1))',
      "print('IDS=' + ','.join(map(str, ids)))"].join('\n') + '\n'
    const sortie = shellDjango(code)
    const ids = (/IDS=([\d,]*)/.exec(sortie)?.[1] || '').split(',').filter(Boolean).map(Number)
    expect(ids, 'la V2 (vente en vigueur sans facture) est rappelée').toContain(neg.devis_v2.id)
    expect(ids, "la V1 remplacée n'est jamais rappelée").not.toContain(r.devisId)
  }, { remise: '0' })
})

etape('P3.2', ['VNT89', 'VNT91', 'VNT92'], async ({ page, suivi, testInfo }) => {
  // Vente démo : acompte 15 000 payé puis solde (reste à facturer 34 000) émis. PDF du solde, reçu de l'acompte
  // et détail API concordent au centime ; la porte manuelle `devis` est fermée.
  await avecReplique(page, testInfo, async (r) => {
    const acompte = await acompteParApi(page.request, r.devisId)
    const neg = await prixNegocieParApi(page.request, r.devisId, '49000')   // 54 500 -> 49 000 : la V2 est la tête de vente
    r.devisId = neg.devis_v2.id
    await echeancierSolde(page.request, r.devisId)
    const rep = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/facturer/`, { timeout: 120_000,
      data: { nature: 'solde', emettre: true } }), 'facture du solde')
    const solde = rep.facture
    const detail = await facture(page.request, solde.id)
    const sv = detail.situation_vente
    expect(sv, 'situation_vente servie par le DÉTAIL').toBeTruthy()
    expect([f2(sv.prix_convenu_ttc), f2(sv.emis_ttc), f2(sv.paye_ttc), f2(sv.reste_a_payer_ttc)])
      .toEqual(['49000.00', '49000.00', '15000.00', '34000.00'])
    const ligneAcompte = sv.factures.find((x) => x.id === acompte.id)
    expect([ligneAcompte.statut, f2(ligneAcompte.total_ttc)]).toEqual(['payee', '15000.00'])
    const { texte } = await pdfFacture(page.request, solde.id)
    expect(texte).toContain('Situation de la vente au')
    expect(texte).toContain(acompte.reference)
    expect(texte).toMatch(/15000\.00 MAD/)
    expect(texte).toContain('Payée')
    expect(texte).toContain('Reste dû sur la vente')
    for (const k of ['prix_convenu_ttc', 'emis_ttc', 'paye_ttc', 'reste_a_payer_ttc']) {
      expect(texte, `PDF == détail API : ${k}`).toContain(`${f2(sv[k])} MAD`)
    }
    // Reçu de l'acompte (UN paiement) : « Reste dû sur la vente » == etat_vente.
    const paiement = (await venteDe(page.request, r.devisId)).factures.find((x) => x.id === acompte.id).paiements[0]
    const recu = await page.request.get(`${API}/ventes/paiements/${paiement.id}/recu-pdf/`, { timeout: 120_000 })
    expect(recu.status()).toBe(200)
    const octets = await recu.body()
    expect(octets.subarray(0, 5).toString()).toBe('%PDF-')
    const texteRecu = norm(await textePdf(octets))
    expect(texteRecu).toContain('Reste dû sur la vente')
    expect(texteRecu).toContain('34000.00 MAD')
    expect([r.reference, neg.devis_v2.reference].some((ref) => texteRecu.includes(ref)), 'le reçu nomme le devis de la vente (V1 ou V2)').toBe(true)
    // Porte manuelle fermée (VNT89) : créer une facture avec `devis` dans le corps est refusé.
    suivi.attendre(new RegExp(`${API}/ventes/factures/$`), 400)
    const manuel = await page.request.post(`${API}/ventes/factures/`, { timeout: 120_000, data: { devis: r.devisId, client: (await devisDetail(page.request, r.devisId)).client, date_emission: DATE_PAIEMENT } })
    expect(manuel.status()).toBe(400)
    expect(await manuel.text()).toContain('facture_de_devis')
  }, { remise: '0' })
})

etape('P3.3', ['VNT93', 'VNT92'], async ({ page, testInfo }) => {
  // Rendu arabe (client langue_document='ar') des nouveaux blocs du PDF de facture et du reçu : aucune clé brute.
  await avecReplique(page, testInfo, async (r) => {
    const acompte = await acompteParApi(page.request, r.devisId)
    const neg = await prixNegocieParApi(page.request, r.devisId, '49000')   // 54 500 -> 49 000 : la V2 est la tête de vente
    r.devisId = neg.devis_v2.id
    await echeancierSolde(page.request, r.devisId)
    const rep = await lireJson(await page.request.post(`${API}/ventes/devis/${r.devisId}/facturer/`, { timeout: 120_000,
      data: { nature: 'solde', emettre: true } }), 'facture du solde')
    const dv = await devisDetail(page.request, r.devisId)
    const maj = await page.request.patch(`${API}/crm/clients/${dv.client}/`, { timeout: 120_000, data: { langue_document: 'ar' } })
    expect(maj.status(), await maj.text()).toBeLessThan(300)
    const { texte } = await pdfFacture(page.request, rep.facture.id)
    expect(texte, 'bloc en arabe').toMatch(/[؀-ۿ]/)
    expect(texte).toContain('وضعية البيع')
    for (const cle of ['situation_vente_au', 'prix_convenu', 'reste_du_sur_la_vente', 'prochaines_echeances', 'cette_facture', 'total_facture', 'paye_sur_la_vente', 'reste_a_facturer']) {
      expect(texte, `clé brute « ${cle} » imprimée`).not.toContain(cle)
    }
    expect(texte).not.toContain('Situation de la vente au')
    const paiement = (await venteDe(page.request, r.devisId)).factures.find((x) => x.id === acompte.id).paiements[0]
    const recu = await page.request.get(`${API}/ventes/paiements/${paiement.id}/recu-pdf/`, { timeout: 120_000 })
    expect(recu.status()).toBe(200)
    const texteRecu = norm(await textePdf(await recu.body()))
    expect(texteRecu, 'reçu en arabe').toMatch(/[؀-ۿ]/)
    expect(texteRecu, 'clé française brute du reçu').not.toContain('Reste dû sur la vente')
  }, { remise: '0' })
})

// ───────────────────────── Lot M4 (VNT107) : étapes P4.x ─────────────────────────
etape('P4.1', ['VNT97', 'VNT98', 'VNT100', 'VNT102', 'VNT104', 'VNT105'], async ({ page, suivi, testInfo }) => {
  // Non-régression du parcours M1 sur le code découpé : Facturer l'acompte (UI), liste des factures, PDF,
  // encaissement, Annuler (avoir automatique) — mêmes écrans, mêmes montants que P1.2 / P1.5.
  await avecReplique(page, testInfo, async (r) => {
    const dialogue = await ouvrirFacturer(page, r)
    await dialogue.getByRole('tab', { name: 'Acompte' }).click()
    await dialogue.getByRole('spinbutton', { name: 'Montant (MAD)' }).fill('15000')
    const f = await creerLaFacture(page, dialogue, r.devisId)
    expect(f.statut).toBe('emise')
    const ligne = await ligneFacture(page, f)
    await expect(ligne).toContainText(f.reference)
    await ligne.getByRole('button', { name: /PDF/ }).first().waitFor()
    const { texte } = await pdfFacture(page.request, f.id)
    expect(texte).toMatch(/15000\.00 MAD/)
    // Encaissement (module encaissement découpé, VNT98).
    const enc = await page.request.post(`${API}/ventes/factures/${f.id}/enregistrer-paiement/`, { timeout: 120_000,
      data: { montant: '15000.00', date_paiement: DATE_PAIEMENT, mode_paiement: 'virement', reference: 'VIR-4' } })
    expect(enc.status(), await enc.text()).toBeLessThan(300)
    expect((await facture(page.request, f.id)).statut).toBe('payee')
    // Annuler depuis la liste (cycle découpé, VNT97) : avoir de contre-passation.
    const l2 = await ligneFacture(page, f)
    await ouvrirActions(l2)
    await page.getByTestId('annuler-facture').click()
    const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture ${f.reference}` })
    await expect(dlg).toBeVisible()
    await dlg.getByRole('radio', { name: 'Garder en avance client' }).check()
    const cible = new RegExp(`/ventes/factures/${f.id}/annuler/$`)
    const [rep] = await Promise.all([
      page.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname)),
      dlg.getByRole('button', { name: 'Annuler la facture', exact: true }).click(),
    ])
    expect(rep.status(), await rep.text()).toBeLessThan(300)
    expect((await facture(page.request, f.id)).statut).toBe('annulee')
    const avoirs = listeDe(await lireJson(await page.request.get(`${API}/ventes/avoirs/?facture=${f.id}`, { timeout: 120_000 }), 'avoirs'))
    expect(avoirs).toHaveLength(1)
    expect(f2(avoirs[0].total_ttc)).toBe('15000.00')
    await page.reload()
    await page.getByPlaceholder('Référence, client').fill(f.reference)
    await expect(page.locator(`#facture-row-${f.id}`)).toContainText(/Annulée/i, { timeout: 30_000 })
    suivi.verifie(5)
  })
})

etape('P4.2', ['VNT103', 'VNT106'], async ({ page, suivi, testInfo }) => {
  // Renouveler un devis ACCEPTÉ ⇒ 409 deuxieme_affaire, rien créé ; les champs retirés (acompte_pct/montant)
  // ne sont plus servis.
  await avecReplique(page, testInfo, async (r) => {
    const avant = listeDe(await lireJson(await page.request.get(`${API}/ventes/devis/?lead=${r.leadId}`, { timeout: 120_000 }), 'devis du lead'))
    suivi.attendre(new RegExp(`/ventes/devis/${r.devisId}/renouveler/$`), 409)
    const rep = await page.request.post(`${API}/ventes/devis/${r.devisId}/renouveler/`, { timeout: 120_000 })
    expect(rep.status(), await rep.text()).toBe(409)
    expect((await rep.json()).code).toBe('deuxieme_affaire')
    const apres = listeDe(await lireJson(await page.request.get(`${API}/ventes/devis/?lead=${r.leadId}`, { timeout: 120_000 }), 'devis du lead'))
    expect(apres, 'rien créé').toHaveLength(avant.length)
    const brut = JSON.stringify(await devisDetail(page.request, r.devisId))
    expect(brut).not.toContain('acompte_pct')
    expect(brut).not.toContain('acompte_montant')
  })
})
