// CIQ650 — ALLER-RETOUR EN DIRECT du parcours site professionnel BT :
// visite → lead → chantier → dossier 82-21 → recette → réception.
//
// Pile locale `seed_demo`, AUCUN mock réseau sur les écrans testés. Sept temps,
// sur de vraies réponses serveur (leçon QJR5 : « déployable ≠ vert ») :
//   1. lead commercial aux faits inconnus : la fiche dit « AVANT le devis » (règle
//      site professionnel, jamais « exception »), la visite `ci` se planifie par la
//      vraie fenêtre ;
//   2. relevé (mesures de l'exemple du contrat `visite_terrain.json`, deux zones,
//      deux mesures « non relevé » + motif, motif inconnu refusé) → terminer →
//      valider : le lead porte la puissance souscrite et la tension MESURÉES ;
//   3. devis commercial accepté → chantier BT (template C&I) et dossier 82-21 ouvert
//      tout seul, pièces sourcées, jamais un second dossier ;
//   4. « En cours » refusé avant la convention (saisie à l'écran du dossier), refusé
//      encore sans documents de sécurité, puis autorisé ;
//   5. recette saisie à l'écran du chantier : un essai raté → « non conforme »
//      CALCULÉ par le serveur ; corrigé avec une réserve → « conforme avec réserves » ;
//   6. portail client : il voit la recette et la réserve ouverte ;
//   7. réception provisoire, PV signé avec fonction (texte extrait du PDF), réception
//      définitive refusée tant que la réserve est ouverte, accordée une fois levée.
//
// PRÉREQUIS (le spec le dit plutôt que de simuler) : `manage.py shell` joignable
// pour les documents de sécurité (aucune API — module QHSE parqué) et le mot de
// passe du compte portail : `E2E_DJANGO_EXEC` (défaut : `docker compose exec -T
// django_core`, puis le Django de l'hôte `backend/django_core`).
// Nettoyage best-effort en afterAll (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, lireJson, listeDe, telephoneFixeUnique, isoDansJours, textePdf, uniq,
  creerDevisCommercialDepuisLead, mesuresContratVisite, planifierVisiteDepuisLead,
  remplirVisiteCi, ajouterDocumentsHse, contextePortailClient, PNG_1PX, ouvrirJalonsChantier,
} from './helpers.js'

const jeton = String(Date.now()).slice(-9)
const societe = `Hôtel Atlas ${jeton}`
const email = `direction-${jeton}@hotel-atlas.example`
const MOT_DE_PASSE_PORTAIL = 'Portail-E2E-2026!'
const MENTION_VISITE_PRO = 'Visite technique avant devis (règle site professionnel).'
const RESERVE = 'Réserve E2E coffret AC'
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
const raisons = async (reponse) => {
  const corps = await reponse.json()
  return [].concat(corps.statut ?? corps.detail ?? []).join(' ')
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(chantierIds.map((id) =>
    request.delete(`${API}/installations/chantiers/${id}/`).catch(() => null)))
  await Promise.all(devisIds.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  await Promise.all(leadIds.map((id) => request.delete(`${API}/crm/leads/${id}/`).catch(() => null)))
  await Promise.all(clientIds.map((id) => request.delete(`${API}/crm/clients/${id}/`).catch(() => null)))
})

test.describe('CIQ650 — site professionnel BT, de la visite à la réception', () => {
  test('1. lead commercial : « AVANT le devis » (pas « exception »), visite ci planifiée à l’écran', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    etat.lead = await lireJson(await request.post(`${API}/crm/leads/`, {
      data: {
        nom: uniq('Direction Chantier E2E'), societe, ville: 'Casablanca',
        telephone: telephoneFixeUnique(), email, type_installation: 'commercial',
        facture_hiver: '9000', langue_preferee: 'fr',
      },
    }), 'création du lead commercial')
    leadIds.push(etat.lead.id)
    const detail = await lireJson(await request.get(`${API}/crm/leads/${etat.lead.id}/`), 'lead')
    expect(detail.devis_auto?.visite_avant_devis?.requise,
      'tension, puissance souscrite et toit inconnus : visite avant devis').toBe(true)

    const avertissement = await planifierVisiteDepuisLead(page, etat.lead.id)
    expect(avertissement).toContain('AVANT le devis')
    expect(avertissement).toContain('Site professionnel')
    expect(avertissement, 'plus de mention « exception »').not.toContain('exception')
    await testInfo.attach('ciq650-visite-planifiee', {
      body: await page.screenshot(), contentType: 'image/png',
    })

    const historique = await lireJson(
      await request.get(`${API}/crm/leads/${etat.lead.id}/historique/`), 'historique')
    const notes = listeDe(historique).map((a) => String(a.body || ''))
      .filter((corps) => corps.includes('Visite technique planifiée'))
    expect(notes.length, 'note de planification dans l’historique').toBeGreaterThan(0)
    for (const corps of notes) expect(corps).toContain(MENTION_VISITE_PRO)

    const visites = (await lireJson(
      await request.get(`${API}/crm/leads/${etat.lead.id}/visites/`), 'visites du lead')).visites
    expect(visites.length).toBeGreaterThan(0)
    etat.visiteId = visites[0].id
    const visite = await lireJson(
      await request.get(`${API}/visites/visites/${etat.visiteId}/`), 'visite')
    expect(visite.gabarit, 'lead commercial : gabarit site professionnel').toBe('ci')
  })

  test('2. relevé (deux zones, « non relevé » + motif) → validé : le lead porte les mesures', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    const base = mesuresContratVisite('exemple_ci')
    const commerce = mesuresContratVisite('exemple_ci_commerce')
    const z1 = base.toiture_ci.zones_toiture[0]
    const z2 = { ...commerce.toiture_ci.zones_toiture[0], id: 'z2', libelle: 'Terrasse annexe' }
    const cleCharge = (zone) => `zones_toiture[${zone}].charge_admissible_declaree_kg_m2`

    // Un motif hors du vocabulaire fermé est refusé, l'erreur nomme la mesure.
    const refus = await request.patch(`${API}/visites/visites/${etat.visiteId}/mesures/`, {
      data: {
        categorie: 'toiture_ci',
        valeurs: { zones_toiture: [z1], _non_releves: { [cleCharge('z1')]: 'au_hasard' } },
      },
    })
    expect(refus.status(), 'motif « non relevé » inconnu').toBe(400)
    expect(Object.keys((await refus.json()).erreurs || {}).some((k) => k.startsWith('_non_releves')),
      'l’erreur nomme le champ « non relevé »').toBeTruthy()

    const mesures = {
      ...base,
      site_commerce: commerce.site_commerce,
      comptage: { ...base.comptage, niveau_tension_constate: 'bt', puissance_souscrite_kva_constatee: 36 },
      toiture_ci: {
        zones_toiture: [z1, z2],
        _non_releves: { [cleCharge('z1')]: 'non_applicable', [cleCharge('z2')]: 'acces_refuse' },
      },
    }
    const complete = await remplirVisiteCi(request, etat.visiteId, mesures)
    expect(complete.completude?.manquants, 'rien ne manque pour terminer').toEqual([])
    expect(complete.mesures.toiture_ci.zones_toiture).toHaveLength(2)
    expect(Object.keys(complete._non_releves || {}).length, 'deux mesures « non relevé »').toBe(2)

    await page.goto(`/visites/${etat.visiteId}`)
    await expect(page.getByText('Visite technique — site professionnel').first())
      .toBeVisible({ timeout: 30_000 })
    await testInfo.attach('ciq650-wizard-ci', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })

    const terminee = await lireJson(await request.post(
      `${API}/visites/visites/${etat.visiteId}/terminer/`, { data: {} }), 'terminer')
    expect(terminee.statut).toBe('terminee')
    expect(Number(terminee.releve_ci.surface_utile.constate),
      'surface = somme des zones (40 × 18 + 140)').toBeCloseTo(860, 0)
    const validee = await lireJson(await request.post(
      `${API}/visites/visites/${etat.visiteId}/valider/`, { data: {} }), 'valider')
    expect(validee.statut).toBe('validee')
    expect(validee.releve_ci.validee_le, 'relevé validé').toBeTruthy()

    const lead = await lireJson(await request.get(`${API}/crm/leads/${etat.lead.id}/`), 'lead relu')
    expect(Number(lead.compteur_puissance_kva), 'puissance souscrite mesurée').toBe(36)
    expect(lead.puissance_souscrite_source).toBe('mesure_visite')
    expect(lead.tension_raccordement).toBe('bt')
    expect(lead.tension_source).toBe('mesure_visite')
  })

  test('3. devis commercial accepté → chantier BT (template C&I) + dossier 82-21 ouvert, jamais deux', async ({ page, request }, testInfo) => {
    test.setTimeout(240_000)
    etat.devisId = await creerDevisCommercialDepuisLead(page, etat.lead.id)
    devisIds.push(etat.devisId)
    await lireJson(await request.post(`${API}/ventes/devis/${etat.devisId}/accepter/`,
      { data: { nom: 'Directeur E2E' } }), 'acceptation du devis')

    const chantier = await lireJson(await request.post(`${API}/installations/chantiers/creer-depuis-devis/`,
      { data: { devis: etat.devisId } }), 'chantier depuis le devis')
    etat.chantierId = chantier.id
    chantierIds.push(chantier.id)
    expect(chantier.type_installation).toBe('industriel')
    expect(chantier.niveau_tension, 'niveau recopié du lead (mesuré)').toBe('bt')
    expect(chantier.regime_8221, 'le régime est qualifié ou à qualifier, jamais « non concerné »')
      .not.toBe('non_concerne')
    if (chantier.client) clientIds.push(chantier.client)
    etat.clientId = chantier.client

    const checklist = await lireJson(await request.get(`${chantierUrl()}checklist/`), 'checklist')
    const cles = checklist.items.map((e) => e.cle)
    expect(cles, 'template « Site professionnel (BT) »').toContain('plan_prevention_signe')
    expect(cles).not.toContain('poste_livraison_controle')

    await expect.poll(async () => (await dossiersDuDevis(request)).length,
      { message: 'le chantier C&I ouvre seul son dossier 82-21' }).toBe(1)
    const [dossier] = await dossiersDuDevis(request)
    etat.dossierId = dossier.id
    expect(dossier.statut).toBe('en_constitution')
    expect(dossier.chantier, 'dossier lié au chantier').toBe(chantier.id)
    expect(dossier.checklist_items.length, 'pièces semées').toBeGreaterThan(0)
    expect(dossier.pieces.length).toBeGreaterThan(0)
    for (const piece of dossier.pieces) expect(piece.source, `source de « ${piece.label} »`).toBeTruthy()

    // Ré-émission (second appel de création) : toujours UN dossier.
    await lireJson(await request.post(`${API}/installations/chantiers/creer-depuis-devis/`,
      { data: { devis: etat.devisId } }), 'chantier redemandé')
    expect((await dossiersDuDevis(request)).length, 'jamais un second dossier').toBe(1)

    // APX25 : le parcours vit dans l'onglet « Jalons & gates ». Le stepper
    // `ch6-gate-timeline` n'existe que si la société a AMORCÉ son cycle
    // (AUD313 : `POST /etapes-chantier/amorcer/`, Directeur) — état partagé
    // qu'un spec ne mute pas ; la fiche ouverte montre sa recette dans les deux cas.
    await ouvrirJalonsChantier(page, chantier.id)
    await testInfo.attach('ciq650-chantier-ci', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('4. « En cours » refusé sans convention puis sans documents de sécurité, puis autorisé', async ({ page, request }, testInfo) => {
    test.setTimeout(180_000)
    const passerEnCours = () => request.patch(chantierUrl(), { data: { statut: 'en_cours' } })

    const sansConvention = await passerEnCours()
    expect(sansConvention.status(), 'travaux avant la convention').toBe(400)
    expect(await raisons(sansConvention)).toMatch(/convention de raccordement/)

    // La convention se saisit à l'écran du dossier réglementaire (étape « Convention »).
    await page.goto('/ventes/dossiers-reglementaires')
    await page.getByText('File de travail', { exact: true }).first().click()
    const ligne = page.locator(`li[data-dossier-id="${etat.dossierId}"]`)
    await expect(ligne).toBeVisible({ timeout: 30_000 })
    await ligne.getByRole('button', { name: 'Détail 82-21' }).click()
    const detail = page.getByTestId('dossier-detail-8221')
    await expect(detail).toBeVisible()
    await expect(detail.getByText(/Source :/).first(), 'pièces sourcées').toBeVisible()
    const aujourdhui = isoDansJours(0)
    await detail.locator('#dossier-convention_signee_le').fill(aujourdhui)
    await detail.getByRole('button', { name: 'Enregistrer le dossier' }).click()
    await expect.poll(async () => (await dossiersDuDevis(request))[0].convention_signee_le,
      { message: 'la convention saisie est enregistrée' }).toBe(aujourdhui)
    await testInfo.attach('ciq650-dossier-convention', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })

    const sansHse = await passerEnCours()
    expect(sansHse.status(), 'convention signée mais aucun document de sécurité').toBe(400)
    const motifs = await raisons(sansHse)
    expect(motifs).toMatch(/Documents de sécurité manquants/)
    expect(motifs, 'la convention n’est plus le motif').not.toMatch(/convention de raccordement/)

    ajouterDocumentsHse(etat.chantierId)
    const autorise = await lireJson(await passerEnCours(), 'passage « En cours » autorisé')
    expect(autorise.statut).toBe('en_cours')
  })

  test('5. recette à l’écran : essai raté → « non conforme » calculé ; corrigée avec une réserve', async ({ page, request }, testInfo) => {
    test.setTimeout(240_000)
    await ouvrirJalonsChantier(page, etat.chantierId)
    await page.getByRole('button', { name: /fiche de recette/ }).first().click()
    const fiche = page.getByRole('dialog')
    await expect(fiche.getByText('Fiche de recette (IEC 62446-1)')).toBeVisible({ timeout: 30_000 })

    for (const cle of ESSAIS) await fiche.locator(`#recette-${cle}`).selectOption('true')
    await fiche.locator('#recette-isolement_ok').selectOption('false')
    await fiche.locator('#recette-isolement_mohm').fill('0.4')
    // Le résultat est AFFICHÉ, jamais choisi : la case « avec réserves » est fermée.
    await expect(fiche.getByLabel('Conforme avec réserves')).toBeDisabled()
    await fiche.getByRole('button', { name: 'Enregistrer la fiche' }).click()
    await expect(fiche.getByTestId('recette-resultat')).toContainText('Non conforme', { timeout: 20_000 })
    await testInfo.attach('ciq650-recette-non-conforme', {
      body: await page.screenshot(), contentType: 'image/png',
    })

    // Corrigée : essai refait conforme, réserve ouverte, puis le seul choix humain.
    await fiche.locator('#recette-isolement_ok').selectOption('true')
    await fiche.locator('#reserve-description').fill(RESERVE)
    await fiche.locator('#reserve-echeance').fill(isoDansJours(30))
    await fiche.locator('#reserve-responsable').fill('Chef de chantier E2E')
    await fiche.getByRole('button', { name: 'Ajouter la réserve' }).click()
    await expect(fiche.getByTestId('recette-reserves').getByText(RESERVE)).toBeVisible({ timeout: 20_000 })
    await fiche.getByLabel('Conforme avec réserves').check()
    await fiche.getByRole('button', { name: 'Enregistrer la fiche' }).click()
    await expect(fiche.getByTestId('recette-resultat')).toContainText('Conforme avec réserves', { timeout: 20_000 })
    await testInfo.attach('ciq650-recette-reserves', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    await fiche.getByRole('button', { name: 'Fermer' }).first().click()

    const fiches = listeDe(await lireJson(await request.get(
      `${API}/installations/recettes-commissioning/?installation=${etat.chantierId}`), 'fiche de recette'))
    expect(fiches).toHaveLength(1)
    expect(fiches[0].resultat).toBe('reserves')
    expect(fiches[0].passe).toBe(true)
    const reserves = await lireJson(await request.get(`${chantierUrl()}reserves/`), 'réserves')
    const ouvertes = reserves.filter((r) => r.statut === 'ouverte')
    expect(ouvertes).toHaveLength(1)
    expect(ouvertes[0].description).toBe(RESERVE)
    expect(ouvertes[0].bloquante, 'réserve non bloquante : la réception reste possible').toBeFalsy()
    etat.reserveId = ouvertes[0].id
  })

  test('6. portail : le client voit la recette et la réserve, aucun prix', async ({ playwright, request, baseURL }) => {
    test.setTimeout(180_000)
    expect(etat.clientId, 'le chantier porte son client').toBeTruthy()
    const portail = await contextePortailClient(
      playwright, request, baseURL, etat.clientId, MOT_DE_PASSE_PORTAIL)
    try {
      const vue = await lireJson(await portail.get(`${API}/portail/mes-chantiers/${etat.chantierId}/`),
        'chantier côté client')
      expect(vue.recette_ci, 'le client voit la recette').toBeTruthy()
      expect(vue.recette_ci.resultat).toBe('reserves')
      expect(vue.recette_ci.reserves_ouvertes.map((r) => r.description)).toContain(RESERVE)
      expect(vue.recette_ci.reserves_ouvertes[0].date_echeance).toBe(isoDansJours(30))
      expect(JSON.stringify(vue.recette_ci)).not.toMatch(/instrument|prix_achat|technicien/)
    } finally {
      await portail.dispose()
    }
  })

  test('7. réception provisoire, PV signé avec fonction, définitive refusée tant que la réserve est ouverte', async ({ playwright, request, baseURL }) => {
    test.setTimeout(240_000)
    const receptionne = await lireJson(await request.patch(chantierUrl(),
      { data: { statut: 'receptionne' } }), 'réception provisoire')
    expect(receptionne.statut).toBe('receptionne')

    const signe = await lireJson(await request.post(`${chantierUrl()}signer-client/`, {
      data: {
        signature_client: `data:image/png;base64,${PNG_1PX.toString('base64')}`,
        signataire_nom: 'Karim Directeur', signataire_fonction: 'Directeur général',
        signataire_societe: societe,
      },
    }), 'signature du PV')
    expect(signe.signataire_fonction).toBe('Directeur général')

    const pdf = await request.get(`${API}/documents/chantiers/${etat.chantierId}/pv-reception/`)
    expect(pdf.status(), 'PV de réception').toBe(200)
    const texte = await textePdf(await pdf.body())
    expect(texte).toMatch(/Directeur général/)
    expect(texte).toMatch(/Recette de mise en service/)
    expect(texte, 'la réserve ouverte figure au PV').toMatch(/E2E coffret AC/)

    const refus = await request.post(`${chantierUrl()}reception-definitive/`, { data: {} })
    expect(refus.status(), 'définitive avec une réserve ouverte').toBe(400)
    const detailRefus = (await refus.json()).detail
    expect(detailRefus).toMatch(/réserve\(s\) non levée\(s\)/)
    expect(detailRefus).toContain(RESERVE)

    await lireJson(await request.post(`${chantierUrl()}reserves/${etat.reserveId}/lever/`,
      { data: { resolution: 'Étiquette posée (E2E)' } }), 'levée de la réserve')
    const definitive = await lireJson(await request.post(`${chantierUrl()}reception-definitive/`,
      { data: {} }), 'réception définitive')
    expect(definitive.date_reception_definitive, 'date de réception définitive').toBeTruthy()

    const portail = await contextePortailClient(
      playwright, request, baseURL, etat.clientId, MOT_DE_PASSE_PORTAIL)
    try {
      const vue = await lireJson(await portail.get(`${API}/portail/mes-chantiers/${etat.chantierId}/`),
        'chantier côté client')
      expect(vue.recette_ci.reserves_ouvertes, 'plus aucune réserve ouverte').toEqual([])
      expect(vue.recette_ci.date_reception_definitive).toBeTruthy()
    } finally {
      await portail.dispose()
    }
  })
})
