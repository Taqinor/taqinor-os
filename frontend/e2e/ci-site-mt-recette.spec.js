// CIQ665 — ALLER-RETOUR EN DIRECT du parcours site MT : visite avec supplément
// MT → chantier MT → recette avec découplage exigé.
//
// Pile locale `seed_demo`, AUCUN mock réseau sur les écrans testés. Six temps :
//   1. lead industriel : la fiche dit « AVANT le devis », la visite `ci` se planifie
//      à l'écran ;
//   2. niveau constaté MT → le supplément MT est servi ; le cos φ exige sa source
//      (400 qui nomme le champ), une cellule est « non relevée — à faire par un
//      électricien » ; terminer, valider : le lead porte tension, puissance, cos φ ;
//   3. devis industriel accepté (vrai générateur, PDF de 4 pages) → chantier MT :
//      template « Site professionnel (MT) », régime d'accord, dossier 82-21 ouvert ;
//      le schéma unifilaire d'un étage MT dessine le découplage « à confirmer » ;
//   4. réglages imposés par l'étude saisis à l'écran du dossier réglementaire ;
//   5. recette : découplage NON saisi → « en cours » ; saisi « conforme » à
//      l'écran → « conforme » ; « non conforme » → « non conforme ».
//
// PRÉREQUIS : aucun accès shell ici (les documents de sécurité ne sont pas exigés
// par ce parcours, qui s'arrête à la recette). Nettoyage best-effort en afterAll
// (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, lireJson, listeDe, telephoneFixeUnique, isoDansJours, uniq,
  creerDevisIndustrielDepuisLead, mesuresContratVisite, planifierVisiteDepuisLead,
  remplirVisiteCi, nombrePagesPdf, ouvrirJalonsChantier,
} from './helpers.js'

const jeton = String(Date.now()).slice(-9)
const societe = `Usine Atlas ${jeton}`
const email = `direction-${jeton}@usine-atlas.example`
const ESSAIS = [
  'doc_dossier_ok', 'doc_schema_ok', 'doc_datasheets_ok', 'visuel_structure_ok',
  'visuel_cablage_ok', 'visuel_terre_ok', 'continuite_terre_ok', 'polarite_ok',
  'isolement_ok', 'performance_ok', 'securite_coupure_ok', 'securite_signalisation_ok',
]

const leadIds = []
const devisIds = []
const chantierIds = []
const clientIds = []
const etat = {}

const chantierUrl = () => `${API}/installations/chantiers/${etat.chantierId}/`
const dossiersDuDevis = async (request) => listeDe(await lireJson(
  await request.get(`${API}/ventes/dossiers-reglementaires/?devis=${etat.devisId}`), 'dossiers du devis'))
const fichesDuChantier = async (request) => listeDe(await lireJson(await request.get(
  `${API}/installations/recettes-commissioning/?installation=${etat.chantierId}`), 'fiche de recette'))

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(chantierIds.map((id) =>
    request.delete(`${API}/installations/chantiers/${id}/`).catch(() => null)))
  await Promise.all(devisIds.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  await Promise.all(leadIds.map((id) => request.delete(`${API}/crm/leads/${id}/`).catch(() => null)))
  await Promise.all(clientIds.map((id) => request.delete(`${API}/crm/clients/${id}/`).catch(() => null)))
})

test.describe('CIQ665 — site MT, de la visite à la recette', () => {
  test('1. lead industriel : « AVANT le devis », visite ci planifiée à l’écran', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    etat.lead = await lireJson(await request.post(`${API}/crm/leads/`, {
      data: {
        nom: uniq('Direction Usine E2E'), societe, ville: 'Kenitra',
        telephone: telephoneFixeUnique(), email, type_installation: 'industriel',
        facture_hiver: '60000', langue_preferee: 'fr',
      },
    }), 'création du lead industriel')
    leadIds.push(etat.lead.id)

    const avertissement = await planifierVisiteDepuisLead(page, etat.lead.id)
    expect(avertissement).toContain('AVANT le devis')
    expect(avertissement).not.toContain('exception')
    await testInfo.attach('ciq665-visite-planifiee', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    const visites = (await lireJson(
      await request.get(`${API}/crm/leads/${etat.lead.id}/visites/`), 'visites du lead')).visites
    expect(visites.length).toBeGreaterThan(0)
    etat.visiteId = visites[0].id
    const visite = await lireJson(await request.get(`${API}/visites/visites/${etat.visiteId}/`), 'visite')
    expect(visite.gabarit).toBe('ci')
  })

  test('2. niveau MT constaté : supplément servi, cos φ exige sa source, cellule « non relevée » ; validée', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    const mt = mesuresContratVisite('exemple_ci_mt')
    expect(mt.comptage.niveau_tension_constate).toBe('mt')
    const urlMesures = `${API}/visites/visites/${etat.visiteId}/mesures/`

    // Avant le niveau MT, le supplément n'existe pas : catégorie inconnue.
    const avant = await request.patch(urlMesures,
      { data: { categorie: 'poste_mt', valeurs: { tgbt_jeu_de_barres: 'cuivre' } } })
    expect(avant.status(), 'supplément MT absent tant que le niveau n’est pas MT').toBe(400)
    await lireJson(await request.patch(urlMesures,
      { data: { categorie: 'comptage', valeurs: mt.comptage } }), 'comptage MT')

    // Le cos φ constaté sans sa source est refusé, l'erreur NOMME le champ.
    const sansSource = await request.patch(urlMesures,
      { data: { categorie: 'factures_mt', valeurs: { cos_phi_constate: 0.92 } } })
    expect(sansSource.status(), 'cos φ sans source').toBe(400)
    expect(Object.keys((await sansSource.json()).erreurs || {}), 'l’erreur nomme la source du cos φ')
      .toContain('source_cos_phi')

    const posteSansCellule = { ...mt.poste_mt }
    delete posteSansCellule.cellule_protection
    const mesures = {
      ...mt,
      poste_mt: { ...posteSansCellule, _non_releves: { cellule_protection: 'a_faire_par_electricien' } },
      factures_mt: { ...mt.factures_mt, cos_phi_constate: 0.92, source_cos_phi: 'facture' },
    }
    const complete = await remplirVisiteCi(request, etat.visiteId, mesures)
    expect(complete.completude?.manquants, 'rien ne manque pour terminer').toEqual([])
    expect(complete._non_releves['poste_mt.cellule_protection'],
      'cellule « non relevée — à faire par un électricien »').toBe('a_faire_par_electricien')
    expect(complete.checklist.map((b) => b.categorie), 'supplément MT servi').toContain('poste_mt')

    await page.goto(`/visites/${etat.visiteId}`)
    await expect(page.getByText('Visite technique — site professionnel').first())
      .toBeVisible({ timeout: 30_000 })
    await testInfo.attach('ciq665-wizard-mt', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })

    await lireJson(await request.post(`${API}/visites/visites/${etat.visiteId}/terminer/`,
      { data: {} }), 'terminer')
    const validee = await lireJson(await request.post(`${API}/visites/visites/${etat.visiteId}/valider/`,
      { data: {} }), 'valider')
    expect(validee.statut).toBe('validee')

    const lead = await lireJson(await request.get(`${API}/crm/leads/${etat.lead.id}/`), 'lead relu')
    expect(lead.tension_raccordement, 'niveau MT mesuré').toBe('mt')
    expect(lead.tension_source).toBe('mesure_visite')
    expect(Number(lead.compteur_puissance_kva)).toBe(250)
    expect(Number(lead.cos_phi)).toBeCloseTo(0.92, 2)
    expect(lead.cos_phi_source).toBe('mesure_visite')
  })

  test('3. devis industriel accepté (PDF de 4 pages) → chantier MT, template MT, régime d’accord, dossier ouvert', async ({ page, request }, testInfo) => {
    test.setTimeout(300_000)
    etat.devisId = await creerDevisIndustrielDepuisLead(page, etat.lead.id, { tension: 'mt' })
    devisIds.push(etat.devisId)
    const pdf = await request.get(`${API}/ventes/devis/${etat.devisId}/proposal/?pdf_mode=full`)
    expect(pdf.status(), '/proposal').toBe(200)
    expect(await nombrePagesPdf(await pdf.body()), 'document industriel : 4 pages').toBe(4)

    await lireJson(await request.post(`${API}/ventes/devis/${etat.devisId}/accepter/`,
      { data: { nom: 'Directeur E2E' } }), 'acceptation du devis')
    const chantier = await lireJson(await request.post(`${API}/installations/chantiers/creer-depuis-devis/`,
      { data: { devis: etat.devisId } }), 'chantier depuis le devis')
    etat.chantierId = chantier.id
    chantierIds.push(chantier.id)
    if (chantier.client) clientIds.push(chantier.client)
    expect(chantier.type_installation).toBe('industriel')
    expect(chantier.niveau_tension, 'niveau MT recopié du lead').toBe('mt')
    expect(chantier.regime_8221, 'régime d’accord de raccordement').toBe('accord_raccordement')

    const checklist = await lireJson(await request.get(`${chantierUrl()}checklist/`), 'checklist')
    const cles = checklist.items.map((e) => e.cle)
    for (const cle of ['poste_livraison_controle', 'reglages_protection_appliques',
      'essais_injection_decouplage', 'mise_sous_tension_distributeur']) {
      expect(cles, `template « Site professionnel (MT) » : ${cle}`).toContain(cle)
    }

    await expect.poll(async () => (await dossiersDuDevis(request)).length,
      { message: 'le chantier MT ouvre seul son dossier 82-21' }).toBe(1)
    const [dossier] = await dossiersDuDevis(request)
    etat.dossierId = dossier.id
    expect(dossier.chantier).toBe(chantier.id)
    expect(dossier.regime_8221).toBe('accord_raccordement')
    expect(dossier.statut).toBe('en_constitution')

    // Le schéma unifilaire d'un étage MT : découplage « à confirmer », jamais inventé.
    const mtSchema = await lireJson(await request.post(`${API}/ventes/schema-unifilaire/?format=json`, {
      data: { etage_mt: { transformateurs: [{ nb: 1, kva: 400 }], cellule: 'cellule existante', injection_limitee: true } },
    }), 'schéma unifilaire MT')
    expect(mtSchema.svg).toContain('Protection découplage')
    expect(mtSchema.svg).toContain('à confirmer')
    const btSchema = await lireJson(await request.post(`${API}/ventes/schema-unifilaire/?format=json`,
      { data: {} }), 'schéma unifilaire BT')
    expect(btSchema.svg, 'sans étage MT, aucun bloc de découplage').not.toContain('Protection découplage')

    // APX25 : le parcours vit dans l'onglet « Jalons & gates ». Le stepper
    // `ch6-gate-timeline` n'existe que si la société a AMORCÉ son cycle
    // (AUD313 : `POST /etapes-chantier/amorcer/`, Directeur) — état partagé
    // qu'un spec ne mute pas ; la fiche ouverte montre sa recette dans les deux cas.
    await ouvrirJalonsChantier(page, chantier.id)
    await testInfo.attach('ciq665-chantier-mt', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('4. réglages imposés par l’étude saisis à l’écran du dossier réglementaire', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    await page.goto('/ventes/dossiers-reglementaires')
    await page.getByText('File de travail', { exact: true }).first().click()
    const ligne = page.locator(`li[data-dossier-id="${etat.dossierId}"]`)
    await expect(ligne).toBeVisible({ timeout: 30_000 })
    await ligne.getByRole('button', { name: 'Détail 82-21' }).click()
    const detail = page.getByTestId('dossier-detail-8221')
    await expect(detail).toBeVisible()
    await expect(detail.getByText(/Source :/).first(), 'pièces sourcées').toBeVisible()
    await detail.locator('#dossier-etude_conclusion').selectOption('favorable')
    await detail.locator('#dossier-etude_reglages_imposes').selectOption('oui')
    await detail.locator('#dossier-convention_signee_le').fill(isoDansJours(0))
    await detail.getByRole('button', { name: 'Enregistrer le dossier' }).click()
    await expect.poll(async () => (await dossiersDuDevis(request))[0].resume?.etude?.reglages_imposes,
      { message: 'les réglages imposés sont lus dans le dossier' }).toBeTruthy()
    await testInfo.attach('ciq665-dossier-reglages', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('5. recette : découplage non saisi → en cours ; saisi conforme → conforme ; non conforme → non conforme', async ({ page, request }, testInfo) => {
    test.setTimeout(240_000)
    const ouverte = await lireJson(await request.post(`${chantierUrl()}recette/`, { data: {} }),
      'ouverture de la fiche de recette')
    const tousVrais = Object.fromEntries(ESSAIS.map((cle) => [cle, true]))
    const url = `${API}/installations/recettes-commissioning/${ouverte.id}/`
    const enCours = await lireJson(await request.patch(url, {
      data: { ...tousVrais, limitation_injection_etat: 'ok' },
    }), 'essais conformes, découplage non saisi')
    expect(enCours.resultat, 'réglages imposés : le découplage est exigé').toBe('en_cours')

    // À l'écran : la section MT est servie, le résultat calculé est « en cours ».
    await ouvrirJalonsChantier(page, etat.chantierId)
    await page.getByRole('button', { name: /fiche de recette/ }).first().click()
    const fiche = page.getByRole('dialog')
    await expect(fiche.getByTestId('recette-mt')).toBeVisible({ timeout: 30_000 })
    await expect(fiche.getByTestId('recette-resultat')).toContainText('En cours')
    await testInfo.attach('ciq665-recette-en-cours', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    // Découplage saisi « conforme » à l'écran → le serveur calcule « conforme ».
    await fiche.locator('#recette-decouplage_etat').selectOption('ok')
    await fiche.getByRole('button', { name: 'Enregistrer la fiche' }).click()
    await expect(fiche.getByTestId('recette-resultat')).toContainText('Conforme', { timeout: 20_000 })
    await testInfo.attach('ciq665-recette-conforme', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    expect((await fichesDuChantier(request))[0].resultat).toBe('conforme')

    // Un découplage « non conforme » est un essai faux ; remis conforme, il se rétablit.
    const faux = await lireJson(await request.patch(url, { data: { decouplage_etat: 'non_ok' } }),
      'découplage non conforme')
    expect(faux.resultat).toBe('non_conforme')
    const retabli = await lireJson(await request.patch(url, { data: { decouplage_etat: 'ok' } }),
      'découplage conforme')
    expect(retabli.resultat).toBe('conforme')
  })
})
