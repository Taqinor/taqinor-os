// AGR624 — ALLER-RETOUR EN DIRECT du parcours chantier pompage (clôture de la
// vague AGR6, leçon QJR5 : « déployable ≠ vert »). Pile locale `seed_demo`
// + `seed_catalogue` (pompes OSP à courbe), aucun mock réseau :
//
//   1. devis agricole ACCEPTÉ (pompe à courbe chiffrée, entrées v2) ;
//   2. chantier agricole créé depuis le devis : régime « déclaration hors
//      réseau », checklist « Pompage solaire » à 13 étapes, plan d'interventions ;
//   3. seuil d'écart de recette saisi en Paramètres (réglage société) ;
//   4. recette pompage saisie SUR L'ÉCRAN du chantier : écart affiché ; hors
//      seuil → commentaire exigé (400 sans, 200 avec) ;
//   5. PV de réception PDF : les mesures et la mention « art. 3 » (texte extrait
//      du PDF par pdfjs-dist) ;
//   6. portail client (compte provisionné) : il voit la recette et saisit un
//      relevé m³ ;
//   7. la fiche équipement SAV montre ce relevé et sa moyenne.
//
// PRÉREQUIS D'ENVIRONNEMENT (le spec le dit plutôt que de simuler) :
//   • `manage.py seed_catalogue` joué (sinon : pas de pompe à courbe → échec nommé) ;
//   • le mot de passe du compte portail est posé par `manage.py shell` dans le
//     conteneur Django (`E2E_DJANGO_EXEC`, défaut « docker compose exec -T
//     django_core ») — le mot de passe temporaire réel part par email.
// Le prix de la pompe et le seuil société sont RESTAURÉS en afterAll (base
// partagée, workers: 1). Le job `e2e-shard` de la CI énumère ses specs : ce
// fichier n'y est pas encore (décision de budget CI, voir i18n-quote-journey).
import { execFileSync } from 'node:child_process'
import { test, expect } from '@playwright/test'
import { connecterPortail, ouvrirJalonsChantier } from './helpers.js'

const API = '/api/django'
const MOT_DE_PASSE_PORTAIL = 'Portail-E2E-2026!'

const nettoyage = { devis: [], chantiers: [], equipements: [], prixPompe: null, seuil: undefined }
const etat = {}

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}
const liste = (corps) => (Array.isArray(corps) ? corps : (corps.results || []))

/** Texte brut d'un PDF (pdfjs-dist, déjà une dépendance du frontend). */
async function textePdf(octets) {
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  const doc = await pdfjs.getDocument({
    data: new Uint8Array(octets), useSystemFonts: true, disableFontFace: true,
  }).promise
  let texte = ''
  for (let i = 1; i <= doc.numPages; i += 1) {
    const page = await doc.getPage(i)
    const contenu = await page.getTextContent()
    texte += `${contenu.items.map((it) => it.str).join(' ')}\n`
  }
  return texte
}

/** Pose le mot de passe du compte portail dans le conteneur Django local. */
function poserMotDePassePortail(username) {
  const [cmd, ...args] = (process.env.E2E_DJANGO_EXEC || 'docker compose exec -T django_core').split(' ')
  const code = 'from django.contrib.auth import get_user_model as g; '
    + `u = g().objects.get(username=${JSON.stringify(username)}); `
    + `u.set_password(${JSON.stringify(MOT_DE_PASSE_PORTAIL)}); u.save()`
  execFileSync(cmd, [...args, 'python', 'manage.py', 'shell', '-c', code], { stdio: 'pipe' })
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(nettoyage.equipements.map((id) =>
    request.delete(`${API}/sav/equipements/${id}/`).catch(() => null)))
  await Promise.all(nettoyage.chantiers.map((id) =>
    request.delete(`${API}/installations/chantiers/${id}/`).catch(() => null)))
  await Promise.all(nettoyage.devis.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  if (nettoyage.prixPompe) {
    await request.patch(`${API}/stock/produits/${nettoyage.prixPompe.id}/`,
      { data: { prix_vente: nettoyage.prixPompe.avant } }).catch(() => null)
  }
  if (nettoyage.seuil !== undefined) {
    await request.patch(`${API}/parametres/update/`,
      { data: { recette_pompage_ecart_max_pct: nettoyage.seuil } }).catch(() => null)
  }
})

test('AGR624 — devis agricole accepté → chantier hors réseau, checklist 13 étapes, plan', async ({ request }) => {
  test.setTimeout(180_000)
  // Une pompe à courbe du catalogue, chiffrée le temps du test.
  const produits = liste(await json(await request.get(
    `${API}/stock/produits/?search=OSP&page_size=100`), 'produits OSP'))
  const pompe = produits.find((p) => p.courbe_pompe && Object.keys(p.courbe_pompe).length)
  expect(pompe, 'aucune pompe à courbe au catalogue — jouer `manage.py seed_catalogue`').toBeTruthy()
  if (!(parseFloat(pompe.prix_vente) > 0)) {
    nettoyage.prixPompe = { id: pompe.id, avant: pompe.prix_vente ?? null }
    await json(await request.patch(`${API}/stock/produits/${pompe.id}/`,
      { data: { prix_vente: '15000.00' } }), 'prix de la pompe')
  }
  const clients = liste(await json(await request.get(`${API}/crm/clients/`), 'clients'))
  expect(clients.length, 'seed_demo doit fournir un client').toBeGreaterThan(0)
  etat.client = clients[0]

  const devis = await json(await request.post(`${API}/ventes/devis/`, {
    data: { client: etat.client.id, taux_tva: '20.00', mode_installation: 'agricole' },
  }), 'création du devis')
  nettoyage.devis.push(devis.id)
  etat.devisId = devis.id
  // Entrées v2 SEULES (le serveur calcule la promesse du devis — AGR123).
  await json(await request.post(`${API}/ventes/devis/${devis.id}/replace-lines/`, {
    data: {
      lignes: [{
        produit: pompe.id, designation: pompe.nom, quantite: '1.00',
        prix_unitaire: '12500.00', remise: '0.00', taux_tva: '20.00',
        type_ligne: 'produit', ordre: 0,
      }],
      etude_params: {
        mode_pompe: 'neuve',
        besoin: { mode: 'volume_declare', volume_m3_jour: 60, mois_pointe: 7, cultures: [], region: null },
        source: { niveau_dynamique_m: 40, niveau_statique_m: 32 },
        hmt_entrees: { saisie_m: 45 },
        alim: 'tri', type_pompe: 'immergee', options_cochees: [], taille: 'recommandee',
      },
    },
  }), 'lignes et étude du devis')
  await json(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, {
    data: { nom: 'Exploitant E2E' },
  }), 'acceptation du devis')

  const chantier = await json(await request.post(`${API}/installations/chantiers/creer-depuis-devis/`,
    { data: { devis: devis.id } }), 'chantier depuis le devis')
  nettoyage.chantiers.push(chantier.id)
  etat.chantierId = chantier.id
  expect(chantier.regime_8221).toBe('declaration_hors_reseau')
  expect(chantier.raccordement_reseau).toBe('hors_reseau')

  // L'action `checklist` rend `{installation, items, completion}` (N4), jamais
  // une liste paginée : lire `items` (comme les specs CIQ650 / CIQ665).
  const checklist = (await json(await request.get(
    `${API}/installations/chantiers/${chantier.id}/checklist/`), 'checklist')).items || []
  expect(checklist.length, 'checklist « Pompage solaire »').toBe(13)
  expect(checklist.some((e) => /onduleur/i.test(e.libelle || e.designation || '')),
    'aucune étape « Onduleur raccordé » en pompage').toBeFalsy()

  await json(await request.post(
    `${API}/installations/chantiers/${chantier.id}/creer-interventions-standard/`, { data: {} }),
  "plan d'interventions")
  const detail = await json(await request.get(
    `${API}/installations/chantiers/${chantier.id}/`), 'chantier')
  expect(detail.nb_interventions, "plan d'interventions semé").toBeGreaterThan(0)
})

test('AGR624 — seuil saisi en Paramètres, recette saisie à l’écran, commentaire exigé hors seuil', async ({ page, request }) => {
  test.setTimeout(180_000)
  const profil = await json(await request.get(`${API}/parametres/`), 'paramètres')
  nettoyage.seuil = profil.recette_pompage_ecart_max_pct ?? null
  await page.goto('/parametres')
  // Le champ AGR607 vit dans l'onglet « Avancé » (AvanceSection), jamais dans
  // l'onglet « Société » ouvert par défaut.
  await page.getByRole('navigation', { name: 'Sections des paramètres' })
    .getByRole('button', { name: 'Avancé', exact: true }).click({ timeout: 30_000 })
  await expect(page.locator('#pe-ecart-recette')).toBeVisible({ timeout: 30_000 })
  await page.locator('#pe-ecart-recette').fill('1')
  await page.getByRole('button', { name: /Enregistrer/ }).first().click()
  await expect.poll(async () => (await json(await request.get(`${API}/parametres/`),
    'paramètres relus')).recette_pompage_ecart_max_pct, { timeout: 20_000 }).toBeTruthy()

  // La promesse du devis est FIGÉE dans la fiche : on mesure moitié moins.
  const ouverture = await json(await request.post(
    `${API}/installations/chantiers/${etat.chantierId}/recette-pompage/`, { data: {} }),
  'ouverture de la fiche de recette')
  const promis = ouverture.record?.comparaison?.promesse?.debit_hmt_m3h
  expect(promis, 'le devis doit porter un débit promis (pompe à courbe chiffrée)').toBeGreaterThan(0)
  etat.mesure = Math.round((promis / 2) * 10) / 10

  // APX25 : la fiche de recette vit dans l'onglet « Jalons & gates ».
  await ouvrirJalonsChantier(page, etat.chantierId)
  await page.getByRole('button', { name: /fiche de recette/ }).first().click()
  await page.locator('#recette-pompage-hmt_mesuree_m').fill('45')
  await page.locator('#recette-pompage-debit_mesure_m3h').fill(String(etat.mesure))
  // AGR609 (d) : l'écart est jugé sur l'état APRÈS l'écriture — une mesure hors
  // seuil SANS commentaire est refusée dès cet enregistrement (400 FR), et le
  // message affiché sous le champ porte l'écart chiffré.
  await page.getByRole('button', { name: 'Enregistrer la fiche' }).click()
  const erreur = page.getByTestId('erreur-commentaire_ecart')
  await expect(erreur).toBeVisible({ timeout: 20_000 })
  await expect(erreur).toContainText('%')
  await page.locator('#recette-pompage-commentaire_ecart').fill('Vanne de refoulement partiellement fermée à l’essai.')
  await page.getByRole('button', { name: 'Enregistrer la fiche' }).click()
  await expect(erreur).toHaveCount(0, { timeout: 20_000 })
  // Enregistrée : l'écart servi est affiché, hors seuil ⇒ commentaire obligatoire.
  await expect(page.getByTestId('cmp-ecart')).toContainText('%', { timeout: 20_000 })
  await expect(page.getByTestId('commentaire-requis')).toBeVisible()

  const relue = await json(await request.get(
    `${API}/installations/chantiers/${etat.chantierId}/recette-pompage/`), 'recette relue')
  expect(relue.record.debit_mesure_m3h).toBe(etat.mesure)
  expect(relue.record.comparaison.hors_seuil).toBe(true)
  expect(relue.record.commentaire_ecart).toMatch(/Vanne/)
})

test('AGR624 — PV de réception PDF : mesures et mention art. 3', async ({ request }) => {
  const pdf = await request.get(`${API}/documents/chantiers/${etat.chantierId}/pv-reception/`)
  expect(pdf.status(), 'PV de réception').toBe(200)
  const texte = await textePdf(await pdf.body())
  expect(texte).toMatch(/IEC 62253/)
  expect(texte).toMatch(/art\. ?3/)
  // La mesure saisie est imprimée telle quelle (virgule ou point décimal).
  const mesure = String(etat.mesure).replace('.', '[.,]')
  expect(texte).toMatch(new RegExp(`(^|[^\\d])${mesure}([^\\d]|$)`))
})

test('AGR624 — portail client : recette visible, relevé m³ saisi ; la fiche SAV le montre', async ({ playwright, request }) => {
  test.setTimeout(240_000)
  const baseURL = test.info().project.use.baseURL
  // Le compte portail du client : réutilisé s'il existe, créé sinon.
  const existants = liste(await json(await request.get(`${API}/portail/comptes-portail/`),
    'comptes portail'))
  const compte = existants.find((c) => c.client === etat.client.id)
    ?? await json(await request.post(`${API}/portail/comptes-portail/`,
      { data: { client: etat.client.id } }), 'compte portail du client')
  const prov = await json(await request.post(
    `${API}/portail/comptes-portail/${compte.id}/provisionner-acces/`, { data: {} }), 'accès portail')

  // Un équipement SAV (la pompe) rattaché au chantier, pour porter les relevés.
  const produits = liste(await json(await request.get(
    `${API}/stock/produits/?search=OSP&page_size=5`), 'pompe'))
  const eq = await json(await request.post(`${API}/sav/equipements/`, {
    data: { produit: produits[0].id, installation: etat.chantierId,
      numero_serie: `E2E-AGR624-${Date.now()}`, date_pose: new Date().toISOString().slice(0, 10) },
  }), 'équipement SAV')
  nettoyage.equipements.push(eq.id)

  try {
    poserMotDePassePortail(prov.username)
  } catch (err) {
    throw new Error(`mot de passe du compte portail non posé (E2E_DJANGO_EXEC) : ${err.message}`)
  }
  // AUD139 : le mot de passe temporaire doit être changé avant toute route portail.
  const portail = await connecterPortail(playwright, baseURL, prov.username, MOT_DE_PASSE_PORTAIL)
  try {

    const detail = await json(await portail.get(`${API}/portail/mes-chantiers/${etat.chantierId}/`),
      'chantier côté client')
    expect(detail.recette_pompage, 'le client voit la recette').toBeTruthy()
    expect(detail.recette_pompage.debit_mesure_m3h).toBe(etat.mesure)
    expect(JSON.stringify(detail)).not.toMatch(/instrument|prix_achat/)

    const releves = await json(await portail.get(
      `${API}/portail/mes-chantiers/${etat.chantierId}/releves/`), 'relevés portail')
    const cible = releves.equipements.find((e) => (e.types_admis || []).includes('m3'))
    expect(cible, 'un équipement admettant les relevés m³').toBeTruthy()
    const aujourdhui = new Date().toISOString().slice(0, 10)
    const hier = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)
    await json(await portail.post(`${API}/portail/mes-chantiers/${etat.chantierId}/releves/`,
      { data: { equipement: cible.id, type: 'm3', valeur: '100', date: hier } }), 'relevé 1')
    await json(await portail.post(`${API}/portail/mes-chantiers/${etat.chantierId}/releves/`,
      { data: { equipement: cible.id, type: 'm3', valeur: '160', date: aujourdhui } }), 'relevé 2')
    const recul = await portail.post(`${API}/portail/mes-chantiers/${etat.chantierId}/releves/`,
      { data: { equipement: cible.id, type: 'm3', valeur: '50', date: aujourdhui } })
    expect(recul.status(), 'un compteur ne recule pas').toBe(400)

    // La fiche équipement SAV (côté ERP) montre ce relevé et sa moyenne.
    const cote = liste(await json(await request.get(
      `${API}/sav/equipements/${cible.id}/releves-compteur/`), 'relevés SAV'))
    const dernier = cote.find((r) => r.type === 'm3' && Number(r.valeur) === 160)
    expect(dernier, 'le relevé du client est dans la fiche équipement').toBeTruthy()
    expect(dernier.moyenne_jour_depuis_precedent).toBeCloseTo(60, 0)
  } finally {
    await portail.dispose()
  }
})
