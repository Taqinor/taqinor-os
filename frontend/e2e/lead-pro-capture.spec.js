// CIQ424 — ALLER-RETOUR EN DIRECT du lead PRO : webhook du site → fiche →
// appel en 5 étapes → questionnaire pro → client entreprise → générateur.
//
// Pile locale `seed_demo`, AUCUN mock réseau. Six temps joués sur de vrais
// écrans et de vraies réponses serveur :
//   1. payload webhook commercial (MAD seul, tension pré-cochée) → la fiche
//      montre la section « Professionnel » ouverte, la tension marquée « défaut
//      visible du site » et les trois sections résidentielles repliées ;
//   2. le panneau d'appel saute ce que le site a donné (la facture) et propose
//      la visite avant devis (puissance souscrite, surface… inconnues) ;
//   3. le lien questionnaire ne coche que des sections pro ; une réponse
//      « société » avec ICE remplit les colonnes ;
//   4. le devis auto est prêt ; le devis créé au générateur donne un client
//      ENTREPRISE au nom de la société, ICE recopié ;
//   5. un lead résidentiel portant un devis industriel affiche le bandeau, et
//      son type ne change qu'après le clic confirmé ;
//   6. tranche Meta « plus_de_4000dh » : INCOMPATIBLE avec une pile locale (le
//      webhook Meta relit le détail du lead au Graph API de Meta et exige la
//      signature HMAC de l'app) — couvert par `tests_meta_form_mapping.py`.
//
// Prérequis pour les temps 1 à 4 : la pile e2e pose `WEBSITE_LEAD_WEBHOOK_SECRET`
// (même valeur que `E2E_WEBHOOK_SECRET` côté Playwright, défaut
// `e2e-webhook-secret`). Sans cela le récepteur est fermé (401) : ces temps se
// sautent en le DISANT. Nettoyage best-effort en afterAll (base partagée).
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, lireJson, posterWebhookSite, telephoneMobileUnique,
  creerDevisCommercialDepuisLead, uniq,
} from './helpers.js'

const CLE_REPLI = 'taqinor.lw.collapsed'
const leadIds = []
const devisIds = []
const clientIds = []
const jeton = String(Date.now()).slice(-9)
const societe = `Hôtel Atlas ${jeton}`
const ice = `${jeton}000000`
const email = `direction-${jeton}@hotel-atlas.example`
let lead = null
let jetonQuestionnaire = null
let webhookFerme = false

const leadDetail = async (request, id) => lireJson(
  await request.get(`${API}/crm/leads/${id}/`), `lead ${id}`)

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  await Promise.all(leadIds.map((id) => request.delete(`${API}/crm/leads/${id}/`).catch(() => null)))
  await Promise.all(clientIds.map((id) => request.delete(`${API}/crm/clients/${id}/`).catch(() => null)))
})

test.describe('CIQ424 — lead pro, du site au générateur', () => {
  test('1. webhook commercial : section Professionnel, tension « défaut visible », résidentiel replié', async ({ page, request }, testInfo) => {
    const nom = uniq('Pro E2E')
    const { status, corps } = await posterWebhookSite(request, {
      fullName: nom, phone: telephoneMobileUnique(), city: 'Casablanca', email,
      whatsappOptIn: true, mode: 'commercial', raisonSociale: societe,
      // MAD seul (aucun kWh), tension pré-cochée jamais touchée (pas de tensionSource).
      tensionRaccordement: 'bt', proMonthlyMad: 9000,
    })
    webhookFerme = status === 401
    test.skip(webhookFerme, 'webhook fermé (401) : poser WEBSITE_LEAD_WEBHOOK_SECRET = E2E_WEBHOOK_SECRET sur la pile e2e')
    expect(status, `webhook → HTTP ${status} ${JSON.stringify(corps)}`).toBe(201)
    leadIds.push(corps.lead_id)

    lead = await leadDetail(request, corps.lead_id)
    expect(lead.type_installation).toBe('commercial')
    expect(lead.societe).toBe(societe)
    expect(lead.tension_raccordement).toBe('bt')
    expect(lead.tension_source).toBe('site_defaut_visible')
    // « défaut visible » n'est jamais une déclaration : la tension reste à demander.
    expect(lead.entrees_ci?.manquants ?? []).toContain('tension_raccordement')

    // Les replis persistés d'une session précédente primeraient sur l'auto-repli.
    await page.addInitScript((cle) => { try { localStorage.removeItem(cle) } catch { /* sans stockage */ } }, CLE_REPLI)
    await page.goto(`/crm/leads/${lead.id}`)
    const pro = page.locator('section.lw-section[data-nav-id="pro"]')
    await expect(pro).toBeVisible({ timeout: 30_000 })
    await expect(pro.locator('.lw-section-head')).toHaveAttribute('aria-expanded', 'true')
    for (const id of ['energie', 'equipements', 'toiture']) {
      await expect(page.locator(`section.lw-section[data-nav-id="${id}"] .lw-section-head`),
        `section résidentielle « ${id} » repliée`).toHaveAttribute('aria-expanded', 'false')
    }
    await expect(pro.locator('#lf-tension-source')).toHaveValue('site_defaut_visible')
    await expect(pro.locator('[data-visite-avant-devis]')).toBeVisible()
    await testInfo.attach('ciq424-fiche-pro', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('2. panneau d’appel : saute ce que le site a donné, propose la visite avant devis', async ({ page, request }, testInfo) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    const panneau = await lireJson(
      await request.get(`${API}/crm/leads/${lead.id}/panneau-appel/`), 'panneau d’appel')
    expect(panneau.segment).toBe('commercial')
    const champs = (panneau.champs_a_poser || []).map((c) => c.champ)
    expect(champs, 'la facture (MAD) donnée par le site n’est pas redemandée').not.toContain('facture_hiver')
    expect(champs, 'aucune question résidentielle').not.toContain('occupation_jour')
    expect(champs, 'la puissance souscrite, inconnue, reste à poser').toContain('compteur_puissance_kva')

    const detail = await leadDetail(request, lead.id)
    expect(detail.devis_auto?.visite_avant_devis?.requise, 'visite avant devis requise').toBe(true)

    await page.goto(`/crm/leads/${lead.id}`)
    await page.locator('a.lw-rail-contact-link', { hasText: '☎' }).click()
    await expect(page.getByRole('dialog', { name: /Appel —/ })).toBeVisible()
    await expect(page.getByTestId('panneau-script-appel').first()).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('visite-avant-devis-pro')).toBeVisible()
    await testInfo.attach('ciq424-panneau-appel', {
      body: await page.screenshot(), contentType: 'image/png',
    })
  })

  test('3. questionnaire : sections pro seulement ; réponse « société » avec ICE', async ({ request, playwright, baseURL }) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    const lien = await lireJson(await request.post(
      `${API}/crm/leads/${lead.id}/questionnaire-lien/`, { data: {} }), 'lien du questionnaire')
    jetonQuestionnaire = lien.token
    expect(jetonQuestionnaire, 'jeton du questionnaire').toBeTruthy()
    const cochees = Object.entries(lien.questions || {}).filter(([, v]) => v).map(([k]) => k)
    expect(cochees.length, 'au moins une section posée').toBeGreaterThan(0)
    for (const residentielle of ['occupation', 'equipements', 'toiture', 'energie']) {
      expect(cochees, `section résidentielle « ${residentielle} »`).not.toContain(residentielle)
    }

    // Le client répond SANS session : contexte anonyme.
    const anonyme = await playwright.request.newContext({ baseURL })
    try {
      const lecture = await lireJson(
        await anonyme.get(`${API}/crm/public/questionnaire/${jetonQuestionnaire}/`), 'questionnaire public')
      expect(lecture.sections).toContain('societe')
      for (const residentielle of ['occupation', 'equipements', 'toiture', 'energie']) {
        expect(lecture.sections).not.toContain(residentielle)
      }
      const reponse = await lireJson(await anonyme.post(
        `${API}/crm/public/questionnaire/${jetonQuestionnaire}/`,
        { data: { section: 'societe', reponses: { societe, ice, fonction_contact: 'Directeur' } } }),
      'réponse « société »')
      expect(reponse.enregistrees).toEqual(expect.arrayContaining(['ice']))
    } finally {
      await anonyme.dispose()
    }
    const relu = await leadDetail(request, lead.id)
    expect(relu.ice).toBe(ice)
    expect(relu.societe).toBe(societe)
    expect(relu.fonction_contact).toBe('Directeur')
  })

  test('4. devis auto prêt ; devis créé → client ENTREPRISE au nom de la société, ICE recopié', async ({ page, request }, testInfo) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    const detail = await leadDetail(request, lead.id)
    expect(detail.devis_auto?.pret, `devis auto prêt (manque : ${JSON.stringify(detail.devis_auto?.manquants)})`).toBe(true)
    await page.goto(`/crm/leads/${lead.id}`)
    await expect(page.getByRole('button', { name: 'Devis automatique' })).toBeEnabled({ timeout: 30_000 })

    const devisId = await creerDevisCommercialDepuisLead(page, lead.id)
    devisIds.push(devisId)
    const devis = await lireJson(await request.get(`${API}/ventes/devis/${devisId}/`), 'devis')
    const clientId = devis.client?.id ?? devis.client
    expect(clientId, 'client résolu côté serveur').toBeTruthy()
    clientIds.push(clientId)
    const client = await lireJson(await request.get(`${API}/crm/clients/${clientId}/`), 'client')
    expect(client.type_client).toBe('entreprise')
    expect(client.nom).toBe(societe)
    expect(client.ice).toBe(ice)
    expect(client.contact_nom, 'la personne est le contact, pas le client').toBeTruthy()
    await testInfo.attach('ciq424-generateur', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('5. lead résidentiel + devis industriel : bandeau, type changé seulement après le clic confirmé', async ({ page, request }, testInfo) => {
    const residentiel = await lireJson(await request.post(`${API}/crm/leads/`, {
      data: {
        nom: uniq('Résidentiel E2E'), ville: 'Casablanca', telephone: telephoneMobileUnique(),
        type_installation: 'residentiel', facture_hiver: '800',
      },
    }), 'création du lead résidentiel')
    leadIds.push(residentiel.id)
    const devis = await lireJson(await request.post(`${API}/ventes/devis/`, {
      data: { lead: residentiel.id, taux_tva: '20.00', mode_installation: 'industriel' },
    }), 'devis industriel sur lead résidentiel')
    devisIds.push(devis.id)

    await page.goto(`/crm/leads/${residentiel.id}`)
    const bandeau = page.getByTestId('lw-incoherence-segment')
    await expect(bandeau).toBeVisible({ timeout: 30_000 })
    await testInfo.attach('ciq424-bandeau-incoherence', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    // Rien ne change tant que personne n'a cliqué.
    expect((await leadDetail(request, residentiel.id)).type_installation).toBe('residentiel')

    await bandeau.getByRole('button', { name: 'Passer en Industriel' }).click()
    const confirmation = page.getByRole('alertdialog')
    await expect(confirmation).toBeVisible()
    // Annuler ne change rien non plus.
    await confirmation.getByRole('button', { name: 'Annuler' }).click()
    // La 1re confirmation doit être REFERMÉE avant d'en rouvrir une : un clic
    // pendant sa fermeture n'ouvre rien (nocturne CAD177 : bandeau cliqué, aucune modale).
    await expect(confirmation).toHaveCount(0)
    expect((await leadDetail(request, residentiel.id)).type_installation).toBe('residentiel')

    await bandeau.getByRole('button', { name: 'Passer en Industriel' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Passer en Industriel' }).click()
    await expect.poll(async () => (await leadDetail(request, residentiel.id)).type_installation,
      { message: 'le type ne change qu’après la confirmation' }).toBe('industriel')
    await expect(page.getByTestId('lw-incoherence-segment')).toHaveCount(0)
  })

  test.fixme('6. payload Meta « plus_de_4000dh » : aucune facture à 4 000, tranche affichée', async () => {
    // Le webhook Meta (`/crm/webhooks/meta-lead-ads/`) refuse tout POST non signé
    // (HMAC de `META_LEAD_ADS_APP_SECRET`, QJR414) et relit ensuite le lead au
    // Graph API de Meta : aucune pile locale ne peut le rejouer. La règle est
    // gardée par `apps/crm/tests_meta_form_mapping.py` (facture vide, tranche
    // `{min_mad: 4000, max_mad: null}`) ; l'affichage de la tranche (lecture
    // seule, `#lf-facture-tranche`) par les tests de SectionPro.
  })
})
