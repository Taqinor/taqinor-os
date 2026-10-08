// AGR222 — ALLER-RETOUR EN DIRECT du parcours « économie agricole » (D-AGR-5, Q17).
//
// Pile locale seedée (`seed_demo`), aucun mock réseau. Le devis est créé PAR
// L'ÉCRAN, relu par l'API, rouvert (`?edit=`) puis ré-enregistré sans toucher :
//   1. butane 2 bouteilles/jour × 3 jours/semaine, 50 DH, déclaré aujourd'hui ;
//      mois cochés par le vendeur (volume déclaré : rien de pré-coché, AGR212)
//      puis CONFIRMÉS ; enregistrement ;
//   2. la carte « Économie déclarée » montre la dépense détaillée, le retour
//      SANS aide et l'étiquette « estimation » ;
//   3. rouvrir + ré-enregistrer = `saisies_economie_pompage` identique (API) ;
//   4. énergie « aucune » ⇒ aucun retour (le coût du m³ seul, ou son motif) ;
//   5. une ligne à 0 % sans base légale ⇒ message SOUS le champ ;
//   6. une date de solde saisie dans l'échéancier est relue à la réouverture.
// Non exécuté localement : il tourne dans le job e2e de la CI (capture jointe).
// Nettoyage best-effort en afterAll (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import { choisirMarche } from './helpers'

const API = '/api/django'
const AUJOURDHUI = new Date().toISOString().slice(0, 10)
const ids = []

async function lireJson(reponse, quoi) {
  expect(reponse.ok(), `${quoi} → HTTP ${reponse.status()}`).toBeTruthy()
  return reponse.json()
}

async function clientDeLaDemo(request) {
  const corps = await lireJson(await request.get(`${API}/crm/clients/`), 'clients')
  const liste = Array.isArray(corps) ? corps : (corps.results || [])
  expect(liste.length, 'seed_demo doit fournir un client').toBeGreaterThan(0)
  return liste[0]
}

async function devisParApi(request, id) {
  return lireJson(await request.get(`${API}/ventes/devis/${id}/`), `devis ${id}`)
}

async function choisirDansSelect(page, idDeclencheur, libelle) {
  await page.locator(idDeclencheur).click()
  await page.getByRole('option', { name: libelle }).click()
}

async function declarerButane(page) {
  await page.locator('#gen-farm-fuel').selectOption('butane')
  await page.locator('#gen-eco-quantite').fill('2')
  await page.locator('#gen-eco-unite').selectOption('bouteille_12kg')
  await page.locator('#gen-eco-periode').selectOption('jour_irrigation')
  await page.locator('#gen-eco-jours').fill('3')
  await page.locator('#gen-eco-prix').fill('50')
  await page.locator('#gen-eco-date').fill(AUJOURDHUI)
}

async function creerDevisAgricole(page, client) {
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await expect(page.locator('table.lines-table tbody tr').first())
    .toBeVisible({ timeout: 45_000 })
  await page.locator('#gen-client').click()
  await page.locator('[role="searchbox"]').last().fill(client.nom || client.name || '')
  await page.locator('[role="option"]').first().click()
  await choisirMarche(page, /Agricole/)
  await page.getByRole('radio', { name: 'Pompe neuve' }).click()
  await page.getByRole('radio', { name: 'Volume déclaré' }).click()
  await page.locator('#gen-besoin-volume').fill('60')
  await page.locator('#gen-hmt').fill('45')
  await page.getByRole('radio', { name: /Tri 380V/ }).click()
  await choisirDansSelect(page, '#gen-farm-crop', 'Agrumes')
  await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })
  await page.getByTestId('btn-auto-remplir').click()
  await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 30_000 })
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(ids.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('AGR222 — butane déclaré : carte, enregistrement, réouverture identique', async ({ page, request }) => {
  test.setTimeout(300_000)
  await creerDevisAgricole(page, await clientDeLaDemo(request))
  await declarerButane(page)

  // AGR212 (DevisGenerator `moisCalendrier`) : seul un besoin AGRONOMIQUE
  // (mode « Cultures ») pré-coche les mois. Ici le besoin est un VOLUME
  // DÉCLARÉ (D-AGR-3, déclaré d'abord) : aucun mois n'est inventé, le vendeur
  // coche lui-même la saison d'irrigation puis la CONFIRME.
  const mois = page.getByTestId('mois-irrigation')
  await expect(mois).not.toContainText(/pré-cochés/)
  for (const m of [4, 5, 6, 7, 8, 9]) await mois.getByTestId(`mois-irr-${m}`).check()
  await page.getByLabel('Mois confirmés avec le client').check()

  // La carte : dépense détaillée, retour SANS aide, étiquette « estimation ».
  const carte = page.getByTestId('carte-economie-vue')
  await expect(carte).toBeVisible({ timeout: 45_000 })
  await expect(carte).toContainText(/estimation/i)
  await expect(page.getByTestId('detail-declare')).toBeVisible()
  await expect(page.getByTestId('depense-actuelle')).not.toContainText('non calculé')
  await expect(page.getByTestId('retour-ans')).toContainText('Retour sans aide')

  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  // Les saisies d'économie partent APRÈS la création, par la fusion
  // `PATCH …/etude-params/` (QJR62) : on attend sa réponse avant de relire.
  const etudeEcrite = page.waitForResponse((r) => r.request().method() === 'PATCH'
    && /\/ventes\/devis\/\d+\/etude-params\/$/.test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  await etudeEcrite
  const id = cree.id ?? cree.devis?.id
  expect(id, 'identifiant du devis créé').toBeTruthy()
  ids.push(id)

  const avant = (await devisParApi(request, id)).etude_params.saisies_economie_pompage
  expect(avant.energie_actuelle.valeur).toBe('butane')
  expect(avant.consommation).toMatchObject({
    quantite: 2, unite: 'bouteille_12kg', periode: 'jour_irrigation',
    jours_irrigation_par_semaine: 3,
  })
  expect(avant.depense_unitaire_payee.valeur).toBe(50)
  expect(avant.depense_unitaire_payee.saisi_le).toBe(AUJOURDHUI)
  expect(avant.mois_irrigation.provenance.origine).toBe('saisie')

  // Rouvrir puis ré-enregistrer SANS toucher : l'objet serveur est identique.
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('#gen-farm-fuel')).toHaveValue('butane', { timeout: 45_000 })
  const sauvegarde = page.waitForResponse((r) => ['PUT', 'POST', 'PATCH'].includes(r.request().method())
    && new RegExp(`/ventes/devis/${id}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: 'Enregistrer les modifications' }).click()
  await sauvegarde
  const apres = (await devisParApi(request, id)).etude_params.saisies_economie_pompage
  expect(apres).toEqual(avant)

  // Énergie « aucune » : aucun retour — le coût du m³ seul, ou son motif.
  // L'enregistrement quitte le formulaire (écran « Devis enregistré ») : on le rouvre.
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('#gen-farm-fuel')).toHaveValue('butane', { timeout: 45_000 })
  await page.locator('#gen-farm-fuel').selectOption('aucune')
  await expect(page.getByTestId('retour-ans')).toContainText('non calculé', { timeout: 45_000 })
})

test('AGR222 — ligne à 0 % sans base légale, et date de solde relue', async ({ page, request }) => {
  test.setTimeout(300_000)
  await creerDevisAgricole(page, await clientDeLaDemo(request))
  await declarerButane(page)

  // Une ligne à 0 % sans base légale : le message s'affiche SOUS le champ.
  // Le champ du taux est l'input NUMÉRIQUE : à 0 %, la même cellule montre en
  // plus l'input texte « base légale » (deux inputs — violation stricte sinon).
  const tva = page.locator('table.lines-table tbody tr').first()
    .locator('td[data-label="TVA %"] input[type="number"]')
  await tva.fill('0')
  const base = page.getByTestId('ligne-base-legale').first()
  await expect(base.getByRole('alert')).toContainText(/Base légale obligatoire/)
  await tva.fill('20')
  await expect(page.getByTestId('ligne-base-legale')).toHaveCount(0)

  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  const id = cree.id ?? cree.devis?.id
  ids.push(id)

  // Date de solde saisie dans l'échéancier (Édition complète) : relue ensuite.
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await page.getByRole('button', { name: /Personnaliser l'échéancier/ }).click()
  const carte = page.getByTestId('carte-echeancier')
  const derniere = carte.locator('input[type="date"]').last()
  await derniere.fill('2027-03-31')
  const sauvegarde = page.waitForResponse((r) => ['PUT', 'POST', 'PATCH'].includes(r.request().method())
    && new RegExp(`/ventes/devis/${id}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: 'Enregistrer les modifications' }).click()
  await sauvegarde
  const tranches = (await devisParApi(request, id)).echeancier
  expect(tranches.at(-1).date_prevue).toBe('2027-03-31')

  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.getByTestId('carte-echeancier').locator('input[type="date"]').last())
    .toHaveValue('2027-03-31', { timeout: 45_000 })
})
