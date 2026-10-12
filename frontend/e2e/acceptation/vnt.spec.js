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
import { groupe } from './_oracles.js'
import { uniq, lireJson, listeDe, textePdf, telephoneMobileUnique } from '../helpers.js'

const plage = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => `VNT${a + i}`)
const etape = groupe('VNT', [
  ...plage(10, 23), ...plage(25, 31), ...plage(33, 42), 'VNT44', 'VNT45', 'VNT46',
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

/** Lead + devis (11 lignes) créés par l'API, envoyé puis accepté.
 *  - POST crm/leads/ : patron de suivi-commercial.spec.js:73 ;
 *  - POST stock/produits/ : patron de comptes-justes.spec.js:46 (+ marque, garantie_mois, garantie_production_mois
 *    de stock/serializers.py:742,789) ;
 *  - POST ventes/devis/atomic/ : views/devis_edition.py:206 (corps = en-tête + `lignes`, lead OU client) ;
 *  - POST ventes/devis/<id>/share-link/ {envoi:true} : views/devis_envoi.py:101 (brouillon → envoyé via
 *    mark_devis_sent, sans e-mail) ; statut en lecture seule (serializers.py:1129) ;
 *  - POST ventes/devis/<id>/accepter/ : views/devis_cycle.py:560 (mono-option : pas d'`option`). */
async function creerReplique(request) {
  const lead = await lireJson(await request.post(`${API}/crm/leads/`, {
    data: { nom: uniq('VNT Kharbachi'), ville: 'Casablanca', telephone: telephoneMobileUnique() },
  }), 'lead réplique')
  const lignes = []
  for (const [i, l] of LIGNES.entries()) {
    const donnees = { nom: `${l.d} ${Date.now()}-${i}`, prix_vente: l.pu }
    if (l.marque) donnees.marque = l.marque
    if (l.gar) donnees.garantie_mois = l.gar
    if (l.garProd) donnees.garantie_production_mois = l.garProd
    const produit = await lireJson(await request.post(`${API}/stock/produits/`, { data: donnees }), `produit ${l.d}`)
    lignes.push({
      produit: produit.id, designation: l.d, quantite: l.q, prix_unitaire: l.pu, remise: '0.00',
      taux_tva: l.tva, type_ligne: 'produit', ordre: i,
    })
  }
  // À CONFIRMER : le corps `atomic` (produit requis par ligne, echeancier en en-tête) n'a pas été exécuté ici
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    data: { lead: lead.id, taux_tva: '20.00', remise_globale: '10', echeancier: ECHEANCIER, lignes },
  }), 'devis réplique')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { data: { envoi: true } }), 'envoi du devis')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { data: { nom: 'Tijani Kharbachi' } }), 'acceptation du devis')
  const relu = await lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`), 'devis relu')
  expect(relu.statut, 'devis accepté').toBe('accepte')
  return { leadId: lead.id, devisId: devis.id, reference: relu.reference }
}

async function nettoyer(request, r) {
  if (!r) return
  await request.delete(`${API}/ventes/devis/${r.devisId}/`).catch(() => null)
  await request.delete(`${API}/crm/leads/${r.leadId}/`).catch(() => null)
}

/** Corps d'étape avec réplique fraîche + nettoyage (best-effort). */
async function avecReplique(page, testInfo, corps) {
  testInfo.setTimeout(240_000)
  let r = null
  try {
    r = await creerReplique(page.request)
    await corps(r)
  } finally {
    await nettoyer(page.request, r)
  }
}

/** GET devis/<id>/facturer/ (contrat ventes/contract_samples/devis_facturer.json `apercu_get`). */
async function apercu(request, devisId) {
  return lireJson(await request.get(`${API}/ventes/devis/${devisId}/facturer/`), 'aperçu facturer')
}

/** Acompte posé par l'API (SETUP des étapes dont le geste testé vient après) —
 *  corps de la requête : devis_facturer.json `requete`. */
async function acompteParApi(request, devisId, { montant = '15000.00', payer = true, emettre = true } = {}) {
  const data = { nature: 'acompte', montant_ttc: montant, emettre }
  if (payer) data.paiements = [{ montant, date_paiement: DATE_PAIEMENT, mode_paiement: 'virement', reference: 'VIR-1012' }]
  const rep = await lireJson(await request.post(`${API}/ventes/devis/${devisId}/facturer/`, { data }), 'acompte par API')
  return rep.facture
}

/** Détail d'une facture : GET ventes/factures/<id>/ (FactureSerializer `__all__` : statut, total_ttc,
 *  montant_ht, montant_tva, ventilation_tva, objet_vente, garanties, tva_par_taux). */
async function facture(request, id) {
  return lireJson(await request.get(`${API}/ventes/factures/${id}/`), `facture ${id}`)
}

/** Ventilation TVA lue de `ventilation_tva` (sinon `tva_par_taux`), clés `base_ht`|`base` + `montant`. */
function ventilation(f) {
  const brut = (Array.isArray(f.ventilation_tva) && f.ventilation_tva.length ? f.ventilation_tva : f.tva_par_taux) || []
  return Object.fromEntries(brut.map((b) => [Number(b.taux), { base: f2(b.base_ht ?? b.base), tva: f2(b.montant ?? b.tva) }]))
}

/** Fiche lead (route /crm/leads/:id : features/crm/module.config.jsx:126) → onglet Devis
 *  (ContextRail.jsx:159 testid lw-context-rail, :169 onglet « N devis ») → bouton
 *  « Facturer (facture complète) » (DevisTab.jsx:1011-1017, visible quand la porte est « libre »)
 *  → dialogue « Facturer — <ref> » (FacturerVenteDialog.jsx:416, form testid :245). */
async function ouvrirFacturer(page, r) {
  await page.goto(`/crm/leads/${r.leadId}`)
  await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  await page.getByRole('button', { name: /Facturer \(facture complète\)/ }).first().click()
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
  for (let i = 0; i < 20; i += 1) {
    const rep = await request.get(`${API}/ventes/factures/${id}/telecharger-pdf/`)
    if (rep.status() === 200) {
      const octets = await rep.body()
      expect(rep.headers()['content-type'] || '').toContain('application/pdf')
      expect(octets.subarray(0, 5).toString()).toBe('%PDF-')
      expect(octets.length).toBeGreaterThan(5_000)
      return { octets, texte: norm(await textePdf(octets)) }
    }
    await new Promise((ok) => { setTimeout(ok, 1500) })
  }
  throw new Error(`PDF de la facture ${id} jamais servi`)
}

etape('P1.1', plage(15, 23), async ({ page }, testInfo) => {
  // La réplique (lead + devis 11 lignes, remise 10 %, envoyé, accepté) porte le prix convenu 49 000,00
  // et rien n'est encore facturé : GET devis/<id>/facturer/ (devis_facturer.json `apercu_get`).
  await avecReplique(page, testInfo, async (r) => {
    const ap = await apercu(page.request, r.devisId)
    expect(f2(ap.vente.prix_convenu_ttc)).toBe('49000.00')
    expect(f2(ap.vente.reste_a_facturer_ttc)).toBe('49000.00')
    expect(f2(ap.vente.emis_ttc)).toBe('0.00')
    // Persistance : le lead s'ouvre, l'onglet Devis liste la réplique acceptée avec son bouton Facturer.
    await page.goto(`/crm/leads/${r.leadId}`)
    await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    await expect(page.getByTestId('lw-context-rail')).toContainText(r.reference)
    await expect(page.getByRole('button', { name: /Facturer \(facture complète\)/ }).first()).toBeVisible()
    await page.reload()
    expect(f2((await apercu(page.request, r.devisId)).vente.prix_convenu_ttc)).toBe('49000.00')
  })
})

etape('P1.2', ['VNT25', ...plage(26, 31), 'VNT44', 'VNT45'], async ({ page, suivi }, testInfo) => {
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

etape('P1.3', plage(33, 42), async ({ page, suivi }, testInfo) => {
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
    expect(texte).toMatch(/2279\.59/)
    // À CONFIRMER : mise en forme de la ventilation par taux (_chaine_totaux.html)
    for (const n of ['2644.90', '264.49', '10075.51', '2015.10']) expect(texte, `ventilation ${n}`).toContain(n)
    expect(texte).toMatch(/30\.61 % du prix convenu 49000\.00 MAD/)
    expect(texte).toContain('Garanties')
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

etape('P1.4', ['VNT45'], async ({ page, suivi }, testInfo) => {
  // Téléphone (375 px) : le dialogue s'ouvre en tiroir bas ; acompte tapé en POURCENTAGE (30 %) → 14 700,00.
  await avecReplique(page, testInfo, async (r) => {
    await page.setViewportSize({ width: 375, height: 812 })
    // À CONFIRMER : à 375 px l'onglet « Devis » du rail de contexte reste atteignable tel quel (ouvrirFacturer)
    const dialogue = await ouvrirFacturer(page, r)
    await expect(page.locator('[data-sheet-scroller]'), 'tiroir bas (ui/Sheet.jsx:168, side=bottom)').toBeVisible()
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
    suivi.verifie(5)
  })
})

etape('P1.5', [...plage(10, 14), 'VNT46'], async ({ page, suivi }, testInfo) => {
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
    const avoirs = listeDe(await lireJson(await page.request.get(`${API}/ventes/avoirs/?facture=${f.id}`), 'avoirs de la facture'))
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

etape('P1.6', ['VNT33', 'VNT34', 'VNT46'], async ({ page, suivi }, testInfo) => {
  // Refacturer l'acompte en BROUILLON (filigrane), puis supprimer ce brouillon ; la vente reste libre.
  await avecReplique(page, testInfo, async (r) => {
    // setup : acompte payé puis annulé (garder en avance) — corps de facture_annulation.json `requete_garder_en_avance`
    const payee = await acompteParApi(page.request, r.devisId)
    await lireJson(await page.request.post(`${API}/ventes/factures/${payee.id}/annuler/`, {
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
    expect((await page.request.get(`${API}/ventes/factures/${f.id}/`)).status()).toBe(404)
    expect(f2((await apercu(page.request, r.devisId)).vente.reste_a_facturer_ttc)).toBe('49000.00')
    suivi.verifie(5)
  })
})

etape('P1.7', ['VNT44', 'VNT45'], async ({ page, suivi }, testInfo) => {
  // Montant 60 000 > reste : l'erreur s'affiche SOUS le champ + bandeau « Corrigez : Montant », jamais un toast.
  await avecReplique(page, testInfo, async (r) => {
    // refus métier montant_depasse_reste (devis_facturer.json erreurs_400) : le SEUL 4xx excusé
    suivi.attendre(new RegExp(`/ventes/devis/${r.devisId}/facturer/$`), 400)
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
