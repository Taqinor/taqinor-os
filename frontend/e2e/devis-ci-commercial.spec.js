// CIQ334 — CLÔTURE DE LA VAGUE COMMERCIALE : aller-retour EN DIRECT d'un devis
// commercial (hôtel, BT), profil DÉCLARÉ compris (leçon QJR5 « déployable ≠
// vert » : la preuve se fait en direct, pile locale `seed_demo`, aucun mock).
//
//   1. création depuis `/ventes/devis/nouveau` : marché Commercial, catégorie
//      Hôtel, 12 mois de consommation, rythme déclaré — FERMÉ LE DIMANCHE
//      (lundi → samedi ouverts) et FERMETURE du 01/08 au 31/08 —, Auto-remplir
//      (moteur serveur), « Créer le devis » ; puis rouvrir (`?edit=`) et
//      ré-enregistrer sans rien toucher ⇒ `etude_params` IDENTIQUE ;
//   2. PDF client (`/proposal`, le chemin unique de `generer-pdf`, règle #4) :
//      3 pages, avec ou sans `include_etude` ; les taux d'autoconsommation et
//      de couverture imprimés = ceux de la DERNIÈRE réponse `etude-ci/preview`,
//      et le dimanche + août ne sont pas valorisés (surplus non valorisé > 0
//      au mois 8 du bilan) ;
//   3. lien public → `GET /api/django/ventes/proposal/<token>/` : `synthese_ci`
//      présent et égal à la synthèse imprimée, `quote.eco_s_ann` nul,
//      `expires_at` du lien ≥ fin de la validité du devis (CIQ511) ;
//   4. (optionnel, `WEB_URL` = apps/web en dev) /proposition capturée en FR et
//      en AR, jointe au rapport ;
//   5. signature en ligne (`POST …/proposal/<token>/accept/`, contrat
//      `acceptation_entreprise.json`) SANS ICE → refus 400 qui NOMME le champ ;
//      AVEC l'ICE → devis accepté, PDF signé portant raison sociale, qualité
//      et ICE.
// Base partagée, workers: 1 : nettoyage best-effort en afterAll.
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, KWH_COMMERCIAL, choisirMarche, declarerProfilCi, executerDansDjango,
  lireJson, listeDe, textePdf,
} from './helpers'

const ANNEE = new Date().getFullYear()
const ENTREPRISE = {
  raison_sociale: 'Hôtel E2E Atlas SARL',
  signataire_qualite: 'Directeur général',
  // ICE FACTICE de 15 chiffres (le même que l'exemple du contrat).
  ice: '000000000000000',
}
const devisIds = []
const etat = { devisId: null, apercu: null, token: null, pdfTexte: null }

/** Nombre de pages d'un PDF, lu sur ses objets /Type /Page (pas /Pages). */
function nombrePages(octets) {
  const texte = Buffer.from(octets).toString('latin1')
  return (texte.match(/\/Type\s*\/Page(?![s\w])/g) || []).length
}

/** Un pourcentage (72.8) est-il imprimé, au format FR ou point, arrondi ou non ? */
function pctImprime(texte, pct) {
  const formes = new Set([pct.toFixed(1).replace('.', ','), pct.toFixed(1), String(Math.round(pct))])
  return [...formes].some((f) => new RegExp(`(^|[^\\d,.])${f.replace('.', '\\.')}\\s?%`).test(texte))
}

async function premierLead(request) {
  const liste = listeDe(await lireJson(await request.get(`${API}/crm/leads/`), 'leads'))
  expect(liste.length, 'seed_demo doit fournir au moins un lead').toBeGreaterThan(0)
  return liste.find((l) => l.type_installation === 'commercial') || liste[0]
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('CIQ334 — créer (hôtel, dimanche fermé, août fermé), rouvrir, ré-enregistrer : etude_params identique', async ({ page, request }) => {
  test.setTimeout(300_000)
  // La DERNIÈRE réponse de l'aperçu C&I serveur (aucun calcul local).
  page.on('response', async (r) => {
    if (r.request().method() === 'POST' && r.ok()
      && /\/ventes\/etude-ci\/preview\/$/.test(new URL(r.url()).pathname)) {
      try { etat.apercu = await r.json() } catch { /* corps illisible : ignoré */ }
    }
  })
  const lead = await premierLead(request)
  await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await choisirMarche(page, /Commercial/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()

  // Catégorie commerciale : Hôtel.
  await page.locator('div.grid', { has: page.getByText('Catégorie commerciale', { exact: true }) })
    .getByRole('combobox').first().click()
  await page.getByRole('option', { name: /Hôtel/ }).click()

  for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH_COMMERCIAL[i]))
  // Lundi → samedi ouverts (dimanche FERMÉ), 8 h → 18 h, BT patenté.
  await declarerProfilCi(page)
  await expect(page.getByTestId('gen-ci-jour-6')).not.toBeChecked()
  // Fermeture annuelle du 01/08 au 31/08.
  await page.getByTestId('ci-fermetures').getByRole('button', { name: 'Ajouter une fermeture' }).click()
  await page.getByLabel('Fermeture 1 du').fill(`${ANNEE}-08-01`)
  await page.getByLabel('Fermeture 1 au').fill(`${ANNEE}-08-31`)
  await page.getByLabel('Fermeture 1 motif').fill('Fermeture annuelle')

  await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
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
  expect(avant.mode_installation).toBe('commercial')
  expect(avant.etude_params.categorie_commerciale).toBe('hotel')

  // Rouvrir, ré-enregistrer sans rien toucher.
  await page.goto(`/ventes/devis/nouveau?edit=${etat.devisId}`)
  await expect(page.getByTestId('ci-profil')).toBeVisible({ timeout: 45_000 })
  await expect(page.getByLabel('Fermeture 1 du')).toHaveValue(`${ANNEE}-08-01`)
  const sauvegarde = page.waitForResponse((r) => r.request().method() !== 'GET'
    && new RegExp(`/ventes/devis/${etat.devisId}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Enregistrer les modifications/ }).click()
  await sauvegarde
  await expect.poll(async () => {
    const relu = await lireJson(await request.get(`${API}/ventes/devis/${etat.devisId}/`), 'devis relu')
    return relu.etude_params
  }, { timeout: 30_000, message: 'etude_params identique après réouverture' }).toEqual(avant.etude_params)
  expect(etat.apercu, 'au moins une réponse etude-ci/preview').toBeTruthy()
})

test('CIQ334 — PDF : 3 pages avec ou sans étude, taux = dernier aperçu, dimanche et août non valorisés', async ({ request }) => {
  test.setTimeout(180_000)
  expect(etat.devisId, 'le test de création doit précéder').toBeTruthy()
  for (const suffixe of ['', '&include_etude=1']) {
    const pdf = await request.get(`${API}/ventes/devis/${etat.devisId}/proposal/?pdf_mode=full${suffixe}`)
    expect(pdf.status(), `/proposal${suffixe}`).toBe(200)
    const octets = await pdf.body()
    expect(nombrePages(octets), `document commercial${suffixe} : 3 pages`).toBe(3)
    if (!suffixe) etat.pdfTexte = await textePdf(octets)
  }
  const bilan = etat.apercu.bilan
  const autoconso = Math.round(bilan.taux_autoconso * 1000) / 10
  const couverture = Math.round(bilan.taux_couverture * 1000) / 10
  expect(pctImprime(etat.pdfTexte, autoconso), `taux d'autoconsommation ${autoconso} % imprimé`).toBeTruthy()
  expect(pctImprime(etat.pdfTexte, couverture), `taux de couverture ${couverture} % imprimé`).toBeTruthy()
  const aout = (bilan.par_mois || []).find((m) => Number(m.mois) === 8)
  expect(aout, 'bilan du mois 8').toBeTruthy()
  expect(Number(aout.non_valorise_kwh ?? aout.surplus_kwh), 'août : surplus non valorisé > 0').toBeGreaterThan(0)
})

test('CIQ334 — lien public : synthese_ci = synthèse imprimée, eco_s_ann nul, lien ≥ validité', async ({ request }) => {
  expect(etat.devisId, 'le test de création doit précéder').toBeTruthy()
  const lien = await lireJson(await request.post(`${API}/ventes/devis/${etat.devisId}/share-link/`,
    { data: {} }), 'lien de partage')
  etat.token = lien.token
  expect(etat.token, 'jeton public de la proposition').toBeTruthy()
  const data = await lireJson(await request.get(`${API}/ventes/proposal/${etat.token}/`), 'proposition publique')
  expect(data.synthese_ci, 'synthese_ci').toBeTruthy()
  expect(data.quote?.eco_s_ann ?? null, 'quote.eco_s_ann').toBeNull()
  const energie = data.synthese_ci.energie || {}
  for (const cle of ['taux_autoconso_pct', 'taux_couverture_pct']) {
    expect(typeof energie[cle], `synthese_ci.energie.${cle}`).toBe('number')
    expect(pctImprime(etat.pdfTexte, energie[cle]), `${cle} = ${energie[cle]} % imprimé au PDF`).toBeTruthy()
  }
  const sortie = executerDansDjango(
    'import json; from apps.ventes.models import ShareLink; '
    + `l = ShareLink.objects.get(token=${JSON.stringify(etat.token)}); `
    + 'print(json.dumps({"expires_at": l.expires_at.date().isoformat(), '
    + '"date_validite": l.devis.date_validite.isoformat() if l.devis.date_validite else None}))')
  const { expires_at: expire, date_validite: validite } = JSON.parse(sortie.trim().split('\n').at(-1))
  expect(validite, 'date de validité du devis').toBeTruthy()
  expect(expire >= validite, `lien (${expire}) ≥ validité (${validite})`).toBeTruthy()
})

test('CIQ334 — page /proposition en FR et en AR (apps/web en dev, WEB_URL requis)', async ({ page }) => {
  test.skip(!process.env.WEB_URL, 'WEB_URL (apps/web en dev) non fourni : captures non prises')
  expect(etat.token, 'le test du lien doit précéder').toBeTruthy()
  for (const langue of ['fr', 'ar']) {
    await page.goto(`${process.env.WEB_URL}/proposition/${etat.token}`)
    await page.locator(`#prop-lang-${langue}`).click()
    await expect(page.locator('body')).toContainText(/\S/, { timeout: 30_000 })
    await test.info().attach(`ciq334-proposition-${langue}`, {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  }
})

test('CIQ334 — signature entreprise : sans ICE refusée en nommant le champ, avec ICE acceptée et imprimée', async ({ request }) => {
  test.setTimeout(180_000)
  expect(etat.token, 'le test du lien doit précéder').toBeTruthy()
  const corps = (entreprise) => ({
    nom: 'Karim E2E', option: '', consent_esign: true,
    signed_at_client: new Date().toISOString(), on_behalf_of: '', entreprise,
  })
  const sansIce = await request.post(`${API}/ventes/proposal/${etat.token}/accept/`,
    { data: corps({ ...ENTREPRISE, ice: '' }) })
  expect(sansIce.status(), 'acceptation sans ICE').toBe(400)
  expect((await sansIce.json()).champ, 'le refus nomme le champ').toBe('entreprise.ice')

  const accepte = await lireJson(await request.post(`${API}/ventes/proposal/${etat.token}/accept/`,
    { data: corps(ENTREPRISE) }), 'acceptation avec ICE')
  expect(accepte.statut).toBe('accepte')
  expect(accepte.entreprise).toEqual(ENTREPRISE)

  const signe = await request.get(`${API}/ventes/devis/${etat.devisId}/proposal/?pdf_mode=full`)
  expect(signe.status(), 'PDF signé').toBe(200)
  const texte = await textePdf(await signe.body())
  for (const valeur of Object.values(ENTREPRISE)) {
    expect(texte, `PDF signé : « ${valeur} »`).toContain(valeur)
  }
})
