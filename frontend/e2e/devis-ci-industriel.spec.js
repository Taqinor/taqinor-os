// CIQ346 — CLÔTURE DE LA VAGUE INDUSTRIELLE : aller-retour EN DIRECT d'un devis
// industriel MT (leçon QJR5 « déployable ≠ vert » : la preuve se fait en
// direct, pile locale `seed_demo`, aucun mock réseau).
//
//   1. création depuis `/ventes/devis/nouveau` : marché Industriel, tension MT,
//      12 FACTURES MT déclarées (mois, montant TTC, kWh), rythme déclaré, taux
//      d'actualisation DÉCLARÉ par le client, Auto-remplir (moteur serveur),
//      « Créer le devis » ; rouvrir (`?edit=`) et ré-enregistrer sans rien
//      toucher ⇒ objet (`etude_params`) IDENTIQUE ;
//   2. PDF client (`/proposal`, le chemin unique de `generer-pdf`, règle #4) :
//      4 pages, avec ou sans `include_etude` ; page finance « TRI sur 25 ans »
//      avec la VAN ;
//   3. lien public → `GET /api/django/ventes/proposal/<token>/` :
//      `synthese_ci.argent` égal à celui du PDF, aucune clé P90 ;
//   4. (optionnel, `WEB_URL` = apps/web en dev) /proposition : aucun « heures
//      les plus chères », aucun « CBAM » sans déclaration ; captures FR et AR ;
//   5. signature en ligne avec raison sociale, qualité et ICE → copie signée
//      complète.
// Base partagée, workers: 1 : nettoyage best-effort en afterAll.
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, KWH_INDUSTRIEL, choisirMarche, declarerProfilCi, lireJson, listeDe, textePdf,
} from './helpers'

const ANNEE_FACTURES = new Date().getFullYear() - 1
// Montants TTC de facture de TEST (fixture e2e, jamais imprimés comme un fait) :
// kWh du profil industriel × 1,25 MAD.
const FACTURES_MT = KWH_INDUSTRIEL.map((kwh, i) => ({
  mois: `${ANNEE_FACTURES}-${String(i + 1).padStart(2, '0')}`,
  montant_ttc: String(Math.round(kwh * 1.25)),
  kwh: String(kwh),
}))
const TAUX_ACTUALISATION = '8'
const ENTREPRISE = {
  raison_sociale: 'Usine E2E Souss SA',
  signataire_qualite: 'Directeur administratif et financier',
  // ICE FACTICE de 15 chiffres (le même que l'exemple du contrat).
  ice: '000000000000000',
}
const devisIds = []
const etat = { devisId: null, token: null, pdfTexte: null }

/** Nombre de pages d'un PDF, lu sur ses objets /Type /Page (pas /Pages). */
function nombrePages(octets) {
  const texte = Buffer.from(octets).toString('latin1')
  return (texte.match(/\/Type\s*\/Page(?![s\w])/g) || []).length
}

/** Toutes les clés d'un objet JSON, à toute profondeur. */
function clesProfondes(v, out = []) {
  if (Array.isArray(v)) v.forEach((x) => clesProfondes(x, out))
  else if (v && typeof v === 'object') {
    for (const [k, x] of Object.entries(v)) { out.push(k); clesProfondes(x, out) }
  }
  return out
}

async function premierLead(request) {
  const liste = listeDe(await lireJson(await request.get(`${API}/crm/leads/`), 'leads'))
  expect(liste.length, 'seed_demo doit fournir au moins un lead').toBeGreaterThan(0)
  return liste.find((l) => l.type_installation === 'industriel') || liste[0]
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('CIQ346 — créer (MT, 12 factures, taux d’actualisation déclaré), rouvrir, ré-enregistrer : objet identique', async ({ page, request }) => {
  test.setTimeout(300_000)
  const lead = await premierLead(request)
  await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await choisirMarche(page, /Industriel/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()
  await expect(page.getByTestId('ci-industriel-mt')).toBeVisible()
  await page.locator('#gen-ci-tension').selectOption('mt')

  // Consommation par 12 FACTURES MT déclarées.
  await page.getByTestId('ci-saisie-factures').check()
  const lignesFactures = page.locator('[data-testid^="gen-ci-facture-mois-"]')
  while (await lignesFactures.count() < FACTURES_MT.length) {
    await page.getByTestId('ci-factures').getByRole('button', { name: 'Ajouter une facture' }).click()
  }
  for (const [i, f] of FACTURES_MT.entries()) {
    await page.getByTestId(`gen-ci-facture-mois-${i}`).fill(f.mois)
    await page.getByTestId(`gen-ci-facture-montant-${i}`).fill(f.montant_ttc)
    await page.getByTestId(`gen-ci-facture-kwh-${i}`).fill(f.kwh)
  }
  // Calendrier + taille (voir declarerProfilCi) ; en MT le contrat est le Tarif
  // Général, reconnu par la tension.
  await declarerProfilCi(page, { contrat: null })
  await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
  // Taux d'actualisation DÉCLARÉ par le client (la VAN n'existe que sur lui).
  await page.locator('#gen-eco-taux').fill(TAUX_ACTUALISATION)
  await page.locator('#gen-eco-taux-source').fill('Déclaré par le DAF (e2e)')

  const auto = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/etude-ci\/preview\/$/.test(new URL(r.url()).pathname))
  await page.getByTestId('btn-auto-remplir').click()
  await auto
  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  etat.devisId = cree.id ?? cree.devis?.id
  expect(etat.devisId, 'identifiant du devis créé').toBeTruthy()
  devisIds.push(etat.devisId)

  const avant = await lireJson(await request.get(`${API}/ventes/devis/${etat.devisId}/`), 'devis')
  expect(avant.mode_installation).toBe('industriel')

  // Rouvrir, ré-enregistrer sans rien toucher.
  await page.goto(`/ventes/devis/nouveau?edit=${etat.devisId}`)
  await expect(page.getByTestId('ci-industriel-mt')).toBeVisible({ timeout: 45_000 })
  await expect(page.getByTestId('gen-ci-facture-kwh-11')).toHaveValue(FACTURES_MT[11].kwh)
  await expect(page.locator('#gen-eco-taux')).toHaveValue(TAUX_ACTUALISATION)
  const sauvegarde = page.waitForResponse((r) => r.request().method() !== 'GET'
    && new RegExp(`/ventes/devis/${etat.devisId}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Enregistrer les modifications/ }).click()
  await sauvegarde
  await expect.poll(async () => {
    const relu = await lireJson(await request.get(`${API}/ventes/devis/${etat.devisId}/`), 'devis relu')
    return relu.etude_params
  }, { timeout: 30_000, message: 'objet identique après réouverture' }).toEqual(avant.etude_params)
})

test('CIQ346 — PDF : 4 pages avec ou sans étude, « TRI sur 25 ans » et VAN', async ({ request }) => {
  test.setTimeout(180_000)
  expect(etat.devisId, 'le test de création doit précéder').toBeTruthy()
  for (const suffixe of ['', '&include_etude=1']) {
    const pdf = await request.get(`${API}/ventes/devis/${etat.devisId}/proposal/?pdf_mode=full${suffixe}`)
    expect(pdf.status(), `/proposal${suffixe}`).toBe(200)
    const octets = await pdf.body()
    expect(nombrePages(octets), `document industriel${suffixe} : 4 pages`).toBe(4)
    if (!suffixe) etat.pdfTexte = await textePdf(octets)
  }
  expect(etat.pdfTexte).toMatch(/TRI sur 25 ans/)
  expect(etat.pdfTexte).toMatch(/VAN/)
})

test('CIQ346 — lien public : synthese_ci.argent = celui du PDF, aucune clé P90', async ({ request }) => {
  expect(etat.devisId, 'le test de création doit précéder').toBeTruthy()
  const lien = await lireJson(await request.post(`${API}/ventes/devis/${etat.devisId}/share-link/`,
    { data: {} }), 'lien de partage')
  etat.token = lien.token
  expect(etat.token, 'jeton public de la proposition').toBeTruthy()
  const data = await lireJson(await request.get(`${API}/ventes/proposal/${etat.token}/`), 'proposition publique')
  const synthese = data.synthese_ci
  expect(synthese, 'synthese_ci').toBeTruthy()
  expect(synthese.argent, 'synthese_ci.argent').toBeTruthy()
  const p90 = clesProfondes(synthese).filter((k) => /p90/i.test(k))
  expect(p90, 'aucune clé P90 servie').toEqual([])
  // La VAN servie est celle imprimée (chiffres comparés sans séparateurs).
  const van = synthese.argent.van_mad
  expect(typeof van, 'synthese_ci.argent.van_mad (taux déclaré)').toBe('number')
  const chiffresPdf = etat.pdfTexte.replace(/[\s.,]/g, '')
  expect(chiffresPdf, `VAN ${van} MAD imprimée`).toContain(String(Math.round(Math.abs(van))))
})

test('CIQ346 — page /proposition : ni « heures les plus chères » ni « CBAM », FR et AR (WEB_URL requis)', async ({ page }) => {
  test.skip(!process.env.WEB_URL, 'WEB_URL (apps/web en dev) non fourni : captures non prises')
  expect(etat.token, 'le test du lien doit précéder').toBeTruthy()
  for (const langue of ['fr', 'ar']) {
    await page.goto(`${process.env.WEB_URL}/proposition/${etat.token}`)
    await page.locator(`#prop-lang-${langue}`).click()
    await expect(page.locator('body')).toContainText(/\S/, { timeout: 30_000 })
    if (langue === 'fr') {
      await expect(page.locator('body')).not.toContainText(/heures les plus chères/i)
      await expect(page.locator('body')).not.toContainText(/CBAM/)
    }
    await test.info().attach(`ciq346-proposition-${langue}`, {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  }
})

test('CIQ346 — signature entreprise (raison sociale, qualité, ICE) → copie signée complète', async ({ request }) => {
  test.setTimeout(180_000)
  expect(etat.token, 'le test du lien doit précéder').toBeTruthy()
  const accepte = await lireJson(await request.post(`${API}/ventes/proposal/${etat.token}/accept/`, {
    data: {
      nom: 'Nadia E2E', option: '', consent_esign: true,
      signed_at_client: new Date().toISOString(), on_behalf_of: '', entreprise: ENTREPRISE,
    },
  }), 'acceptation entreprise')
  expect(accepte.statut).toBe('accepte')
  expect(accepte.entreprise).toEqual(ENTREPRISE)
  const signe = await request.get(`${API}/ventes/devis/${etat.devisId}/proposal/?pdf_mode=full`)
  expect(signe.status(), 'PDF signé').toBe(200)
  const texte = await textePdf(await signe.body())
  for (const valeur of [...Object.values(ENTREPRISE), 'Nadia E2E']) {
    expect(texte, `copie signée : « ${valeur} »`).toContain(valeur)
  }
})
