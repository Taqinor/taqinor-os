// AGR423 — ALLER-RETOUR EN DIRECT du lead AGRICOLE : site → fiche → appel →
// visite du point d'eau → lead → générateur.
//
// Pile locale `seed_demo`, AUCUN mock réseau. Six temps :
//   1. un payload webhook agricole du site (forage, HMT, besoin, butane, pompe
//      actuelle) est reçu et rangé en colonnes ;
//   2. la fiche montre la section « Pompage » remplie et ouverte, les trois
//      sections résidentielles repliées ;
//   3. le panneau d'appel saute ce que le site a donné et propose la visite de
//      relevé du point d'eau (niveau et débit du forage inconnus) ;
//   4. planifier la visite : l'écran dit la règle pompage, JAMAIS « exception »
//      (AGR408) ; le gabarit point_eau se termine sans aucune mesure de toit ;
//      la validation fait remonter le niveau mesuré sur le lead ;
//   5. le générateur ouvert depuis le lead est pré-rempli sans défaut inventé
//      (pas de distance 20 m, culture et région vides) et sans CV cible ;
//   6. un lead résidentiel portant un devis agricole affiche le bandeau, et son
//      type ne change qu'après le clic confirmé.
//
// Prérequis pour les temps 1 à 5 : la pile e2e pose `WEBSITE_LEAD_WEBHOOK_SECRET`
// (même valeur que `E2E_WEBHOOK_SECRET` côté Playwright, défaut
// `e2e-webhook-secret`). Sans cela le récepteur est fermé (401) : ces temps se
// sautent en le DISANT. Nettoyage best-effort en afterAll (base partagée).
import { test, expect } from '@playwright/test'
import {
  API_DJANGO as API, lireJson, posterWebhookSite, telephoneMobileUnique,
  isoDansJours, uniq, choisirMarche,
} from './helpers.js'

const CLE_REPLI = 'taqinor.lw.collapsed'
// PNG 1×1 valide : une vraie photo de slot (magic-bytes contrôlés par le serveur).
const PNG_1PX = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==',
  'base64')
const MENTION_POINT_EAU = 'Visite de relevé du point d’eau, avant devis (règle pompage).'

const leadIds = []
const devisIds = []
let lead = null
let visiteId = null
let webhookFerme = false

const leadDetail = async (request, id) => lireJson(
  await request.get(`${API}/crm/leads/${id}/`), `lead ${id}`)

async function sectionOuverte(page, id) {
  const tete = page.locator(`section.lw-section[data-nav-id="${id}"] .lw-section-head`)
  await expect(tete, `section « ${id} »`).toBeVisible({ timeout: 30_000 })
  return tete
}

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) => request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
  await Promise.all(leadIds.map((id) => request.delete(`${API}/crm/leads/${id}/`).catch(() => null)))
})

test.describe('AGR423 — lead agricole, du site au générateur', () => {
  test('1-2. webhook agricole : colonnes remplies, section Pompage ouverte, résidentiel replié', async ({ page, request }, testInfo) => {
    const nom = uniq('Ferme E2E')
    const { status, corps } = await posterWebhookSite(request, {
      fullName: nom, phone: telephoneMobileUnique(), city: 'Taroudant',
      whatsappOptIn: true, mode: 'agricole', waterSource: 'forage',
      hmtM: 60, besoinM3j: 80, pompeActuelle: 'butane', pompeCvActuelle: 5,
    })
    webhookFerme = status === 401
    test.skip(webhookFerme, 'webhook fermé (401) : poser WEBSITE_LEAD_WEBHOOK_SECRET = E2E_WEBHOOK_SECRET sur la pile e2e')
    expect(status, `webhook → HTTP ${status} ${JSON.stringify(corps)}`).toBe(201)
    leadIds.push(corps.lead_id)

    lead = await leadDetail(request, corps.lead_id)
    expect(lead.type_installation).toBe('agricole')
    expect(Number(lead.pompe_hmt_m)).toBe(60)
    expect(lead.pompe_hmt_source).toBe('site_web')
    expect(Number(lead.besoin_eau_m3j)).toBe(80)
    expect(lead.pompe_alim_actuelle).toBe('butane')
    // La pompe ACTUELLE n'est jamais le CV cible : colonne dédiée.
    expect(Number(lead.pompe_actuelle_cv)).toBe(5)
    expect(lead.niveau_statique_m ?? null, 'niveau d’eau inconnu').toBeNull()

    await page.addInitScript((cle) => { try { localStorage.removeItem(cle) } catch { /* sans stockage */ } }, CLE_REPLI)
    await page.goto(`/crm/leads/${lead.id}`)
    await expect(await sectionOuverte(page, 'pompage')).toHaveAttribute('aria-expanded', 'true')
    for (const id of ['energie', 'equipements', 'toiture']) {
      await expect(await sectionOuverte(page, id)).toHaveAttribute('aria-expanded', 'false')
    }
    const pompage = page.locator('section.lw-section[data-nav-id="pompage"]')
    await expect.poll(async () => Number(await pompage.locator('#lf-pompe-hmt').inputValue())).toBe(60)
    await expect.poll(async () => Number(await pompage.locator('#lf-besoin-eau').inputValue())).toBe(80)
    await expect(pompage.locator('#lf-pompe-alim-actuelle')).toHaveValue('butane')
    await testInfo.attach('agr423-fiche-pompage', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('3. panneau d’appel : saute ce que le site a donné, propose la visite du point d’eau', async ({ page, request }, testInfo) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    const panneau = await lireJson(
      await request.get(`${API}/crm/leads/${lead.id}/panneau-appel/`), 'panneau d’appel')
    expect(panneau.segment).toBe('agricole')
    const champs = (panneau.champs_a_poser || []).map((c) => c.champ)
    expect(champs, 'énergie actuelle donnée par le site').not.toContain('pompe_alim_actuelle')
    expect(champs, 'besoin en eau donné par le site').not.toContain('besoin_eau_m3j')
    expect(champs, 'le niveau d’eau, inconnu, reste à poser').toContain('niveau_statique_m')

    expect((await leadDetail(request, lead.id)).devis_auto?.visite_point_eau_avant_devis?.requise,
      'visite du point d’eau requise').toBe(true)
    await page.goto(`/crm/leads/${lead.id}`)
    await page.locator('a.lw-rail-contact-link', { hasText: '☎' }).click()
    await expect(page.getByRole('dialog', { name: /Appel —/ })).toBeVisible()
    await expect(page.getByTestId('panneau-script-appel').first()).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('visite-point-eau')).toBeVisible()
    await testInfo.attach('agr423-panneau-appel', {
      body: await page.screenshot(), contentType: 'image/png',
    })
  })

  test('4. planifier la visite : règle pompage (pas « exception »), relevé sans toit, retour au lead', async ({ page, request }, testInfo) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    // L'écran de la fiche dit la règle pompage…
    await page.goto(`/crm/leads/${lead.id}`)
    const tete = await sectionOuverte(page, 'visite')
    if ((await tete.getAttribute('aria-expanded')) === 'false') await tete.click()
    const avertissement = page.getByTestId('visite-sans-devis')
    await expect(avertissement).toContainText('AVANT le devis')
    await expect(avertissement).not.toContainText('exception')
    // …planifier passe par la vraie fenêtre.
    await page.getByRole('button', { name: 'Planifier la visite technique' }).click()
    await page.locator('#pv-date-prevue').fill(isoDansJours(3))
    await page.getByRole('button', { name: 'Planifier la visite', exact: true }).click()
    await expect(page.getByTestId('section-visite-row').first()).toBeVisible({ timeout: 30_000 })
    await testInfo.attach('agr423-visite-planifiee', {
      body: await page.screenshot(), contentType: 'image/png',
    })

    const historique = await lireJson(
      await request.get(`${API}/crm/leads/${lead.id}/historique/`), 'historique')
    const notes = (Array.isArray(historique) ? historique : historique.results || [])
      .map((a) => String(a.body || ''))
      .filter((corps) => corps.includes('Visite technique planifiée'))
    expect(notes.length, 'note de planification dans l’historique').toBeGreaterThan(0)
    for (const corps of notes) {
      expect(corps).toContain(MENTION_POINT_EAU)
      expect(corps, 'plus de mention « exception »').not.toContain('exception')
    }

    const liste = (await lireJson(
      await request.get(`${API}/crm/leads/${lead.id}/visites/`), 'visites du lead')).visites
    expect(liste.length).toBeGreaterThan(0)
    visiteId = liste[0].id

    // Le wizard du gabarit point_eau : aucun champ de toit, titre propre.
    const visite = await lireJson(
      await request.get(`${API}/visites/visites/${visiteId}/`), 'visite')
    expect(visite.gabarit).toBe('point_eau')
    expect(visite.photo_toit, 'aucun toit à assembler').toBeNull()
    const categories = visite.checklist.map((b) => b.categorie)
    expect(categories).toContain('point_eau')
    expect(categories).not.toContain('toiture')

    const mesures = {
      point_eau: { source_eau: 'forage', niveau_statique_m: 42, debit_mesure_m3h: 9 },
      pompe_existante: { pompe_presente: true },
      electricite: { electricite_sur_place: 'triphase' },
      site_pv: { distance_forage_champ_m: 120 },
      administratif: { autorisation_prelevement: 'en_cours', compteur_eau: false },
    }
    for (const [categorie, valeurs] of Object.entries(mesures)) {
      await lireJson(await request.patch(`${API}/visites/visites/${visiteId}/mesures/`,
        { data: { categorie, valeurs } }), `mesures « ${categorie} »`)
    }
    // Une vraie photo dans chaque slot requis (autant que `min_photos`).
    for (const bloc of visite.checklist) {
      for (const slot of bloc.slots.filter((s) => s.requis)) {
        for (let i = 0; i < (slot.min_photos || 1); i += 1) {
          await lireJson(await request.post(`${API}/visites/visites/${visiteId}/photos/`, {
            multipart: {
              slot_code: slot.code,
              fichier: { name: `${slot.code}-${i}.png`, mimeType: 'image/png', buffer: PNG_1PX },
            },
          }), `photo « ${slot.code} »`)
        }
      }
    }
    const complete = await lireJson(
      await request.get(`${API}/visites/visites/${visiteId}/`), 'visite complétée')
    expect(complete.completude?.manquants, 'rien ne manque pour terminer').toEqual([])
    await page.goto(`/visites/${visiteId}`)
    await expect(page.getByText('Visite de relevé du point d’eau').first()).toBeVisible({ timeout: 30_000 })
    await testInfo.attach('agr423-wizard-point-eau', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })

    const terminee = await lireJson(
      await request.post(`${API}/visites/visites/${visiteId}/terminer/`, { data: {} }), 'terminer')
    expect(terminee.statut).toBe('terminee')
    const validee = await lireJson(
      await request.post(`${API}/visites/visites/${visiteId}/valider/`, { data: {} }), 'valider')
    expect(validee.statut).toBe('validee')

    // Le niveau MESURÉ remonte sur le lead et remplace la déclaration.
    const relu = await leadDetail(request, lead.id)
    expect(Number(relu.niveau_statique_m)).toBe(42)
    expect(relu.niveau_statique_source).toBe('mesure_visite')
    expect(Number(relu.debit_forage_m3h)).toBe(9)
    expect(relu.devis_auto?.visite_point_eau_avant_devis?.requise,
      'point d’eau relevé : plus de visite requise').toBe(false)
  })

  test('5. générateur ouvert depuis le lead : pré-rempli sans défaut, sans CV cible', async ({ page }, testInfo) => {
    test.skip(webhookFerme, 'webhook fermé : voir le temps 1')
    await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
    await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
      .toBeVisible({ timeout: 30_000 })
    await choisirMarche(page, /Agricole/)
    await expect(page.getByTestId('bloc-cas-pompe')).toBeVisible()
    // Les valeurs reprises de la fiche, avec leur provenance.
    await expect(page.getByTestId('provenance-lead-pompage')).toBeVisible({ timeout: 30_000 })
    await expect.poll(async () => Number(await page.locator('#gen-hmt').inputValue())).toBe(60)
    // Aucune valeur inventée : pas de 20 m, pas de culture ni de région par défaut.
    // La distance est celle MESURÉE à la visite du temps 4 (`site_pv.
    // distance_forage_champ_m: 120`), remontée sur le lead : AGR420 pré-remplit
    // les valeurs « déclarées ou mesurées » — 120, jamais le 20 m de l'écran.
    await expect(page.locator('#gen-distance')).toHaveValue('120')
    await expect(page.locator('#gen-farm-crop')).toContainText('Non renseignée')
    await expect(page.locator('#gen-farm-region')).toContainText('Non renseignée')
    // La pompe ACTUELLE (5 CV) n'est jamais recopiée comme CV cible.
    const plaqueCv = page.locator('#gen-pompecv')
    if (await plaqueCv.count()) expect(await plaqueCv.inputValue()).not.toBe('5')
    // Le lead est agricole : aucun bandeau d'incohérence de segment.
    await expect(page.getByTestId('bandeau-segment-lead')).toHaveCount(0)
    await testInfo.attach('agr423-generateur', {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  })

  test('6. lead résidentiel + devis agricole : bandeau, type changé seulement après le clic confirmé', async ({ page, request }, testInfo) => {
    const residentiel = await lireJson(await request.post(`${API}/crm/leads/`, {
      data: {
        nom: uniq('Résidentiel E2E'), ville: 'Taroudant', telephone: telephoneMobileUnique(),
        type_installation: 'residentiel', facture_hiver: '800',
      },
    }), 'création du lead résidentiel')
    leadIds.push(residentiel.id)
    const devis = await lireJson(await request.post(`${API}/ventes/devis/`, {
      data: { lead: residentiel.id, taux_tva: '20.00', mode_installation: 'agricole' },
    }), 'devis agricole sur lead résidentiel')
    devisIds.push(devis.id)

    await page.goto(`/crm/leads/${residentiel.id}`)
    const bandeau = page.getByTestId('lw-incoherence-segment')
    await expect(bandeau).toBeVisible({ timeout: 30_000 })
    await testInfo.attach('agr423-bandeau-incoherence', {
      body: await page.screenshot(), contentType: 'image/png',
    })
    expect((await leadDetail(request, residentiel.id)).type_installation).toBe('residentiel')

    await bandeau.getByRole('button', { name: 'Passer en Agricole' }).click()
    const confirmation = page.getByRole('alertdialog')
    await expect(confirmation).toBeVisible()
    await confirmation.getByRole('button', { name: 'Annuler' }).click()
    // La 1re confirmation doit être REFERMÉE avant d'en rouvrir une : un clic
    // pendant sa fermeture n'ouvre rien (nocturne CAD177 : bandeau cliqué, aucune modale).
    await expect(confirmation).toHaveCount(0)
    expect((await leadDetail(request, residentiel.id)).type_installation).toBe('residentiel')

    await bandeau.getByRole('button', { name: 'Passer en Agricole' }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: 'Passer en Agricole' }).click()
    await expect.poll(async () => (await leadDetail(request, residentiel.id)).type_installation,
      { message: 'le type ne change qu’après la confirmation' }).toBe('agricole')
    await expect(page.getByTestId('lw-incoherence-segment')).toHaveCount(0)
  })
})
