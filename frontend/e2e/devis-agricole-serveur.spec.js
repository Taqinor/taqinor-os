// AGR130 — ALLER-RETOUR EN DIRECT du générateur agricole : Auto-remplir, enregistrer
// et rouvrir passent par le SERVEUR (aperçu AGR127 → kit AGR121, rafraîchisseur
// AGR123), le navigateur n'envoie que les ENTRÉES v2.
//
// Pile locale `seed_demo`, aucun mock réseau sur les écrans testés. Deux devis,
// créés PAR L'ÉCRAN puis relus par l'API et rouverts (`?edit=`) :
//   1. « pompe neuve » : besoin en eau + HMT, Auto-remplir (lignes du kit
//      serveur), enregistrement ;
//   2. « pompe existante » : plaque relevée, SANS ligne pompe — la garde
//      « au moins une pompe » ne la bloque pas.
// Pour chacun : `etude_params` ne porte AUCUNE clé dérivée écrite par le
// navigateur (pompe_cv, m3_jour…) mais les entrées v2 ET les dérivées posées
// par le serveur ; rouvrir puis ré-enregistrer sans toucher laisse l'objet
// serveur identique (lignes + entrées) ; `/proposal` répond 200 ; l'écran
// rouvert montre les chiffres de `etude_params`.
// Nettoyage best-effort en afterAll (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import { choisirMarche } from './helpers'

const API = '/api/django'
const DERIVEES_CLIENT_INTERDITES = ['pompe_cv', 'pompe_kw', 'hmt_m', 'debit_hmt_m3h',
  'm3_jour', 'champ_kwc', 'heures_pompage']
// Les entrées v2 (contrat etude_pompage_preview.json, cles_etude_params_v2.entrees).
const ENTREES_V2 = ['mode_pompe', 'besoin', 'source', 'hmt_entrees', 'alim', 'type_pompe',
  'localisation', 'distance_champ_m', 'options_cochees', 'taille']

const devisIds = []

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

async function premierClient(request) {
  const corps = await json(await request.get(`${API}/crm/clients/`), 'clients')
  const liste = Array.isArray(corps) ? corps : (corps.results || [])
  expect(liste.length, 'seed_demo doit fournir au moins un client').toBeGreaterThan(0)
  return liste[0]
}

/** Ouvre le générateur en marché Agricole, client choisi, stock chargé. */
async function ouvrirGenerateurAgricole(page, client) {
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await expect(page.locator('table.lines-table tbody tr').first())
    .toBeVisible({ timeout: 45_000 })
  await page.locator('#gen-client').click()
  await page.locator('[role="searchbox"]').last().fill(client.nom || client.name || '')
  await page.locator('[role="option"]').first().click()
  await choisirMarche(page, /Agricole/)
  await expect(page.getByTestId('bloc-cas-pompe')).toBeVisible()
}

async function renseignerBesoinEtHauteur(page) {
  await page.getByRole('radio', { name: 'Volume déclaré' }).click()
  await page.locator('#gen-besoin-volume').fill('60')
  await page.locator('#gen-hmt').fill('45')
  await page.getByRole('radio', { name: /Tri 380V/ }).click()
  // L'aperçu serveur répond (aucun calcul local) : le résultat s'affiche.
  await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })
}

async function enregistrer(page) {
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const devis = await (await creation).json()
  await expect(page.getByText('Devis enregistré')).toBeVisible({ timeout: 45_000 })
  const id = devis.id ?? devis.devis?.id
  expect(id, 'identifiant du devis créé').toBeTruthy()
  devisIds.push(id)
  return id
}

async function lireDevis(request, id) {
  return json(await request.get(`${API}/ventes/devis/${id}/`), `devis ${id}`)
}

const lignesComparables = (devis) => (devis.lignes || []).map((l) => ({
  produit: l.produit, designation: l.designation, quantite: Number(l.quantite),
  prix_unitaire: Number(l.prix_unitaire), taux_tva: Number(l.taux_tva),
}))

async function verifierAllerRetour(page, request, id) {
  const avant = await lireDevis(request, id)
  const etude = avant.etude_params || {}
  // Le navigateur n'a écrit que des entrées : les entrées v2 sont là…
  for (const cle of ['mode_pompe', 'besoin', 'hmt_entrees', 'taille']) {
    expect(etude[cle], `etude_params.${cle}`).toBeTruthy()
  }
  // …et toute dérivée présente vient du rafraîchisseur serveur (AGR123),
  // jamais de l'écran : le serveur REFUSE ces clés en 400 côté navigateur.
  const refus = await request.patch(`${API}/ventes/devis/${id}/etude-params/`, {
    data: { pompe_cv: 99 },
  })
  expect(refus.status(), 'une clé dérivée venue du navigateur est refusée').toBe(400)

  // /proposal répond 200 (rendu du moteur premium, règle #4).
  const pdf = await request.get(`${API}/ventes/devis/${id}/proposal/`)
  expect(pdf.status(), '/proposal').toBe(200)

  // Rouvrir (?edit=) puis ré-enregistrer SANS rien toucher.
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.getByTestId('bloc-cas-pompe')).toBeVisible({ timeout: 45_000 })
  // L'écran rouvert montre les chiffres de `etude_params` (besoin saisi, HMT saisie).
  await expect(page.locator('#gen-besoin-volume')).toHaveValue(
    String(etude.besoin?.volume_m3_jour ?? ''))
  await expect(page.locator('#gen-hmt')).toHaveValue(String(etude.hmt_entrees?.saisie_m ?? ''))
  await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })

  const sauvegarde = page.waitForResponse((r) => ['PUT', 'POST', 'PATCH'].includes(r.request().method())
    && new RegExp(`/ventes/devis/${id}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Enregistrer/ }).first().click()
  await sauvegarde

  const apres = await lireDevis(request, id)
  expect(lignesComparables(apres)).toEqual(lignesComparables(avant))
  for (const cle of ENTREES_V2) {
    expect(apres.etude_params[cle], `etude_params.${cle} identique`).toEqual(etude[cle])
  }
  return apres
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('AGR130 — pompe NEUVE : Auto-remplir (kit serveur), enregistrer, rouvrir, ré-enregistrer', async ({ page, request }) => {
  test.setTimeout(240_000)
  const client = await premierClient(request)
  await ouvrirGenerateurAgricole(page, client)
  await page.getByRole('radio', { name: 'Pompe neuve' }).click()
  await renseignerBesoinEtHauteur(page)

  await page.getByTestId('btn-auto-remplir').click()
  await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 30_000 })
  const id = await enregistrer(page)

  const devis = await lireDevis(request, id)
  expect(devis.etude_params.mode_pompe).toBe('neuve')
  expect(devis.etude_params.plaque ?? null).toBeNull()
  for (const cle of DERIVEES_CLIENT_INTERDITES) {
    // Si la clé existe, c'est le serveur qui l'a posée (elle porte une valeur
    // cohérente avec la pompe retenue), jamais une saisie : la vérité est le
    // refus 400 testé dans `verifierAllerRetour`.
    expect(typeof devis.etude_params[cle] === 'object' && devis.etude_params[cle] !== null)
      .toBeFalsy()
  }
  await verifierAllerRetour(page, request, id)
})

test('AGR130 — pompe EXISTANTE conservée : aucune ligne pompe, la garde ne bloque pas', async ({ page, request }) => {
  test.setTimeout(240_000)
  const client = await premierClient(request)
  await ouvrirGenerateurAgricole(page, client)
  await page.getByRole('radio', { name: 'Pompe existante conservée' }).click()
  await page.locator('#gen-plaque-kw').fill('5.5')
  await page.locator('#gen-plaque-tension').fill('380')
  await page.locator('#gen-plaque-phases').selectOption('tri')
  await renseignerBesoinEtHauteur(page)

  await page.getByTestId('btn-auto-remplir').click()
  await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 30_000 })
  const id = await enregistrer(page)

  const devis = await lireDevis(request, id)
  expect(devis.etude_params.mode_pompe).toBe('existante')
  expect(devis.etude_params.plaque).toMatchObject({ kw: 5.5, tension_v: 380, phases: 'tri' })
  expect(lignesComparables(devis).some((l) => /pompe/i.test(l.designation)
    && !/variateur/i.test(l.designation)), 'aucune ligne pompe en mode existante').toBeFalsy()
  await verifierAllerRetour(page, request, id)
})
