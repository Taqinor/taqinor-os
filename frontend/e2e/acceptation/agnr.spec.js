// AGNR — spec d'acceptation en direct : contre-visite du 01/11/2026 (AGNR61) et échéancier à acompte en MAD
// (AGNR50, AGNR51, AGNR62). Jouée par l'orchestrateur sur la pile locale (CLAUDE.md 3-bis). Données posées par l'API.
// Limite : la page Astro `/proposition` n'est pas servie par la pile docker ; AGNR61-E3 lit son contrat public
// (GET /ventes/proposal/<jeton>/), les barres et journées types en dérivent sans calcul.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import {
  uniq, lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, textePdf, nombrePagesPdf,
} from '../helpers.js'

const etape = groupe('AGNR', ['AGNR50', 'AGNR51', 'AGNR62', 'AGNR61'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const nouveauLead = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid`, ...extra },
}), 'lead')
const devisRelu = async (request, id) => lireJson(await request.get(`${API}/ventes/devis/${id}/`, T), 'devis')
const produitEssai = async (request, nom, pv) => lireJson(await request.post(`${API}/stock/produits/`, {
  ...T, data: { nom: `${nom} ${marque()}`, prix_vente: pv, prix_achat: '111.11' },
}), 'produit')
const plat = (t) => t.replace(/[\s\u00a0\u202f]+/gu, ' ')

const LIGNES = (pan, ond) => [
  { produit: pan.id, designation: pan.nom, quantite: '10', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '10.00', type_ligne: 'produit', ordre: 0 },
  { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
]
const TOUT_PCT = [
  { libelle: 'Commande', type: 'acompte', unite: 'pct', pct_or_montant: 30, jalon: 'commande' },
  { libelle: 'Livraison', type: 'materiel', unite: 'pct', pct_or_montant: 40, jalon: 'livraison_materiel' },
  { libelle: 'Mise en service', type: 'mes', unite: 'pct', pct_or_montant: 20, jalon: 'mise_en_service' },
  { libelle: 'Réception', type: 'solde', unite: 'pct', pct_or_montant: 10, jalon: 'reception_definitive' },
]
const CENT_SOIXANTE = (e, ttc) => e.reduce((s, t) => s + (t.unite === 'montant' ? Number(t.pct_or_montant) : Number(t.pct_or_montant) * ttc / 100), 0)

async function devisIndustriel(request, nom) {
  const lead = await nouveauLead(request, nom, { type_installation: 'industriel' })
  const [pan, ond] = [await produitEssai(request, 'Panneau mono 550W AGNR', '1000.00'), await produitEssai(request, 'Onduleur réseau 10kW AGNR', '5000.00')]
  const d = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'industriel', echeancier: TOUT_PCT, lignes: LIGNES(pan, ond) },
  }), 'devis industriel')
  return { lead, pan, ond, d: await devisRelu(request, d.id) }
}

async function ouvrirDialoguePdf(page, d) {
  await page.goto('/ventes/devis')
  await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 150_000 })
  const ligne = page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: 'PDF', exact: true }).click()
  const dialogue = page.getByRole('dialog').filter({ hasText: `Générer le PDF — ${d.reference}` })
  await expect(dialogue).toBeVisible({ timeout: 30_000 })
  return dialogue
}

/** « Devis Final » (la case garde son état d'un rendu à l'autre) puis « Acompte personnalisé ». */
async function poserAcompte(dialogue, montant) {
  const radio = dialogue.getByRole('radio', { name: /Acompte personnalisé/ })
  if (!(await radio.isVisible().catch(() => false))) await dialogue.getByRole('checkbox', { name: /Devis Final/ }).click()
  await radio.click()
  await dialogue.locator('#pdf-acompte').fill(montant)
}

// ── E1 — dialogue PDF : acompte personnalisé 6 000 puis 8 500 sur 17 000 TTC ─────────────────────────
etape('AGNR61-E1', ['AGNR50', 'AGNR51', 'AGNR62', 'AGNR61'], async ({ page, suivi }) => {
  const m = marque()
  const { d, pan, ond, lead } = await devisIndustriel(page.request, `AGNR61 E1 ${m}`)
  expect(Number(d.total_ttc), '17 000 TTC').toBe(17000)
  const dialogue = await ouvrirDialoguePdf(page, d)
  await poserAcompte(dialogue, '6000')
  const [patch] = await Promise.all([
    page.waitForRequest((r) => r.method() === 'PATCH' && new RegExp(`/ventes/devis/${d.id}/$`).test(new URL(r.url()).pathname), T),
    dialogue.getByRole('button', { name: 'Générer' }).click(),
  ])
  const envoye = patch.postDataJSON().echeancier
  expect(envoye[0], 'acompte en MAD').toMatchObject({ unite: 'montant', pct_or_montant: 6000 })
  expect(envoye[envoye.length - 1], 'AGNR51 : la dernière tranche envoyée est le reste en MAD').toMatchObject({ unite: 'montant', pct_or_montant: 800 })
  expect((await patch.response()).status(), 'PATCH accepté').toBe(200)
  // AGNR50 : stocké = envoyé (non réécrit) ; dernière tranche 800 ; Σ = TTC.
  await expect.poll(async () => (await devisRelu(page.request, d.id)).echeancier?.at(-1)?.pct_or_montant, { timeout: 30_000 }).toBe(800)
  const relu = await devisRelu(page.request, d.id)
  expect(relu.echeancier.map((t) => [t.unite, Number(t.pct_or_montant)]), 'échéancier stocké').toEqual(envoye.map((t) => [t.unite, Number(t.pct_or_montant)]))
  expect(CENT_SOIXANTE(relu.echeancier, 17000), 'Σ montants = 17 000').toBeCloseTo(17000, 2)
  // Idempotent : renvoyer le stocké sans toucher.
  const idem = await lireJson(await page.request.patch(`${API}/ventes/devis/${d.id}/`, { ...T, data: { echeancier: relu.echeancier } }), 'renvoi du stocké')
  expect(idem.echeancier, 'objet identique').toEqual(relu.echeancier)
  // AGNR62 : /proposal imprime 6 000 / 6 800 / 3 400 / 800, jamais 35,29 % · 5 999,30.
  const r = await page.request.get(`${API}/ventes/devis/${d.id}/proposal/?devis_final=true`, T)
  expect(r.ok(), `/proposal (${r.status()})`).toBeTruthy()
  const octets = await r.body()
  const texte = plat(await textePdf(octets))
  for (const montant of ['6 000,00', '6 800,00', '3 400,00', '800,00']) expect(texte, `montant ${montant}`).toContain(`${montant} MAD TTC`)
  expect(texte, 'plus de 5 999,30').not.toContain('5 999,30')
  expect(texte, 'plus de 800,70').not.toContain('800,70')
  expect(await nombrePagesPdf(octets), 'industriel : 4 pages').toBe(4)
  expect(texte, 'jamais le prix d\'achat').not.toContain('111,11')
  // 8 500 : le TTC est dépassé ⇒ 409 nommé, génération arrêtée, devis inchangé.
  await page.keyboard.press('Escape').catch(() => undefined)
  const d2 = await ouvrirDialoguePdf(page, d)
  suivi.attendre(new RegExp(`/ventes/devis/${d.id}/$`), 409)
  await poserAcompte(d2, '8500')
  let genere = false
  page.on('request', (q) => { if (q.url().includes(`/devis/${d.id}/generer-pdf/`)) genere = true })
  const [p409] = await Promise.all([
    page.waitForResponse((x) => x.request().method() === 'PATCH' && new RegExp(`/ventes/devis/${d.id}/$`).test(new URL(x.url()).pathname), T),
    d2.getByRole('button', { name: 'Générer' }).click(),
  ])
  expect(p409.status(), '8 500 : 409').toBe(409)
  await expect(page.getByText(/total/i).filter({ hasText: /acompte|tranche|échéancier/i }).first(), "le message nommé s'affiche").toBeVisible({ timeout: 20_000 })
  expect(genere, 'génération arrêtée').toBe(false)
  expect((await devisRelu(page.request, d.id)).echeancier, 'devis inchangé').toEqual(relu.echeancier)
  // Atomic : même règle, refus = aucun devis.
  const av = [{ libelle: 'Commande', type: 'acompte', unite: 'montant', pct_or_montant: 6000, jalon: 'commande' }, ...TOUT_PCT.slice(1, 3), { ...TOUT_PCT[3] }]
  const ok = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'industriel', echeancier: av, lignes: LIGNES(pan, ond) },
  }), 'atomic 6 000')
  const okRelu = await devisRelu(page.request, ok.id)
  expect(okRelu.echeancier.at(-1), 'atomic : dernière tranche 800 MAD').toMatchObject({ unite: 'montant', pct_or_montant: 800 })
  const avant = listeDe(await lireJson(await page.request.get(`${API}/ventes/devis/?lead=${lead.id}&page_size=50`, T), 'liste')).length
  const refus = await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'industriel', echeancier: [{ ...av[0], pct_or_montant: 8500 }, ...av.slice(1)], lignes: LIGNES(pan, ond) },
  })
  expect(refus.status(), 'atomic 8 500 : 409').toBe(409)
  expect(listeDe(await lireJson(await page.request.get(`${API}/ventes/devis/?lead=${lead.id}&page_size=50`, T), 'liste')), 'aucun devis de plus').toHaveLength(avant)
  suivi.verifie(6)
  suivi.verifie(7)
})

// ── E2 — copies à TTC réduit d'un devis à acompte en MAD ─────────────────────────────────────────────
etape('AGNR61-E2', ['AGNR61'], async ({ page, suivi }) => {
  const m = marque()
  const { d, pan, ond } = await devisIndustriel(page.request, `AGNR61 E2 ${m}`)
  const ech = [{ libelle: 'Commande', type: 'acompte', unite: 'montant', pct_or_montant: 2000, jalon: 'commande' }, ...TOUT_PCT.slice(1, 3), { ...TOUT_PCT[3] }]
  await lireJson(await page.request.patch(`${API}/ventes/devis/${d.id}/`, { ...T, data: { echeancier: ech } }), 'acompte 2 000')
  // Renouvellement : catalogue baissé de moitié ⇒ TTC réduit ⇒ dernière tranche recalée.
  await lireJson(await page.request.patch(`${API}/stock/produits/${pan.id}/`, { ...T, data: { prix_vente: '500.00' } }), 'baisse panneau')
  await lireJson(await page.request.patch(`${API}/stock/produits/${ond.id}/`, { ...T, data: { prix_vente: '2500.00' } }), 'baisse onduleur')
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${d.id}).update(statut='expire')
sortie(1)`)
  const copie = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/renouveler/`, T), 'renouvellement')
  const relue = await devisRelu(page.request, copie.id)
  const ttc = Number(relue.total_ttc)
  expect(ttc, 'TTC réduit').toBeLessThan(17000)
  expect(CENT_SOIXANTE(relue.echeancier, ttc), 'Σ de la copie = son TTC').toBeCloseTo(ttc, 1)
  expect(relue.echeancier.at(-1).unite, 'dernière tranche au reste en MAD').toBe('montant')
  expect(Number(relue.echeancier.at(-1).pct_or_montant), 'aucun montant négatif').toBeGreaterThanOrEqual(0)
  // Source jamais modifiée.
  expect((await devisRelu(page.request, d.id)).echeancier.at(-1).unite).toBe(relue.echeancier.at(-1).unite)
  // Acompte au-delà du TTC de la copie : 409 nommé, aucune copie.
  const d3 = await devisIndustriel(page.request, `AGNR61 E2b ${m}`)
  await lireJson(await page.request.patch(`${API}/ventes/devis/${d3.d.id}/`, { ...T, data: { echeancier: [{ ...ech[0], pct_or_montant: 6000 }, ...ech.slice(1)] } }), 'acompte 6 000 (la copie à moitié prix dépasse)')
  await lireJson(await page.request.patch(`${API}/stock/produits/${d3.pan.id}/`, { ...T, data: { prix_vente: '500.00' } }), 'baisse')
  await lireJson(await page.request.patch(`${API}/stock/produits/${d3.ond.id}/`, { ...T, data: { prix_vente: '2500.00' } }), 'baisse')
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${d3.d.id}).update(statut='expire')
sortie(1)`)
  const refus = await page.request.post(`${API}/ventes/devis/${d3.d.id}/renouveler/`, T)
  expect(refus.status(), 'copie à reste négatif : 409').toBe(409)
  expect(await refus.text(), 'message nommé').toMatch(/dépassent le total de la copie/)
  // Écran : la copie se lit dans la liste.
  await page.goto('/ventes/devis')
  await page.getByPlaceholder('Rechercher (référence ou client)…').fill(relue.reference, { timeout: 150_000 })
  await expect(page.locator('tr', { has: page.getByTestId(`ref-cell-${relue.id}`) }).first()).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

// ── E3 — factures écran 500 / 1 200 ≠ lead 1 800 : la page publique lit la série de l'étude ─────────
etape('AGNR61-E3', ['AGNR61'], async ({ page, suivi }) => {
  const m = marque()
  const lead = await nouveauLead(page.request, `AGNR61 E3 ${m}`, { facture_hiver: '1800', type_installation: 'residentiel' })
  const pan = await produitEssai(page.request, 'Panneau mono 710W E3', '1000.00')
  const ond = await produitEssai(page.request, 'Onduleur réseau E3', '5000.00')
  const d = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: LIGNES(pan, ond) },
  }), 'devis')
  await lireJson(await page.request.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { factures_hiver_ete: { hiver_mad: 500, ete_mad: 1200, ete_differente: true } } }), 'étude')
  const lien = await lireJson(await page.request.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'lien')
  const jeton = lien.token ?? lien.url?.split('/').filter(Boolean).pop()
  const serie = await py(`from apps.ventes.models import Devis
from apps.ventes import etude_horaire as eh
d = Devis.objects.get(pk=${d.id})
p = eh.profil_conso_du_devis(d)
p = p[0] if isinstance(p, tuple) else p
p = p.get('kwh_mensuels') or p.get('mensuel') or p.get('profil') if isinstance(p, dict) else p
sortie(list(p))`)
  const pub = await lireJson(await page.request.get(`${API}/public/proposal/${jeton}/data/`, T), 'proposition publique')
  expect(pub.monthly_consumption, 'mois par mois = série de l\'étude').toEqual(serie.map((v) => Math.round(v)))
  const hiver = Math.min(...serie)
  const ete = Math.max(...serie)
  expect(ete, 'la série suit les factures écran, pas 12 × lead 1 800').toBeGreaterThan(hiver)
  const texte = JSON.stringify(pub)
  expect(texte, 'aucune clé prix_achat').not.toContain('prix_achat')
  // Journées types : conso/jour dérivée du mois de la série.
  const jt = pub.jours_types ?? pub.journee_type ?? pub.journees_types
  expect(jt, 'journées types servies').toBeTruthy()
  const parMois = Array.isArray(jt) ? jt : Object.values(jt)
  expect(parMois.length, 'quatre journées').toBeGreaterThanOrEqual(1)
  for (const j of parMois) expect(Number(j.conso_jour_kwh), 'conso journée > 0').toBeGreaterThan(0)
  const relu = await lireJson(await page.request.get(`${API}/public/proposal/${jeton}/data/`, T), 'relecture')
  expect(relu.monthly_consumption, 'persistance').toEqual(pub.monthly_consumption)
  // Écran : le devis reste ouvrable côté ERP (oracle 8), le jeton interne ne compte aucune ouverture.
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(7)
})

const reouvrirEtEnregistrer = async (page, id) => {
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  // Le catalogue arrive après le formulaire : la garde classe une ligne renommée sur son produit lié (AGNR36).
  await page.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  const sauve = page.waitForResponse((r) => r.request().method() !== 'GET' && new RegExp(`/ventes/devis/${id}/replace-lines/`).test(new URL(r.url()).pathname), T)
  await page.locator('#gen-form').getByRole('button', { name: 'Enregistrer les modifications' }).click()
  const r = await sauve
  expect(r.status(), 'ré-enregistrer sans toucher').toBeLessThan(300)
  }
const sansHeure = (e) => ({ ...e, provenance: e?.provenance && { ...e.provenance, captured_at: undefined } })

// ── E4 — réouverture sans toucher : « Facture réelle », panneaux renommés, échéancier figé ───────────
etape('AGNR61-E4', ['AGNR61'], async ({ page, suivi }) => {
  const m = marque()
  // (a) Facture réelle 150 MAD : etude_params posée comme l'écran la pose : 1 282 kWh/an affichés, ré-enregistrés à 1 282.
  const lead = await nouveauLead(page.request, `AGNR61 E4 ${m}`, { facture_hiver: '800', type_installation: 'residentiel' })
  const pan = await produitEssai(page.request, 'Panneau mono 550W E4', '1000.00')
  const ond = await produitEssai(page.request, 'Onduleur réseau E4', '5000.00')
  const d = await lireJson(await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel',
      lignes: [
        { produit: pan.id, designation: 'Modules toiture sud', quantite: '12', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  await lireJson(await page.request.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { distributeur: 'onee', conso_annuelle: 1282 } }), 'étude')
  await lireJson(await page.request.patch(`${API}/ventes/devis/${d.id}/`, {
    ...T, data: { echeancier: [{ libelle: 'Acompte', type: 'acompte', unite: 'pct', pct_or_montant: 30, fige_le: '2026-10-02T09:00:00+00:00' }, { libelle: 'Livraison', type: 'materiel', unite: 'pct', pct_or_montant: 60, fige_le: '2026-10-02T09:00:00+00:00' }, { libelle: 'Solde', type: 'solde', unite: 'pct', pct_or_montant: 10, fige_le: '2026-10-02T09:00:00+00:00' }] },
  }), 'échéancier figé')
  await reouvrirEtEnregistrer(page, d.id)
  const un = await devisRelu(page.request, d.id)
  expect(un.etude_params.conso_annuelle, 'conso gardée à 1 282').toBe(1282)
  expect(un.echeancier.map((t) => t.fige_le), 'fige_le gardé (AGNR60)').toEqual(['2026-10-02T09:00:00+00:00', '2026-10-02T09:00:00+00:00', '2026-10-02T09:00:00+00:00'])
  // (b) Panneaux renommés : le compte de panneaux suit les lignes, deuxième passage identique.
  await page.reload()
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('#gen-form').getByLabel('Nombre de panneaux').first(), 'panneaux = lignes').toHaveValue('12', { timeout: 30_000 })
  await reouvrirEtEnregistrer(page, d.id)
  const deux = await devisRelu(page.request, d.id)
  expect(sansHeure(deux.etude_params), 'étude identique au 2e passage').toEqual(sansHeure(un.etude_params))
  expect(deux.echeancier, 'échéancier identique').toEqual(un.echeancier)
  expect(deux.total_ttc, 'TTC identique').toBe(un.total_ttc)
  expect(deux.lignes.map((l) => [l.designation, l.quantite, l.prix_unitaire]), 'lignes identiques').toEqual(un.lignes.map((l) => [l.designation, l.quantite, l.prix_unitaire]))
  // (c) Ligne libre sans produit : refus du serveur nommé (409) ; l'avis de l'écran est couvert par (d).
  const libre = await page.request.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: null, designation: 'Câble', quantite: '2', prix_unitaire: '10.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] },
  })
  expect(libre.status(), 'ligne sans produit : 409').toBe(409)
  expect(await libre.text()).toMatch(/Ligne sans produit/)
  // (d) À l'écran, une ligne libre est annoncée avant l'envoi.
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  await page.waitForLoadState('networkidle', { timeout: 90_000 }).catch(() => undefined)
  await page.getByRole('button', { name: 'Ajouter ligne' }).first().click()
  await page.getByRole('textbox', { name: 'Désignation' }).last().fill('Câble')
  await page.locator('#gen-form').getByRole('button', { name: 'Enregistrer les modifications' }).click()
  await expect(page.getByText(/1 ligne sans produit ne sera pas enregistrée : Câble/).first(), 'la ligne libre est annoncée').toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
  void uniq
})
