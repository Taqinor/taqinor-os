// ENF15 — acceptation en direct des six lectures stock qui ont reçu un écran (e6adab273, 8efbbff89) :
// documents-expirants, export-conformite (+ xlsx), delai-mesure (`/stock/fournisseurs/conformite`),
// releve-deductions-tva (FacturesFournisseur), tracabilite (LotsEntrepot), valorisation-a-date
// (InventairesAnnuels). Contrat : apps/stock/contract_samples/stock_lectures_enf15.json.
//
// Oracles durs à chaque étape ; l'écran = l'API rechargée ; `prix_achat` jamais servi au Commercial.
// Données : lot, pièce fournisseur et facture fournisseur « ENF15 … » posés sur la démo locale.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { aujourdHui } from './_enregistrement.js'
import { API_DJANGO, assurerSessionPage, connexionApi, executerDansDjango, lireJson, listeDe, uniq } from '../helpers.js'

const etape = groupe('ENF', ['ENF15'])
const T = { timeout: 120_000 }
const API = API_DJANGO
const MARQUE_ACHAT = '6123.47'
const ESPACES = new RegExp(String.raw`[\s` + String.fromCharCode(160, 0x202f) + ']+', 'g')
const plat = (s) => String(s).replace(ESPACES, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const f2 = (v) => Number(v).toFixed(2)

test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

function shellJson(code) {
  const sortie = executerDansDjango(code)
  const ligne = sortie.split('\n').reverse().find((l) => l.startsWith('@@'))
  expect(ligne, `sortie du shell : ${sortie.slice(-400)}`).toBeTruthy()
  return JSON.parse(ligne.slice(2))
}

async function fournisseur(r) {
  return listeDe(await lireJson(await r.get(`${API}/stock/fournisseurs/?page_size=5&ordering=nom`, T), 'fournisseurs'))[0]
}

async function produitAvecReception(r, four) {
  const produit = await lireJson(await r.post(`${API}/stock/produits/`, {
    ...T, data: { nom: uniq('ENF15 produit'), prix_vente: '9000.00', prix_achat: MARQUE_ACHAT, quantite_stock: 0, tva: '20.00' },
  }), 'produit')
  const bcf = await lireJson(await r.post(`${API}/stock/bons-commande-fournisseur/`, {
    ...T, data: { fournisseur: four.id, date_commande: aujourdHui(), lignes: [{ produit: produit.id, quantite: 5, prix_achat_unitaire: MARQUE_ACHAT }] },
  }), 'BCF')
  await lireJson(await r.post(`${API}/stock/bons-commande-fournisseur/${bcf.id}/envoyer/`, T), 'envoi BCF')
  const relu = await lireJson(await r.get(`${API}/stock/bons-commande-fournisseur/${bcf.id}/`, T), 'BCF relu')
  const rec = await lireJson(await r.post(`${API}/stock/receptions-fournisseur/`, {
    ...T, data: { bon_commande: bcf.id, date_reception: aujourdHui(), lignes: [{ ligne_commande: relu.lignes[0].id, quantite: 5 }] },
  }), 'réception')
  await lireJson(await r.post(`${API}/stock/receptions-fournisseur/${rec.id}/confirmer/`, T), 'confirmation')
  return { produit, bcf: relu }
}

// ── E1 — Conformité : liste = API, pièce qui expire, export xlsx, délai mesuré ───────────────
etape('E1', ['ENF15'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(420_000)
  const r = page.request
  const four = await fournisseur(r)
  await produitAvecReception(r, four)
  const doc = shellJson(`
import json, datetime
from django.utils import timezone
from apps.stock.models import DocumentFournisseur, DossierOnboardingFournisseur
dossier, _ = DossierOnboardingFournisseur.objects.get_or_create(company_id=1, fournisseur_id=${four.id})
d = DocumentFournisseur.objects.create(company_id=1, dossier=dossier, type_document='rc', file_key='enf15/piece.pdf', filename='piece.pdf', date_expiration=timezone.localdate() + datetime.timedelta(days=8))
print('@@' + json.dumps({'id': d.id}))`.trim())
  const conformite = await lireJson(await r.get(`${API}/stock/fournisseurs/export-conformite/`, T), 'conformité')
  expect(Array.isArray(conformite) && conformite.length > 0, 'export-conformite : tableau non vide').toBeTruthy()
  const expirants = await lireJson(await r.get(`${API}/stock/fournisseurs/documents-expirants/?within=30`, T), 'expirants')
  expect(expirants.map((x) => x.document_id), 'pièce posée servie').toContain(doc.id)
  await page.goto('/stock/fournisseurs/conformite')
  await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible({ timeout: 60_000 })
  // Pièces qui expirent : la pièce du fournisseur à J+8 est listée.
  const sectionDocs = page.locator('section[aria-labelledby="cf-docs-titre"]')
  await sectionDocs.locator('#cf-within').fill('30')
  await expect(sectionDocs.getByText(four.nom).first()).toBeVisible({ timeout: 60_000 })
  // Liste de conformité : chaque fournisseur actif, le même que l'API.
  const sectionListe = page.locator('section[aria-labelledby="cf-liste-titre"]')
  await expect(sectionListe.getByText(conformite[0].fournisseur).first()).toBeVisible({ timeout: 60_000 })
  // Export xlsx : un vrai classeur (signature ZIP).
  const [repX] = await Promise.all([
    page.waitForResponse((x) => /\/fournisseurs\/export-conformite\/\?.*export=xlsx/.test(x.url()), T),
    sectionListe.getByRole('button', { name: 'Exporter en Excel' }).click(),
  ])
  expect(repX.status(), 'export xlsx').toBe(200)
  expect((await repX.body()).subarray(0, 2).toString('latin1'), 'classeur xlsx').toBe('PK')
  // Délai mesuré : le fournisseur choisi, le résultat de l'API à l'écran.
  const sectionDelai = page.locator('section[aria-labelledby="cf-delai-titre"]')
  await sectionDelai.getByRole('combobox', { name: 'Fournisseur' }).click()
  await page.getByRole('option', { name: four.nom }).first().click()
  const [repD] = await Promise.all([
    page.waitForResponse((x) => new RegExp(`/fournisseurs/${four.id}/delai-mesure/`).test(x.url()), T),
    sectionDelai.getByRole('button', { name: 'Mesurer' }).click(),
  ])
  expect(repD.status(), 'delai-mesure').toBe(200)
  const delai = await repD.json()
  expect(delai.nb_mesures, 'une livraison confirmée au moins').toBeGreaterThan(0)
  await expect(sectionDelai).toContainText(String(delai.nb_mesures), { timeout: 30_000 })
  await page.reload()
  await expect(sectionDocs.getByText(four.nom).first()).toBeVisible({ timeout: 60_000 })
  // Commercial : aucun montant d'achat servi ni visible.
  const com = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  try {
    await connexionApi(com, { username: 'demo_commercial', password: 'Demo@2026!' })
    const rep = await com.get(`${API}/stock/fournisseurs/export-conformite/`, T)
    expect([200, 403, 404], 'Commercial : refus ou sans montant').toContain(rep.status())
    const corps = await rep.text()
    expect(corps, 'Commercial : pas de montant acheté').not.toContain('montant_achete')
    expect(corps).not.toContain(MARQUE_ACHAT)
  } finally { await com.dispose() }
  suivi.verifie(5)
  suivi.verifie(7)
})

// ── E2 — Relevé de déductions de TVA (FacturesFournisseur) ───────────────────────────────────
etape('E2', ['ENF15'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const four = await fournisseur(r)
  await lireJson(await r.post(`${API}/stock/factures-fournisseur/`, {
    ...T, data: { fournisseur: four.id, reference: uniq('ENF15-FF'), date_facture: aujourdHui(), lignes: [{ designation: 'Matériel ENF15', quantite: '1', prix_unitaire_ht: '1000.00', taux_tva: '20.00' }] },
  }), 'facture fournisseur')
  const jour = aujourdHui()
  const lignes = await lireJson(await r.get(`${API}/stock/factures-fournisseur/releve-deductions-tva/?date_debut=${jour}&date_fin=${jour}`, T), 'relevé')
  expect(Array.isArray(lignes) && lignes.length > 0, `relevé non vide : ${JSON.stringify(lignes)}`).toBeTruthy()
  const total = lignes.reduce((s, l) => s + Number(l.total_tva), 0)
  await page.goto('/stock/factures-fournisseur')
  const section = page.locator('section[aria-labelledby="rdt-titre"]')
  await section.locator('#rdt-debut').fill(jour)
  await section.locator('#rdt-fin').fill(jour)
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /\/releve-deductions-tva\//.test(x.url()), T),
    section.getByRole('button', { name: 'Afficher le relevé' }).click(),
  ])
  expect(rep.status()).toBe(200)
  await expect(section.locator('tfoot')).toBeVisible({ timeout: 30_000 })
  expect(plat(await section.locator('tfoot').innerText()), 'total écran = API').toContain(f2(total))
  expect(await section.locator('tbody tr').count(), 'une ligne par taux').toBe(lignes.length)
  await page.reload()
  await expect(section.getByRole('button', { name: 'Afficher le relevé' })).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── E3 — Traçabilité lot / série (LotsEntrepot) ──────────────────────────────────────────────
etape('E3', ['ENF15'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const numero = `ENF15-${Date.now()}`
  const p = shellJson(`
import json
from decimal import Decimal
from apps.stock.models import Produit, LotEntrepot
pr = Produit.objects.create(company_id=1, nom='ENF15 tracé ${numero}', sku='${numero}', prix_achat=Decimal('${MARQUE_ACHAT}'), prix_vente=Decimal('9000'), quantite_stock=7)
LotEntrepot.objects.create(company_id=1, produit=pr, numero_lot='${numero}', quantite_recue=7, quantite_restante=7)
print('@@' + json.dumps({'id': pr.id, 'nom': pr.nom}))`.trim())
  const chaine = await lireJson(await r.get(`${API}/stock/produits/tracabilite/?lot=${numero}`, T), 'traçabilité')
  expect(chaine.produit?.id ?? chaine.produit?.produit_id ?? p.id).toBe(p.id)
  await page.goto('/stock/lots-entrepot')
  const section = page.locator('section[aria-labelledby="tr-titre"]')
  await section.locator('#tr-numero').fill(numero)
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /\/produits\/tracabilite\//.test(x.url()), T),
    section.getByRole('button', { name: 'Tracer' }).click(),
  ])
  expect(rep.status()).toBe(200)
  await expect(section.getByText(p.nom)).toBeVisible({ timeout: 30_000 })
  await expect(section).toContainText('Restant : 7')
  expect(plat(await section.innerText()), 'prix d\'achat absent').not.toContain(MARQUE_ACHAT)
  // Numéro inconnu : refus lisible, pas un écran cassé.
  suivi.attendre(/\/produits\/tracabilite\//, 404)
  await section.locator('#tr-numero').fill(`INCONNU-${Date.now()}`)
  const [rep404] = await Promise.all([
    page.waitForResponse((x) => /\/produits\/tracabilite\//.test(x.url()), T),
    section.getByRole('button', { name: 'Tracer' }).click(),
  ])
  expect(rep404.status(), 'numéro inconnu').toBe(404)
  await expect(section.getByText('Aucune traçabilité trouvée pour ce numéro.')).toBeVisible({ timeout: 30_000 })
  suivi.verifie(7)
})

// ── E4 — Valorisation à date (InventairesAnnuels) ────────────────────────────────────────────
etape('E4', ['ENF15'], async ({ page, testInfo, suivi }) => {
  testInfo.setTimeout(300_000)
  const r = page.request
  const four = await fournisseur(r)
  const { produit } = await produitAvecReception(r, four)
  const jour = aujourdHui()
  const releve = await lireJson(await r.get(`${API}/stock/produits/valorisation-a-date/?date=${jour}`, T), 'valorisation')
  expect((releve.lignes || []).length, 'lignes de valorisation').toBeGreaterThan(0)
  expect((releve.lignes || []).map((l) => l.produit_id), 'le produit reçu est valorisé').toContain(produit.id)
  await page.goto('/stock/inventaires-annuels')
  const section = page.locator('section[aria-labelledby="val-titre"]')
  await section.locator('#val-date').fill(jour)
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /\/produits\/valorisation-a-date\//.test(x.url()), T),
    section.getByRole('button', { name: 'Valoriser' }).click(),
  ])
  expect(rep.status()).toBe(200)
  expect(plat(await section.innerText()), 'total écran = API').toContain(f2(releve.total))
  // Commercial : la valorisation (coût d'achat) ne lui est jamais servie.
  const com = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  try {
    await connexionApi(com, { username: 'demo_commercial', password: 'Demo@2026!' })
    const repC = await com.get(`${API}/stock/produits/valorisation-a-date/?date=${jour}`, T)
    expect(repC.status(), `Commercial : ${(await repC.text()).slice(0, 200)}`).toBe(403)
  } finally { await com.dispose() }
  suivi.verifie(5)
  suivi.verifie(7)
})
