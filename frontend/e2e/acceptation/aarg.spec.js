// AARG50 — spec d'acceptation en direct du parcours PA4 « Argent » (groupe AARG), jouée par
// l'ORCHESTRATEUR sur la pile locale (CLAUDE.md 3-bis, METHODE §C.4, `_format.md`). EMAIL_BACKEND
// console : aucun envoi réel ; le mail du beat est lu en mémoire (locmem, `executerDansDjango`).
//
// Étapes : P4.x rectificatifs (avoirs, ND), P5.x champs figés, P6.x échéance propre, P7.x relances
// et sorties client (PDF, UBL), P8.x portes de la chaîne (BC, consolidation, retour en brouillon,
// sortie de « Signé », chatter, logo, relevé).
//
// Données : chaque étape crée SES pièces par l'API réelle (produits au `prix_achat` repère pour
// l'oracle 7) ; seuls des états impossibles à poser par l'API (date passée, avertissement de vente)
// passent par le shell Django de la pile (E2E_DJANGO_EXEC).
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import {
  uniq, lireJson, textePdf, telephoneMobileUnique, executerDansDjango, connexionApi, assurerSessionPage, listeDe, PNG_1PX,
} from '../helpers.js'

const etape = groupe('AARG', ['AARG1', 'AARG2', 'AARG16', 'AARG19', 'AARG20', 'AARG23', 'AARG24', 'AARG25',
  'AARG26', 'AARG27', 'AARG28', 'AARG30', 'AARG32', 'AARG36', 'AARG37', 'AARG38', 'AARG39', 'AARG41', 'AARG47',
  'AARG48', 'AARG49', 'AARG53', 'AARG56', 'AARG58', 'AFAC104'])
const API = '/api/django'
// Le jeton de l'état partagé vit 30 min : reconnecter le contexte de l'étape si besoin.
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const T = { timeout: 120_000 }
const PRIX_ACHAT = '4321.09'
const AUJOURDHUI = () => aujourdHui()
const f2 = (v) => Number(v).toFixed(2)
const cents = (v) => Math.round(Number(v) * 100)
const plat = (s) => String(s).replace(/\s+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const contient = (texte, v) => plat(texte).includes(f2(v))

const sansPrixAchat = (texte, quoi) => {
  expect(plat(texte), `${quoi} : prix_achat jamais visible`).not.toContain(PRIX_ACHAT)
  expect(String(texte)).not.toMatch(/prix_achat|prix d'achat/i)
}

/** Lit la sortie JSON d'un bout de Python : le code imprime `@@<json>` sur une ligne. */
function shellJson(code) {
  const sortie = executerDansDjango(code)
  const ligne = sortie.split('\n').reverse().find((l) => l.startsWith('@@'))
  expect(ligne, `sortie du shell : ${sortie.slice(-400)}`).toBeTruthy()
  return JSON.parse(ligne.slice(2))
}

const email = () => `${uniq('aarg').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`

/** Devis accepté par l'API réelle. `lignes` = [[désignation, qté, P.U. HT, taux]]. */
async function vente(request, { lignes = [['Onduleur AARG', '1', '10000.00', '20.00']], client = null, lead = null, remise = '0', mail = null } = {}) {
  let leadId = lead
  if (!client && !leadId) {
    leadId = (await lireJson(await request.post(`${API}/crm/leads/`, {
      ...T, data: { nom: uniq('AARG Client'), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: mail || email() },
    }), 'lead')).id
  }
  const lignesDevis = []
  for (const [i, [d, q, pu, tva]] of lignes.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, {
      ...T, data: { nom: `${d} ${Date.now()}-${i}`, prix_vente: pu, prix_achat: PRIX_ACHAT },
    }), `produit ${d}`)
    lignesDevis.push({ produit: p.id, designation: d, quantite: q, prix_unitaire: pu, remise: '0.00', taux_tva: tva, type_ligne: 'produit', ordre: i })
  }
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: remise, lignes: lignesDevis, ...(leadId ? { lead: leadId } : { client }) },
  }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client AARG' } }), 'acceptation')
  const relu = await lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
  return { id: devis.id, leadId, client: relu.client, reference: relu.reference, ttc: relu.total_ttc }
}

const lireFacture = async (request, id) => lireJson(await request.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)

async function factureComplete(request, d) {
  const r = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  return lireFacture(request, r.facture_id)
}

async function bcConfirme(request, d) {
  const bc = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await request.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC')
  return bc
}

async function factureDeBc(request, d) {
  const bc = await bcConfirme(request, d)
  const brouillon = await lireJson(await request.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  await lireJson(await request.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
  return { bc, facture: await lireFacture(request, brouillon.id) }
}

async function payer(request, id, montant, reference = uniq('VIR-AARG')) {
  return lireJson(await request.post(`${API}/ventes/factures/${id}/enregistrer-paiement/`, {
    ...T, data: { montant: f2(montant), date_paiement: AUJOURDHUI(), mode: 'virement', reference },
  }), `paiement ${reference}`)
}

const facturePayee = async (request) => {
  const d = await vente(request)
  const f = await factureComplete(request, d)
  await payer(request, f.id, f.total_ttc)
  return { d, f: await lireFacture(request, f.id) }
}

async function pdf(request, chemin) {
  const rep = await request.get(`${API}/${chemin}`, T)
  expect(rep.status(), `${chemin} → ${(await rep.text().catch(() => '')).slice(0, 300)}`).toBe(200)
  expect(rep.headers()['content-type'] || '').toContain('application/pdf')
  return textePdf(await rep.body())
}

/** Ligne de la facture dans /ventes/factures. */
async function ligneFacture(page, f) {
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(f.reference)
  const ligne = page.locator(`#facture-row-${f.id}`).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  return ligne
}

/** Refus attendu : statut + (optionnel) motif, puis renvoie le corps. */
async function refus(rep, statut, motif = null) {
  const texte = await rep.text()
  expect(rep.status(), texte.slice(0, 400)).toBe(statut)
  if (motif) expect(texte).toMatch(motif)
  try { return JSON.parse(texte) } catch { return texte }
}

const avanceClient = async (request, clientId) => listeDe(await lireJson(await request.get(`${API}/ventes/paiements/avances-non-affectees/?client=${clientId}`, T), 'avances'))

/** Session API distincte (autre compte du seed démo). */
async function sessionDe(testInfo, username, password = 'Demo@2026!') {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username, password })
  return ctx
}

// ── P4.1 — AARG1 : avoir au-delà du reste dû d'une facture payée ⇒ avance client, relevé ─────
etape('P4.1', ['AARG1'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const { d, f } = await facturePayee(r)
  expect(cents(f.total_ttc)).toBe(1200000)
  const ligne = f.lignes[0]
  const avoir = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, {
    ...T, data: { motif: 'AARG1', type: 'correction', lignes: [{ produit: ligne.produit, designation: ligne.designation, quantite: '0.2', prix_unitaire: ligne.prix_unitaire, taux_tva: '20.00' }] },
  }), 'avoir 2 000 HT')
  expect(f2(avoir.total_ttc)).toBe('2400.00')
  const apres = await lireFacture(r, f.id)
  expect(f2(apres.montant_paye), 'payé 9 600').toBe('9600.00')
  expect(f2(apres.montant_du), 'dû 0').toBe('0.00')
  const paiements = await lireJson(await r.get(`${API}/ventes/factures/${f.id}/paiements/`, T), 'paiements')
  const trop = listeDe(paiements).find((p) => Number(p.montant) < 0)
  expect(trop, 'paiement négatif « Trop-perçu »').toBeTruthy()
  expect(f2(trop.montant)).toBe('-2400.00')
  expect(JSON.stringify(trop)).toMatch(/Trop-perçu après avoir/)
  const releve = await lireJson(await r.get(`${API}/ventes/clients/${d.client}/releve/`, T), 'relevé')
  expect(releve.avances.map((a) => f2(a.montant ?? a.reste ?? a)), 'relevé : avance 2 400').toContain('2400.00')
  expect(f2(releve.totaux.solde), 'solde −2 400').toBe('-2400.00')
  const texte = await pdf(r, `ventes/clients/${d.client}/releve-pdf/`)
  expect(contient(texte, 2400), 'relevé PDF : avance').toBeTruthy()
  sansPrixAchat(texte, 'relevé PDF')
  // Facture NON payée : aucune avance.
  const d2 = await vente(r)
  const f2n = await factureComplete(r, d2)
  const l2 = f2n.lignes[0]
  await lireJson(await r.post(`${API}/ventes/factures/${f2n.id}/creer-avoir/`, {
    ...T, data: { motif: 'AARG1 non payée', type: 'correction', lignes: [{ produit: l2.produit, designation: l2.designation, quantite: '0.2', prix_unitaire: l2.prix_unitaire, taux_tva: '20.00' }] },
  }), 'avoir facture non payée')
  expect(await avanceClient(r, d2.client), 'non payée : aucune avance').toEqual([])
  // Retour client : même chemin.
  const { d: d3, f: f3 } = await facturePayee(r)
  const l3 = f3.lignes[0]
  await lireJson(await r.post(`${API}/ventes/factures/${f3.id}/retour-client/`, {
    ...T, data: { motif: 'AARG1 retour', lignes: [{ produit: l3.produit, quantite: '1' }], restocker: false },
  }), 'retour client')
  const f3r = await lireFacture(r, f3.id)
  expect(f2(f3r.montant_du), 'retour total : dû 0').toBe('0.00')
  const a3 = await avanceClient(r, d3.client)
  expect(a3.length, 'retour : avance créée').toBeGreaterThan(0)
})

// ── P4.2 — AARG2 + AARG37 : annuler l'avoir miroir à l'écran, statut « Annulé » au PDF ───────
etape('P4.2', ['AARG2', 'AARG37'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const { d, f } = await facturePayee(r)
  const annulation = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/annuler/`, {
    ...T, data: { motif: 'AARG2', acompte: { action: 'garder_en_avance' } },
  }), 'annulation garder_en_avance')
  const annulee = await lireFacture(r, f.id)
  expect(annulee.statut).toBe('annulee')
  const avoirId = annulation.avoir?.id
  expect(avoirId, 'avoir miroir').toBeTruthy()
  const avoir = await lireJson(await r.get(`${API}/ventes/avoirs/${avoirId}/`, T), 'avoir miroir')
  // PDF déjà généré avant annulation : actif.
  const avantPdf = await pdf(r, `ventes/avoirs/${avoirId}/telecharger-pdf/`)
  expect(avantPdf, 'PDF avant annulation : pas « Annulé »').not.toMatch(/Statut\s*Annulé/i)
  await page.goto('/ventes/avoirs')
  const rangee = page.locator('tr').filter({ hasText: avoir.reference }).first()
  await expect(rangee).toBeVisible({ timeout: 60_000 })
  await rangee.getByRole('button', { name: 'Annuler', exact: true }).click()
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/ventes/avoirs/${avoirId}/annuler/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('alertdialog').getByRole('button', { name: "Annuler l'avoir" }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(200)
  const apres = await lireFacture(r, f.id)
  expect(f2(apres.montant_paye), 'payé revenu à 12 000').toBe('12000.00')
  expect(apres.statut, 'statut recalculé : payée').toBe('payee')
  expect(await avanceClient(r, d.client), 'avance 0').toEqual([])
  // AARG37 — PDF régénéré, statut Annulé ; rejeu : aucun rendu ni événement de plus.
  const apresPdf = await pdf(r, `ventes/avoirs/${avoirId}/telecharger-pdf/`)
  expect(apresPdf).toMatch(/Statut\s*Annulé/i)
  const avoirRelu = await lireJson(await r.get(`${API}/ventes/avoirs/${avoirId}/`, T), 'avoir relu')
  expect(avoirRelu.annule ?? avoirRelu.annulee ?? avoirRelu.statut === 'annulee').toBeTruthy()
  const hist = async () => listeDe(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/historique/`, T), 'historique')).length
  const n = await hist()
  const rejeu = await r.post(`${API}/ventes/avoirs/${avoirId}/annuler/`, { ...T, data: {} })
  expect(rejeu.status(), await rejeu.text()).toBeLessThan(500)
  expect(await hist(), 'rejeu : aucun événement de plus').toBe(n)
  await page.reload()
  await expect(page.locator('tr').filter({ hasText: avoir.reference }).first()).toBeVisible({ timeout: 60_000 })
})

// ── P4.3 — AARG2 : l'avance a servi ailleurs ⇒ 409, rien d'écrit ─────────────────────────────
etape('P4.3', ['AARG2'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const { d, f } = await facturePayee(r)
  const annulation = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/annuler/`, {
    ...T, data: { motif: 'AARG2 ventilée', acompte: { action: 'garder_en_avance' } },
  }), 'annulation')
  const avances = await avanceClient(r, d.client)
  expect(avances.length).toBeGreaterThan(0)
  // Autre facture du même client : l'avance y est ventilée.
  const d2 = await vente(r, { client: d.client })
  const f2b = await factureComplete(r, d2)
  await lireJson(await r.post(`${API}/ventes/paiements/${avances[0].id}/ventiler/`, {
    ...T, data: { facture: f2b.id, montant: f2(avances[0].reste ?? avances[0].montant) },
  }), 'ventilation')
  const avant = await lireFacture(r, f.id)
  await refus(await r.post(`${API}/ventes/avoirs/${annulation.avoir.id}/annuler/`, { ...T, data: {} }), 409, /avance issue de cette annulation/i)
  const apres = await lireFacture(r, f.id)
  expect(apres.statut).toBe(avant.statut)
  expect(apres.montant_paye).toBe(avant.montant_paye)
})

// ── P4.4 — AARG36 : base HT par taux sur l'avoir et la ND, date de la facture d'origine ──────
etape('P4.4', ['AARG36'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r, { lignes: [['Panneau AARG36', '1', '1000.00', '10.00'], ['Onduleur AARG36', '1', '1000.00', '20.00']] })
  const f = await factureComplete(r, d)
  const nd = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-note-debit/`, {
    ...T, data: { motif: 'AARG36 ventilée', lignes: [
      { produit: f.lignes[0].produit, designation: 'Frais 10', quantite: '1', prix_unitaire: '1000.00', taux_tva: '10.00' },
      { produit: f.lignes[1].produit, designation: 'Frais 20', quantite: '1', prix_unitaire: '1000.00', taux_tva: '20.00' }] },
  }), 'note de débit ventilée')
  const avoir = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, {
    ...T, data: { motif: 'AARG36 total', type: 'correction' },
  }), 'avoir total')
  const texteA = await pdf(r, `ventes/avoirs/${avoir.id}/telecharger-pdf/`)
  expect(plat(texteA), 'avoir : base 10 %').toMatch(/BaseHT\(10\.00%\)1000\.00/)
  expect(plat(texteA), 'avoir : base 20 %').toMatch(/BaseHT\(20\.00%\)1000\.00/)
  const dateFr = new Date(`${f.date_emission}T12:00:00`).toLocaleDateString('fr-FR')
  expect(texteA, "avoir : date de la facture d'origine").toContain(dateFr)
  sansPrixAchat(texteA, 'PDF avoir')
  const texteN = await pdf(r, `ventes/notes-debit/${nd.id}/telecharger-pdf/`)
  expect(plat(texteN), 'ND : base 10 %').toMatch(/BaseHT\(10\.00%\)1000\.00/)
  expect(plat(texteN), 'ND : base 20 %').toMatch(/BaseHT\(20\.00%\)1000\.00/)
  // Écran : le PDF de l'avoir s'ouvre depuis AvoirsPage.
  await page.goto('/ventes/avoirs')
  const rangee = page.locator('tr').filter({ hasText: avoir.reference }).first()
  await expect(rangee).toBeVisible({ timeout: 60_000 })
  const [repPdf] = await Promise.all([
    page.waitForResponse((x) => new RegExp(`/ventes/avoirs/${avoir.id}/telecharger-pdf/$`).test(new URL(x.url()).pathname), T),
    rangee.getByRole('button', { name: /PDF/ }).click(),
  ])
  expect(repPdf.status()).toBe(200)
})

// ── P4.5 — AARG38 : lignes d'avoir bornées, écran « Avoir partiel » ──────────────────────────
etape('P4.5', ['AARG38'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r, { lignes: [['Panneau AARG38', '2', '1000.00', '20.00']] })
  const f = await factureComplete(r, d)
  const l = f.lignes[0]
  const poster = (ligne) => r.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, { ...T, data: { motif: 'AARG38', type: 'correction', lignes: [ligne] } })
  const base = { produit: l.produit, designation: 'Panneau', quantite: '2', prix_unitaire: '1000', taux_tva: '20' }
  await refus(await poster({ ...base, quantite: '3' }), 400, /quantité créditée supérieure à la quantité facturée restante \(2/)
  await refus(await poster({ ...base, quantite: '1', taux_tva: '10' }), 400, /taux de TVA absent de la facture/)
  await refus(await poster({ ...base, quantite: '1', prix_unitaire: '1200' }), 400, /Ligne 1/)
  expect(f2((await lireFacture(r, f.id)).avoirs_total || 0), 'rien écrit').toBe('0.00')
  // Écran : un avoir partiel d'une quantité.
  const ligne = await ligneFacture(page, f)
  await ligne.getByRole('button', { name: 'Avoir', exact: true }).click()
  const dialogue = page.getByRole('dialog').filter({ hasText: `Créer un avoir — ${f.reference}` })
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  await dialogue.locator('input[type="number"]').first().fill('1')
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/creer-avoir\/$/.test(new URL(x.url()).pathname), T),
    dialogue.getByRole('button', { name: 'Avoir partiel' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(201)
  const apres = await lireFacture(r, f.id)
  expect(cents(apres.avoirs_total), 'avoir partiel 1 000 HT = 1 200 TTC').toBe(120000)
  await page.reload()
  await expect(page.locator(`#facture-row-${f.id}`).first()).toBeVisible({ timeout: 60_000 })
  // Facture sans ligne produit (acompte) : ligne libre au plafond, au taux porté (201) ; autre taux : 400.
  const dA = await vente(r)
  const acompte = await lireJson(await r.post(`${API}/ventes/devis/${dA.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'acompte émis')
  const fa = await lireFacture(r, acompte.facture.id)
  const libre = { produit: null, designation: 'Acompte', quantite: '1', prix_unitaire: f2(fa.total_ht), taux_tva: '20' }
  await refus(await r.post(`${API}/ventes/factures/${fa.id}/creer-avoir/`, { ...T, data: { motif: 'AARG38 libre', type: 'correction', lignes: [{ ...libre, taux_tva: '10' }] } }), 400, /taux de TVA absent/)
  await lireJson(await r.post(`${API}/ventes/factures/${fa.id}/creer-avoir/`, { ...T, data: { motif: 'AARG38 libre', type: 'correction', lignes: [libre] } }), 'ligne libre au plafond')
})

// ── P4.6 — AARG39 : contre-passation = porte unique d'annulation ────────────────────────────
etape('P4.6', ['AARG39'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f = await factureComplete(r, await vente(r))
  const avoir = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, {
    ...T, data: { mode: 'contre_passation', motif: 'Erreur' },
  }), 'contre-passation')
  const relue = await lireFacture(r, f.id)
  expect(relue.statut).toBe('annulee')
  const avoirs = listeDe(await lireJson(await r.get(`${API}/ventes/avoirs/?facture=${f.id}`, T), 'avoirs de la facture'))
  expect(avoirs.map((a) => a.id), "réponse = l'avoir créé par annuler_facture, un seul").toEqual([avoir.id])
  const hist = JSON.stringify(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/historique/`, T), 'historique'))
  expect(hist, 'FactureActivity lie les pièces').toContain(avoir.reference)
  // Facture payée : refus d'état (écart retenu 409 `directive_acompte_requise`, contrat facture_annulation.json).
  const f2p = await factureComplete(r, await vente(r))
  await payer(r, f2p.id, 200)
  const corps = await refus(await r.post(`${API}/ventes/factures/${f2p.id}/creer-avoir/`, {
    ...T, data: { mode: 'contre_passation', motif: 'Erreur' },
  }), 409)
  expect(corps.code).toBe('directive_acompte_requise')
  expect((await lireFacture(r, f2p.id)).statut, 'rien annulé').not.toBe('annulee')
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(f.reference)
  await expect(page.locator(`#facture-row-${f.id}`).first()).toBeVisible({ timeout: 60_000 })
})

// ── P5.1 — AARG28 : devis / bon_commande figés sur une facture émise ────────────────────────
etape('P5.1', ['AARG28'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r)
  const acompte = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, {
    ...T, data: { nature: 'acompte', emettre: true },
  }), 'acompte émis')
  const idA = acompte.facture.id
  await refus(await r.patch(`${API}/ventes/factures/${idA}/`, { ...T, data: { devis: null } }), 409, /figé après émission/)
  expect((await lireFacture(r, idA)).devis, 'rien écrit').toBe(d.id)
  const dBc = await vente(r)
  const { facture } = await factureDeBc(r, dBc)
  await refus(await r.patch(`${API}/ventes/factures/${facture.id}/`, { ...T, data: { bon_commande: null } }), 409, /figé après émission/)
  // Brouillon : 200.
  const dB = await vente(r)
  const bc = await bcConfirme(r, dB)
  const brouillon = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'brouillon')
  const rep = await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { bon_commande: null } })
  expect(rep.status(), await rep.text()).toBe(200)
})

// ── P5.2 — AARG49 : libellé et date de livraison figés, formulaire d'une émise ──────────────
etape('P5.2', ['AARG49'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r)
  const bc = await bcConfirme(r, d)
  const brouillon = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'brouillon')
  const ok = await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { libelle: 'Installation 6 kWc', date_livraison: '2026-10-20' } })
  expect(ok.status(), `brouillon : ${await ok.text()}`).toBe(200)
  await lireJson(await r.post(`${API}/ventes/factures/${brouillon.id}/emettre/`, { ...T, data: {} }), 'émission')
  await refus(await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { date_livraison: '2026-11-01' } }), 409, /figé après émission/)
  await refus(await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { libelle: 'Autre' } }), 409, /figé après émission/)
  const relue = await lireFacture(r, brouillon.id)
  expect(relue.libelle).toBe('Installation 6 kWc')
  expect(relue.date_livraison).toBe('2026-10-20')
  // PATCH qui renvoie les valeurs relues : 200.
  const meme = await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { libelle: relue.libelle, date_livraison: relue.date_livraison } })
  expect(meme.status(), await meme.text()).toBe(200)
  // Le formulaire d'une émise (FactureForm) : s'ouvre et s'enregistre (PUT/PATCH des valeurs relues : pas de 409).
  await page.goto(`/ventes/factures?id=${relue.id}`)
  const form = page.getByRole('dialog').filter({ hasText: `Éditer — ${relue.reference}` })
  await expect(form).toBeVisible({ timeout: 30_000 })
  const [repForm] = await Promise.all([
    page.waitForResponse((x) => ['PUT', 'PATCH'].includes(x.request().method()) && new RegExp(`/ventes/factures/${relue.id}/$`).test(new URL(x.url()).pathname), T),
    form.locator('button[type="submit"]').click(),
  ])
  expect(repForm.status(), await repForm.text()).toBe(200)
  const apresForm = await lireFacture(r, relue.id)
  expect(apresForm.libelle, 'libellé intact').toBe('Installation 6 kWc')
  expect(apresForm.date_livraison, 'date intacte').toBe('2026-10-20')
})

// ── P5.3 — AARG56 : statut dérivé de l'échéance appliquée ; échéance non effaçable ──────────
etape('P5.3', ['AARG56'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f = await factureComplete(r, await vente(r))
  await payer(r, f.id, 3000)
  const idP = listeDe(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/paiements/`, T), 'paiements'))[0].id
  shellJson(`from apps.ventes.models import Facture; from django.utils import timezone; from datetime import timedelta; import json; Facture.objects.filter(pk=${f.id}).update(date_emission=(timezone.localdate()-timedelta(days=45)), date_echeance=None); print('@@'+json.dumps(1))`)
  await lireJson(await r.post(`${API}/ventes/paiements/${idP}/rejeter/`, { ...T, data: { motif: 'AARG56 rejet' } }), 'rejet')
  expect((await lireFacture(r, f.id)).statut, 'statut comme le beat').toBe('en_retard')
  const f2e = await factureComplete(r, await vente(r))
  expect(f2e.date_echeance, 'facture datée').toBeTruthy()
  await refus(await r.patch(`${API}/ventes/factures/${f2e.id}/`, { ...T, data: { date_echeance: null } }), 409, /échéance d'une facture émise ne s'efface pas/)
  const dB = await vente(r)
  const bc = await bcConfirme(r, dB)
  const brouillon = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'brouillon')
  const ok = await r.patch(`${API}/ventes/factures/${brouillon.id}/`, { ...T, data: { date_echeance: null } })
  expect(ok.status(), await ok.text()).toBe(200)
})

// ── P6.1 — AARG53 : la note de débit a sa propre échéance ; /ventes/relances ────────────────
etape('P6.1', ['AARG53'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f0 = await factureComplete(r, await vente(r, { lignes: [['Prestation AARG53', '1', '1000.00', '20.00']] }))
  await payer(r, f0.id, f0.total_ttc)
  shellJson(`from apps.ventes.models import Facture; from django.utils import timezone; from datetime import timedelta; import json; d=timezone.localdate()-timedelta(days=120); Facture.objects.filter(pk=${f0.id}).update(date_emission=d, date_echeance=d+timedelta(days=30)); print('@@'+json.dumps(1))`)
  const nd = await lireJson(await r.post(`${API}/ventes/factures/${f0.id}/creer-note-debit/`, {
    ...T, data: { motif: 'AARG53 frais', montant: '416.67', taux_tva: '20.00' },
  }), 'note de débit')
  let f = await lireFacture(r, f0.id)
  expect(f.statut, 'ND du jour : émise, pas en retard').toBe('emise')
  expect(Number(f.jours_retard || 0), 'jours_retard 0').toBe(0)
  await page.goto('/ventes/relances')
  await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 60_000 })
  // Une relance n'apparaît pas (rien d'échu) pour cette facture.
  await expect(page.getByText(f0.reference, { exact: false })).toHaveCount(0)
  // À J+31 de la ND : en retard, 1 jour.
  shellJson(`from apps.ventes.models import NoteDebit, Facture; from django.utils import timezone; from datetime import timedelta; from apps.ventes.scheduled import check_overdue_factures; import json; d=timezone.localdate()-timedelta(days=31); NoteDebit.objects.filter(pk=${nd.id}).update(date_emission=d); check_overdue_factures(); print('@@'+json.dumps(1))`)
  f = await lireFacture(r, f0.id)
  expect(f.statut, 'J+31 : en retard').toBe('en_retard')
  expect(Number(f.jours_retard), '1 jour de retard').toBe(1)
  await page.goto('/ventes/relances')
  await expect(page.getByText(f0.reference, { exact: false }).first()).toBeVisible({ timeout: 60_000 })
})

// ── P7.1 — AARG24 + AARG25 + AARG58 : mail du beat, aperçu « Relancer » ─────────────────────
etape('P7.1', ['AARG24', 'AARG25', 'AARG58'], async ({ page, testInfo }) => {
  testInfo.setTimeout(420_000)
  const r = page.request
  const mail = email()
  const f0 = await factureComplete(r, await vente(r, { lignes: [['Prestation AARG24', '1', '1000.00', '20.00']], mail }))
  await payer(r, f0.id, 500)
  shellJson(`from apps.ventes.models import Facture; from django.utils import timezone; from datetime import date; import json; Facture.objects.filter(pk=${f0.id}).update(date_echeance=date(2026,10,1), prochaine_relance=timezone.localdate()); from apps.ventes.models import FollowupLevel; from apps.ventes.recouvrement import NIVEAUX_RELANCE_DEFAUT; [FollowupLevel.objects.filter(company_id=1, ordre=o).update(message=m) for o, _n, _d, m in NIVEAUX_RELANCE_DEFAUT]; print('@@'+json.dumps(1))`)
  // Le beat réel, boîte en mémoire : aucun envoi réel. Seuls les mails de CETTE facture sont lus.
  const res = shellJson(`
import json
from django.core import mail
from django.test.utils import override_settings
from apps.ventes.scheduled import relance_reminders
from apps.ventes.models import Facture, EmailLog
ref = Facture.objects.get(pk=${f0.id}).reference
Facture.objects.exclude(pk=${f0.id}).filter(prochaine_relance__isnull=False).update(prochaine_relance=None)
with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
    mail.outbox = []
    relance_reminders()
    m = [x for x in mail.outbox if ref in (x.subject + str(x.body))]
print('@@' + json.dumps({'ref': ref, 'n': len(m), 'corps': [str(x.body) for x in m], 'html': [str(a[0])[:60000] for x in m for a in getattr(x, 'alternatives', [])], 'pj': [a[0] for x in m for a in x.attachments], 'sujet': [x.subject for x in m], 'logs': list(EmailLog.objects.filter(facture_id=${f0.id}).values_list('statut', flat=True))}))
`.trim())
  expect(res.n, 'une relance automatique partie').toBe(1)
  const corps = res.corps[0]
  expect(corps, 'cite la référence').toContain(res.ref)
  expect(plat(corps), 'cite 700,00').toContain('700.00')
  expect(corps, "cite l'échéance").toContain('01/10/2026')
  expect(corps, 'pas de « ci-dessus »').not.toMatch(/ci-dessus/i)
  expect((corps.match(/Bonjour/g) || []).length, 'AARG25 : une seule salutation').toBeLessThanOrEqual(1)
  // AARG58 — écart retenu à la livraison : le nom reste `<référence>.pdf`, celui de la relance manuelle.
  expect(res.pj, 'AARG58 : facture en pièce jointe').toContain(`${res.ref}.pdf`)
  expect(res.logs, 'EmailLog envoyé').toContain('envoye')
  // Aperçu « Relancer » (RelancesPage) : objet + message qui disent ce qui est dû.
  const ap = await lireJson(await r.get(`${API}/ventes/factures/${f0.id}/relance-apercu/`, T), 'aperçu')
  const texteAp = JSON.stringify(ap)
  expect((texteAp.match(/Bonjour/g) || []).length, 'aperçu : une seule salutation').toBeLessThanOrEqual(1)
  expect(texteAp).not.toMatch(/ci-dessus/i)
  await page.goto('/ventes/relances')
  await page.locator('tr, [role="row"], article, li').filter({ hasText: res.ref }).first().getByRole('button', { name: 'Relancer' }).click()
  const dlg = page.getByRole('dialog').filter({ hasText: res.ref })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await expect(dlg).toContainText('700,00', { timeout: 30_000 })
  await page.keyboard.press('Escape')
})

// ── P7.2 — AARG27 : identité de l'acheteur figée à l'émission (PDF + UBL) ───────────────────
etape('P7.2', ['AARG27'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const nomX = uniq('X SARL')
  const iceA = `00${String(Date.now()).slice(-13)}`
  const iceB = `01${String(Date.now()).slice(-13)}`
  const client = await lireJson(await r.post(`${API}/crm/clients/`, {
    ...T, data: { nom: nomX, prenom: '', type_client: 'entreprise', email: email(), telephone: telephoneMobileUnique(), ice: iceA, adresse: '12 rue AARG, Casablanca' },
  }), 'client X')
  const d = await vente(r, { client: client.id })
  const f = await factureComplete(r, d)
  const nomY = uniq('Y SARL')
  await lireJson(await r.patch(`${API}/crm/clients/${client.id}/`, { ...T, data: { nom: nomY, ice: iceB } }), 'PATCH client')
  const texte = await pdf(r, `ventes/factures/${f.id}/telecharger-pdf/`)
  expect(plat(texte), 'PDF : X').toContain(plat(nomX))
  expect(texte, 'PDF : ICE A').toContain(iceA)
  expect(texte, 'PDF : pas ICE B').not.toContain(iceB)
  sansPrixAchat(texte, 'PDF facture')
  const ubl = await r.get(`${API}/ventes/factures/${f.id}/ubl/`, T)
  expect(ubl.status(), 'ubl').toBe(200)
  const xml = await ubl.text()
  expect(xml, 'UBL : ICE A').toContain(iceA)
  expect(xml, 'UBL : pas ICE B').not.toContain(iceB)
  // Une facture émise après le PATCH porte Y / B.
  const f2a = await factureComplete(r, await vente(r, { client: client.id }))
  const texte2 = await pdf(r, `ventes/factures/${f2a.id}/telecharger-pdf/`)
  expect(plat(texte2), 'PDF nouvelle : Y').toContain(plat(nomY))
  expect(texte2, 'PDF nouvelle : ICE B').toContain(iceB)
  // Écran : la ligne de la facture porte toujours l'émission.
  await ligneFacture(page, f)
})

/** Allume l'export DGI de la société le temps d'un corps. */
async function avecDgi(r, corps) {
  const profil = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
  const avant = profil.dgi_export_actif
  await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { dgi_export_actif: true } }), 'DGI allumé')
  try { await corps() } finally {
    await lireJson(await r.patch(`${API}/parametres/update/`, { ...T, data: { dgi_export_actif: avant } }), 'DGI rétabli')
  }
}

// ── P7.3 — AARG20 : un seul constructeur UBL, remise comprise ; écran « Export DGI » ────────
etape('P7.3', ['AARG20'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  // HT 10 000, remise 10 % : le total suit le palier d'arrondi commercial (ARRONDI-100), la chaîne se lit sur l'API.
  const f = await factureComplete(r, await vente(r, { lignes: [['Prestation AARG20', '1', '10000.00', '20.00']], remise: '10' }))
  const net = Number(f.total_ht)
  const remiseHt = 10000 - net
  expect(remiseHt, 'une remise sur la facture').toBeGreaterThan(0)
  await avecDgi(r, async () => {
    const ubl = await (await r.get(`${API}/ventes/factures/${f.id}/ubl/`, T)).text()
    const dgi = await r.get(`${API}/ventes/factures/${f.id}/dgi-export/`, T)
    expect(dgi.status(), 'dgi-export').toBe(200)
    const xml = await dgi.text()
    const sansHorodatage = (s) => s.replace(/<!--[^]*?-->/g, '').replace(/\s+/g, ' ')
    expect(sansHorodatage(ubl), 'aperçu = export (hors commentaire d\'aperçu)').toBe(sansHorodatage(xml))
    expect(xml).toMatch(/cac:AllowanceCharge/)
    expect(xml).toMatch(/ChargeIndicator>false</)
    expect(xml).toMatch(new RegExp(`AllowanceCharge>[^]*?<cbc:Amount[^>]*>${f2(remiseHt)}<`))
    expect(xml, 'Σ lignes').toMatch(/LineExtensionAmount[^>]*>10000\.00</)
    expect(xml, 'Σ lignes − remise = en-tête').toMatch(new RegExp(`TaxExclusiveAmount[^>]*>${f2(net)}<`))
    expect(xml, 'TVA de la facture').toMatch(new RegExp(`TaxAmount[^>]*>${f2(f.total_tva)}<`))
    const ligne = await ligneFacture(page, f)
    await ligne.getByRole('button', { name: /Plus d.actions|Actions/i }).first().click()
    const [rep] = await Promise.all([
      page.waitForResponse((x) => /\/dgi-export\/$/.test(new URL(x.url()).pathname), T),
      page.getByRole('menuitem', { name: /Export DGI/ }).click(),
    ])
    expect(rep.status()).toBe(200)
  })
})

// ── P7.4 — AARG41 : UBL 381 / 383, BillingReference ; interrupteur éteint 404 ───────────────
etape('P7.4', ['AARG41'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f = await factureComplete(r, await vente(r, { lignes: [['Prestation AARG41', '1', '1000.00', '20.00']] }))
  const nd = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-note-debit/`, { ...T, data: { motif: 'AARG41', montant: '100.00', taux_tva: '20.00' } }), 'ND')
  const avoir = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/creer-avoir/`, { ...T, data: { motif: 'AARG41 total', type: 'correction' } }), 'avoir')
  const profil = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
  if (!profil.dgi_export_actif) {
    await refus(await r.get(`${API}/ventes/avoirs/${avoir.id}/dgi-export/`, T), 404)
    await refus(await r.get(`${API}/ventes/notes-debit/${nd.id}/dgi-export/`, T), 404)
  }
  await avecDgi(r, async () => {
    const a = await r.get(`${API}/ventes/avoirs/${avoir.id}/dgi-export/`, T)
    expect(a.status(), 'avoir dgi-export').toBe(200)
    const xa = await a.text()
    expect(xa).toMatch(/InvoiceTypeCode[^>]*>381</)
    expect(xa).toMatch(new RegExp(`BillingReference>[^]*?InvoiceDocumentReference>[^]*?<cbc:ID>${f.reference}<`))
    expect(xa).toContain(f2(avoir.total_ttc))
    const n = await r.get(`${API}/ventes/notes-debit/${nd.id}/dgi-export/`, T)
    expect(n.status(), 'ND dgi-export').toBe(200)
    const xn = await n.text()
    expect(xn).toMatch(/InvoiceTypeCode[^>]*>383</)
    expect(xn).toMatch(new RegExp(`<cbc:ID>${f.reference}<`))
  })
})

// ── P8.1 — AARG16 : consolider à l'écran retire le brouillon d'acompte automatique ──────────
etape('P8.1', ['AARG16'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const dA = await vente(r, { lignes: [['Prestation A AARG16', '1', '1000.00', '20.00']] })
  const dB = await vente(r, { lignes: [['Prestation B AARG16', '1', '1000.00', '20.00']], client: dA.client })
  const avant = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${dA.id}`, T), 'factures de A'))
  const brouillonAuto = avant.find((x) => x.statut === 'brouillon')
  await page.goto('/ventes/factures')
  await page.getByRole('button', { name: 'Consolider des devis' }).click()
  const dlg = page.getByRole('dialog').filter({ hasText: 'Consolider des devis' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.getByRole('checkbox', { name: `Sélectionner le devis ${dA.reference}` }).click()
  await dlg.getByRole('checkbox', { name: `Sélectionner le devis ${dB.reference}` }).click()
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/factures\/consolider\/$/.test(new URL(x.url()).pathname), T),
    dlg.getByRole('button', { name: /Consolider \(2\)/ }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(201)
  const conso = await rep.json()
  const f = await lireFacture(r, conso.id)
  expect(f.statut).toBe('emise')
  expect(cents(f.total_ttc)).toBe(240000)
  if (brouillonAuto) {
    const b = await lireFacture(r, brouillonAuto.id)
    expect(b.statut, 'brouillon d\'acompte annulé').toBe('annulee')
    const histB = JSON.stringify(await lireJson(await r.get(`${API}/ventes/factures/${brouillonAuto.id}/historique/`, T), 'historique du brouillon'))
    expect(histB, 'motif du retrait').toMatch(/Remplacé par la facture consolidée/)
  }
  const apres = shellJson(`from apps.ventes.selectors_facturation import factures_de_la_vente; from apps.ventes.models import Devis; import json; d=Devis.objects.get(pk=${dA.id}); print('@@'+json.dumps([x.id for x in factures_de_la_vente(d) if x.statut!='annulee']))`)
  expect(apres, 'seule la consolidée reste active').toEqual([conso.id])
  await ligneFacture(page, f)
})

// ── P8.2 — AARG19 : BC sur devis non accepté / autre client ⇒ 409 ; témoin à l'écran ────────
etape('P8.2', ['AARG19'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const dX = await vente(r)
  const dY = await vente(r)
  const brouillonY = await lireJson(await r.post(`${API}/ventes/devis/`, { ...T, data: { client: dY.client, taux_tva: '20.00' } }), 'devis brouillon de Y')
  await refus(await r.post(`${API}/ventes/bons-commande/`, { ...T, data: { client: dX.client, devis: brouillonY.id } }), 409, /devis doit être accepté/)
  await refus(await r.post(`${API}/ventes/bons-commande/`, { ...T, data: { client: dX.client, devis: dY.id } }), 409, /client du bon de commande doit être celui du devis/)
  const t = await r.post(`${API}/ventes/bons-commande/`, { ...T, data: { client: dX.client, devis: dX.id } })
  expect(t.status(), `témoin : ${await t.text()}`).toBe(201)
  const bcT = await t.json()
  await refus(await r.patch(`${API}/ventes/bons-commande/${bcT.id}/`, { ...T, data: { devis: dY.id } }), 409, /client du bon de commande doit être celui du devis/)
  await page.goto('/ventes/bons-commande')
  await expect(page.getByRole('button', { name: /Nouveau BC/ })).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: /Nouveau BC/ }).click()
  await expect(page.getByRole('dialog').filter({ hasText: 'Nouveau bon de commande' })).toBeVisible({ timeout: 30_000 })
  await page.keyboard.press('Escape')
})

// ── P8.3 — AARG30 : BC annulé, facture de BC annulée ne bloquent plus la chaîne ─────────────
etape('P8.3', ['AARG30'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r)
  const bc1 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC1')
  await refus(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 409)
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc1.id}/annuler/`, { ...T, data: {} }), 'annuler BC1')
  const bc2 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC2 après annulation')
  expect(bc2.id).not.toBe(bc1.id)
  const bc1r = await lireJson(await r.get(`${API}/ventes/bons-commande/${bc1.id}/`, T), 'BC1 relu')
  expect(bc1r.reference, 'BC1 garde sa référence').toBe(bc1.reference)
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc2.id}/confirmer/`, { ...T, data: {} }), 'confirmer BC2')
  const f1 = await lireJson(await r.post(`${API}/ventes/bons-commande/${bc2.id}/creer-facture/`, { ...T, data: {} }), 'F1')
  await refus(await r.post(`${API}/ventes/bons-commande/${bc2.id}/creer-facture/`, { ...T, data: {} }), 409)
  await lireJson(await r.post(`${API}/ventes/factures/${f1.id}/emettre/`, { ...T, data: {} }), 'émission F1')
  const f1e = await lireFacture(r, f1.id)
  await lireJson(await r.post(`${API}/ventes/factures/${f1.id}/annuler/`, { ...T, data: { motif: 'AARG30' } }), 'annuler F1')
  // À l'écran : « Créer la facture » sur BC2.
  await page.goto('/ventes/bons-commande')
  const rangee = page.locator('tr').filter({ hasText: bc2.reference }).first()
  await expect(rangee).toBeVisible({ timeout: 60_000 })
  await rangee.getByRole('button', { name: /Facture/ }).first().click()
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && new RegExp(`/bons-commande/${bc2.id}/creer-facture/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('alertdialog').or(page.getByRole('dialog')).getByRole('button', { name: 'Créer la facture' }).click(),
  ])
  expect(rep.status(), await rep.text()).toBe(201)
  const f1r = await lireFacture(r, f1.id)
  expect(f1r.reference, 'F1 garde sa référence').toBe(f1e.reference)
  const hist = JSON.stringify(await lireJson(await r.get(`${API}/ventes/factures/${f1.id}/historique/`, T), 'historique F1'))
  expect(hist, 'chatter : détaché à la recréation').toMatch(/détachée? du bon de commande .* à la recréation/i)
})

// ── P8.4 — AARG32 : avertissement de vente bloquant aux portes BC et consolidation ──────────
etape('P8.4', ['AARG32'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r)
  const d2 = await vente(r, { client: d.client })
  const bc = await bcConfirme(r, d)
  shellJson(`from apps.crm.models import Client; import json; Client.objects.filter(pk=${d.client}).update(avertissement_bloquant=True, avertissement_vente='Litige en cours'); print('@@'+json.dumps(1))`)
  const c1 = await refus(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 403)
  expect(c1.code).toBe('sale_warning')
  const c2 = await refus(await r.post(`${API}/ventes/factures/consolider/`, { ...T, data: { devis_ids: [d.id, d2.id] } }), 403)
  expect(c2.code).toBe('sale_warning')
  // Commercial : l'override est refusé (BC de SON devis : la portée ne masque pas la porte).
  shellJson(`from apps.ventes.models import Devis; from django.contrib.auth import get_user_model; import json; Devis.objects.filter(pk=${d.id}).update(created_by=get_user_model().objects.get(username='demo_commercial')); print('@@'+json.dumps(1))`)
  const com = await sessionDe(testInfo, 'demo_commercial')
  try {
    const c3 = await com.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: { override_avertissement: true } })
    expect(c3.status(), `commercial : ${await c3.text()}`).toBe(403)
  } finally { await com.dispose() }
  // Admin : override 201, dérogation journalisée.
  const ok = await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: { override_avertissement: true } })
  expect(ok.status(), await ok.text()).toBe(201)
  const f = await ok.json()
  expect(f.id, 'facture créée').toBeTruthy()
  const hist = JSON.stringify(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'chatter du devis'))
  expect(hist, 'dérogation journalisée au chatter du devis').toMatch(/Litige en cours/)
  shellJson(`from apps.crm.models import Client; import json; Client.objects.filter(pk=${d.client}).update(avertissement_bloquant=False, avertissement_vente=''); print('@@'+json.dumps(1))`)
})

// ── P8.5 — AARG23 : réémission = date et numéro d'origine ; refus après envoi au client ─────
etape('P8.5', ['AARG23'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f0 = await factureComplete(r, await vente(r, { lignes: [['Prestation AARG23', '1', '1000.00', '20.00']] }))
  shellJson(`from apps.ventes.models import Facture; from django.utils import timezone; from datetime import timedelta; import json; d=timezone.localdate()-timedelta(days=40); Facture.objects.filter(pk=${f0.id}).update(date_emission=d, date_echeance=d+timedelta(days=30)); print('@@'+json.dumps(1))`)
  const avant = await lireFacture(r, f0.id)
  // Écran : menu de la ligne › Remettre en brouillon.
  const ligne = await ligneFacture(page, avant)
  await ligne.getByRole('button', { name: /Plus d.actions|Actions/i }).first().click()
  const [rep] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'POST' && /\/remettre-brouillon\/$/.test(new URL(x.url()).pathname), T),
    page.getByTestId('remettre-brouillon').click().then(async () => {
      const conf = page.getByRole('alertdialog').or(page.getByRole('dialog')).getByRole('button', { name: /Remettre|Confirmer/ })
      if (await conf.count()) await conf.first().click()
    }),
  ])
  expect(rep.status(), await rep.text()).toBe(200)
  const b = await lireFacture(r, f0.id)
  expect(b.statut).toBe('brouillon')
  await lireJson(await r.post(`${API}/ventes/factures/${f0.id}/emettre/`, { ...T, data: {} }), 'réémission')
  const apres = await lireFacture(r, f0.id)
  expect(apres.statut, 'statut après réémission').not.toBe('brouillon')
  expect(apres.reference, 'numéro d\'origine').toBe(avant.reference)
  expect(apres.date_emission, 'date d\'origine').toBe(avant.date_emission)
  expect(apres.date_echeance, 'échéance d\'origine').toBe(avant.date_echeance)
  // Envoi au client : refus.
  const f1 = await factureComplete(r, await vente(r))
  await lireJson(await r.post(`${API}/ventes/factures/${f1.id}/envoyer-email/`, { ...T, data: {} }), 'envoi au client (backend console)')
  await refus(await r.post(`${API}/ventes/factures/${f1.id}/remettre-brouillon/`, { ...T, data: {} }), 409, /déjà envoyée au client/)
  // Transmission DGI acceptée : refus.
  const f2d = await factureComplete(r, await vente(r))
  shellJson(`from apps.ventes.models import Facture; import json; Facture.objects.filter(pk=${f2d.id}).update(dgi_statut='acceptee'); print('@@'+json.dumps(1))`)
  await refus(await r.post(`${API}/ventes/factures/${f2d.id}/remettre-brouillon/`, { ...T, data: {} }), 409, /déjà envoyée au client/)
})

// ── P8.6 — AARG26 : sortie de « Signé » ─────────────────────────────────────────────────────
etape('P8.6', ['AARG26'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const d = await vente(r, { lignes: [['Installation AARG26', '1', '100000.00', '20.00']] })
  const lead = await lireJson(await r.get(`${API}/crm/leads/${d.leadId}/`, T), 'lead')
  expect(lead.stage, 'lead Signé').toBe('SIGNED')
  const f = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'acompte', montant_ttc: '35000.00', emettre: false } }), 'acompte saisi')
  const idB = f.facture.id
  const corps = await refus(await r.patch(`${API}/crm/leads/${d.leadId}/`, { ...T, data: { stage: 'FOLLOW_UP', confirme_recul: true } }), 409, new RegExp(`BROUILLON-${idB}`))
  expect(JSON.stringify(corps)).toMatch(/déjà créée/)
  expect((await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')).statut, 'devis toujours accepté').toBe('accepte')
  expect((await lireFacture(r, idB)).statut, 'brouillon intact').toBe('brouillon')
  expect(cents((await lireFacture(r, idB)).total_ttc), 'brouillon à 35 000').toBe(3500000)
  // Brouillon automatique non modifié : retiré à la sortie (VNT62).
  const d2 = await vente(r, { lignes: [['Installation AARG26 B', '1', '100000.00', '20.00']] })
  const auto = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${d2.id}`, T), 'factures')).find((x) => x.statut === 'brouillon')
  const ok = await r.patch(`${API}/crm/leads/${d2.leadId}/`, { ...T, data: { stage: 'FOLLOW_UP', confirme_recul: true } })
  expect(ok.status(), await ok.text()).toBe(200)
  expect((await lireJson(await r.get(`${API}/ventes/devis/${d2.id}/`, T), 'devis 2')).statut).toBe('envoye')
  if (auto) expect((await lireFacture(r, auto.id)).statut, 'brouillon auto annulé').toBe('annulee')
  // Écran : fiche du lead, Signé → Relance, « Ramener » : le 409 du serveur s'affiche tel quel, le lead reste à Signé.
  suivi.attendre(new RegExp(`/crm/leads/${d.leadId}/$`), 409)
  await page.goto(`/crm/leads/${d.leadId}`)
  await page.getByRole('group', { name: 'Étape du lead' }).getByRole('button').first().click()
  await page.getByRole('menuitem').filter({ hasText: 'Relance' }).click()
  const [repEcran] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'PATCH' && new RegExp(`/crm/leads/${d.leadId}/$`).test(new URL(x.url()).pathname), T),
    page.getByRole('alertdialog').or(page.getByRole('dialog')).getByRole('button', { name: 'Ramener' }).click(),
  ])
  expect(repEcran.status(), await repEcran.text()).toBe(409)
  await expect(page.getByText(new RegExp(`BROUILLON-${idB}`)).first()).toBeVisible({ timeout: 30_000 })
  expect((await lireJson(await r.get(`${API}/crm/leads/${d.leadId}/`, T), 'lead relu')).stage, 'lead toujours Signé').toBe('SIGNED')
})

// ── P8.7 — AARG47 : trace d'émission sur le lead de la vente ────────────────────────────────
etape('P8.7', ['AARG47'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const mail = email()
  const dA = await vente(r, { mail })
  // Second lead, plus récent, du même client.
  const leadB = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: uniq('AARG47 B'), ville: 'Rabat', telephone: telephoneMobileUnique(), email: mail } }), 'lead B')
  await vente(r, { lead: leadB.id })
  const bRelu = await lireJson(await r.get(`${API}/crm/leads/${leadB.id}/`, T), 'lead B relu')
  expect(bRelu.client, 'même client').toBe(dA.client)
  const f = await factureComplete(r, dA)
  expect(f.lead, 'facture portée par le lead A').toBe(dA.leadId)
  const lire = async (id) => JSON.stringify(await lireJson(await r.get(`${API}/crm/leads/${id}/historique/`, T), `historique ${id}`))
  expect(await lire(dA.leadId), 'trace sur A').toContain(`Facture ${f.reference} émise`)
  expect(await lire(leadB.id), 'pas sur B').not.toContain(`Facture ${f.reference} émise`)
  await page.goto(`/crm/leads/${dA.leadId}`)
  await expect(page.getByText(`Facture ${f.reference} émise`).first()).toBeVisible({ timeout: 60_000 })
})

// ── P8.8 — AARG48 : logo cité par une facture émise jamais effacé ───────────────────────────
etape('P8.8', ['AARG48'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const envoyer = async () => lireJson(await r.post(`${API}/parametres/upload-logo/`, {
    ...T, multipart: { file: { name: 'logo.png', mimeType: 'image/png', buffer: PNG_1PX } },
  }), 'upload logo')
  await envoyer()
  const f = await factureComplete(r, await vente(r))
  const objet = shellJson(`from apps.ventes.models import Facture; from django.conf import settings; from apps.ventes.utils.minio_client import get_minio_client; import json; k=(Facture.objects.get(pk=${f.id}).identite_vendeur or {}).get('logo_key'); h=get_minio_client().head_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=k); print('@@'+json.dumps({'k':k,'n':h['ContentLength']}))`)
  expect(objet.k, 'logo figé').toBeTruthy()
  await envoyer() // remplacement
  const encore = () => shellJson(`from django.conf import settings; from apps.ventes.utils.minio_client import get_minio_client; import json; h=get_minio_client().head_object(Bucket=settings.MINIO_BUCKET_UPLOADS, Key=${JSON.stringify(objet.k)}); print('@@'+json.dumps(h['ContentLength']))`)
  expect(encore(), 'objet gardé après remplacement').toBe(objet.n)
  const rep = await r.delete(`${API}/parametres/delete-logo/`, T)
  expect(rep.status(), await rep.text()).toBeLessThan(300)
  expect(encore(), 'objet gardé après retrait').toBe(objet.n)
  const octets = await (await r.get(`${API}/ventes/factures/${f.id}/telecharger-pdf/`, T)).body()
  expect(octets.toString('latin1'), 'PDF : image du logo présente').toMatch(/\/Subtype\s*\/Image/)
  await ligneFacture(page, f)
})

// ── P8.9 — AFAC104 : ligne de relevé ré-importable après annulation de saisie ───────────────
etape('P8.9', ['AFAC104'], async ({ page, testInfo }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const f = await factureComplete(r, await vente(r, { lignes: [['Prestation AFAC104', '1', '4166.67', '20.00']] }))
  const jour = AUJOURDHUI()
  const csv = (lignes) => Buffer.from(`date;reference;montant;mode\n${lignes.join('\n')}\n`, 'utf-8')
  const dry = async (buffer) => lireJson(await r.post(`${API}/ventes/paiements/import-releve/dry-run/`, {
    ...T, multipart: { file: { name: 'releve.csv', mimeType: 'text/csv', buffer } },
  }), 'dry-run')
  const commit = async (token) => lireJson(await r.post(`${API}/ventes/paiements/import-releve/commit/`, { ...T, data: { token } }), 'commit')
  const ligneF = `${jour};${f.reference};200.00;virement`
  const A = await dry(csv([ligneF]))
  expect((await commit(A.token)).created).toBe(1)
  const paiements = listeDe(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/paiements/`, T), 'paiements'))
  expect(paiements.length).toBe(1)
  await lireJson(await r.post(`${API}/ventes/paiements/${paiements[0].id}/annuler-saisie/`, { ...T, data: { motif: 'saisie erronée' } }), 'annuler-saisie')
  // Relevé B chevauchant.
  const B = await dry(csv([ligneF, `${jour};${f.reference};100.00;virement`]))
  const statuts = (d) => (d.preview || []).map((l) => l.statut)
  expect(statuts(B), `B : ${JSON.stringify(B).slice(0, 500)}`).not.toContain('doublon_import')
  const creesB = await commit(B.token)
  expect(creesB.created, 'B : la ligne annulée et la nouvelle').toBe(2)
  // Relevé C : doublon.
  const C = await dry(csv([ligneF]))
  expect(statuts(C), 'C : doublon_import').toContain('doublon_import')
  // Paiement REJETÉ : la clé reste.
  const apresB = listeDe(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/paiements/`, T), 'paiements B'))
  const cible = apresB.find((p) => f2(p.montant) === '100.00')
  await lireJson(await r.post(`${API}/ventes/paiements/${cible.id}/rejeter/`, { ...T, data: { motif: 'rejet banque' } }), 'rejet')
  const D = await dry(csv([`${jour};${f.reference};100.00;virement`]))
  expect(statuts(D), 'rejeté : doublon_import').toContain('doublon_import')
})
